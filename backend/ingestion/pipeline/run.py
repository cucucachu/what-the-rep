"""Pipeline orchestrator — discover → fetch → parse → normalize → resolve → embed → store → link."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.common import IngestionRunStats
from db.models.enums import IngestionRunStatus, IngestionTriggeredBy, PlatformVendor
from db.models.ingestion_run import IngestionRun
from ingestion.adapters.granicus import GranicusAdapter
from ingestion.pipeline.config import get_granicus_config
from ingestion.pipeline.discover import discover_meetings
from ingestion.pipeline.embed import embed_meeting
from ingestion.pipeline.fetch import fetch_meeting_detail
from ingestion.pipeline.link import link_topics
from ingestion.pipeline.normalize import normalize_meeting
from ingestion.pipeline.parse import parse_meeting_detail
from ingestion.pipeline.resolve import resolve_officials
from ingestion.pipeline.store import store_meeting_graph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineRunResult:
    ingestion_run_id: ObjectId
    stats: IngestionRunStats
    status: IngestionRunStatus


async def _get_body_id(
    db: AsyncIOMotorDatabase, jurisdiction_id: ObjectId, body_name: str
) -> ObjectId:
    body = await db.governing_bodies.find_one(
        {"jurisdiction_id": jurisdiction_id, "name": body_name},
    )
    if body is None:
        raise ValueError(
            f"Governing body {body_name!r} not found for jurisdiction {jurisdiction_id}; "
            "seed officials first",
        )
    return body["_id"]


async def run_ingestion_pipeline(
    db: AsyncIOMotorDatabase,
    jurisdiction_slug: str,
    *,
    since: date | None = None,
    triggered_by: IngestionTriggeredBy = IngestionTriggeredBy.MANUAL,
) -> PipelineRunResult:
    """Run the full ingestion pipeline for one jurisdiction."""
    config = get_granicus_config(jurisdiction_slug)
    adapter = GranicusAdapter(config)
    started_at = datetime.now(tz=UTC)

    jurisdiction = await db.jurisdictions.find_one({"slug": jurisdiction_slug})
    if jurisdiction is None:
        raise ValueError(f"Jurisdiction {jurisdiction_slug!r} not found")
    jurisdiction_id = jurisdiction["_id"]
    body_id = await _get_body_id(db, jurisdiction_id, config.body_name)

    run = IngestionRun(
        jurisdiction_id=jurisdiction_id,
        adapter_vendor=PlatformVendor.GRANICUS,
        started_at=started_at,
        status=IngestionRunStatus.FAILED,
        stats=IngestionRunStats(),
        triggered_by=triggered_by,
    )
    insert = await db.ingestion_runs.insert_one(run.to_mongo())
    run_id = insert.inserted_id

    stats = IngestionRunStats()
    errors: list[str] = []
    status = IngestionRunStatus.SUCCESS

    try:
        refs = discover_meetings(adapter, jurisdiction_slug, since)
        stats.meetings_found = len(refs)

        for ref in refs:
            raw = fetch_meeting_detail(adapter, ref)
            parsed = parse_meeting_detail(
                raw,
                publisher=config.publisher,
                retrieved_at=started_at,
            )
            normalized = normalize_meeting(
                parsed,
                is_marin=jurisdiction_slug == "marin-county-ca",
            )
            resolve_result = await resolve_officials(
                db,
                normalized,
                jurisdiction_id=jurisdiction_id,
                body_id=body_id,
                ingestion_run_id=run_id,
            )
            if resolve_result.unresolved_names:
                logger.warning(
                    "Meeting %s unresolved officials: %s",
                    normalized.external_id,
                    resolve_result.unresolved_names,
                )
            embed_meeting(resolve_result.meeting)
            stored = await store_meeting_graph(
                db,
                resolve_result.meeting,
                jurisdiction_id=jurisdiction_id,
                body_id=body_id,
                ingestion_run_id=run_id,
                now=started_at,
            )
            link_topics(resolve_result.meeting)
            stats.meetings_upserted += stored.stats.meetings_upserted
            stats.agenda_items_upserted += stored.stats.agenda_items_upserted
            stats.actions_upserted += stored.stats.actions_upserted
    except Exception as exc:  # noqa: BLE001 — pipeline records failure on run record
        errors.append(str(exc))
        status = IngestionRunStatus.FAILED
    finally:
        finished_at = datetime.now(tz=UTC)
        stats.errors = errors
        if errors and status != IngestionRunStatus.FAILED:
            status = IngestionRunStatus.PARTIAL
        await db.ingestion_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "finished_at": finished_at,
                    "status": status.value,
                    "stats": stats.model_dump(),
                },
            },
        )

    return PipelineRunResult(ingestion_run_id=run_id, stats=stats, status=status)
