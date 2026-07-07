# What The Rep — Master Plan

> A civic transparency platform that ingests public government data — starting with Marin County, CA and its
> incorporated cities/towns — into a general-purpose, time- and jurisdiction-searchable database, exposed
> entirely through an MCP (Model Context Protocol) server so that both a human-facing web UI and AI agents
> consume the exact same interface.

This document is the single source of truth for scope, architecture, schema, and roadmap. It should evolve as
decisions are revisited — update it in place rather than letting design knowledge live only in chat history.

---

## 1. Vision

Give any resident (or agent acting on their behalf) a fast answer to "what is my government doing?" — at every
level from town council to Congress — with:

- **Officeholders**: who currently holds office, and who has historically, in every elected/appointed seat.
- **Meetings**: schedules, agendas, minutes, video, for every governing body.
- **Actions**: motions, votes, resolutions, ordinances, appointments — with full roll-call detail and outcome.
- **Provenance**: every fact traceable to the government source it came from (or clearly marked secondary source).
- **Semantic search**: "show me everything about housing policy in Marin over the last year" should work as a
  query, powered by embeddings over topics/issues, not just keyword match.

We start narrow (Marin County + its 11 cities/towns) and deep (full data model, full pipeline, real ingestion),
so the hard design problems get solved once, on real data, rather than deferred.

## 2. Guiding Principles

1. **Provenance is non-negotiable.** Every ingested record carries a `sources[]` array (URL, publisher, method,
   retrieved_at). No fact without a source.
2. **Primary sources first.** Prefer the government's own website/API/document over secondary sources
   (Wikipedia, news, Ballotpedia). Secondary sources are allowed as enrichment/fallback, and are labeled as such.
3. **One general schema, not per-jurisdiction hacks.** A city council, a county board of supervisors, a state
   legislature chamber, and a chamber of Congress are all just a "governing body" that holds "meetings" and
   takes "actions." Modeling this once now avoids a rewrite when we go from Novato to Congress.
4. **One backend serves both humans and agents.** No parallel REST API. The Python MCP server is the only
   interface; the React frontend is itself an MCP client/host. Whatever an AI agent can query, the web UI can
   render, and vice versa, by construction.
5. **Structured data by default, rich UI when it earns it.** Simple lists/search results are plain structured
   tool output rendered with normal React components. Only genuinely rich views (vote tally charts, timelines,
   topic trends) are shipped as MCP-UI/MCP Apps resources rendered in a sandboxed iframe.
6. **Detect and reuse ingestion patterns.** Most local governments buy civic-tech software off the shelf
   (Granicus, Legistar, CivicClerk, CivicPlus, PrimeGov...). Every adapter we build for one vendor should work,
   with only config changes, for every other jurisdiction on that vendor. Onboarding a new city should get
   cheaper over time, not stay constant cost.
7. **Idempotent, incremental, auditable ingestion.** Re-running ingestion for a jurisdiction should be safe
   (upsert by external/vendor ID + content hash), and every run is logged for observability.

## 3. Confirmed Tech Stack & Key Decisions

| Area | Decision | Rationale |
|---|---|---|
| Database | **MongoDB Atlas** (managed) | Built-in Atlas Vector Search + Atlas Search (full text) + geospatial (`2dsphere`) in one product; free/dev tier is enough to start. |
| Embeddings | **Self-managed, local open-source model** (e.g. BAAI/BGE or `sentence-transformers` family), vectors stored in our own documents and indexed with **Atlas Vector Search** | Zero per-query API cost, no external API key dependency, fully reproducible offline. Atlas's own "Automated Embedding" (Voyage AI, public preview as of May 2026) was considered but rejected for now to avoid Public-Preview risk and per-token cost; the embedding generation step is built as a pluggable interface so we can swap in a hosted model (or Atlas Automated Embedding) later without a schema change. |
| Backend | **Python**, MCP server built on **FastMCP** (the de facto standard Python MCP framework, now merged into the official MCP Python SDK lineage) | Decorator-based tools/resources/prompts, built-in support for MCP Apps-style UI resources, async-first, good ecosystem for the scraping/parsing/NLP work ingestion needs. |
| UI delivery from backend | **MCP Apps / MCP-UI** (`ui://` resources, `_meta.ui.resourceUri` on tools, `text/html;profile=mcp-app` resources) via Python `mcp-ui-server` helpers | Officially standardized in 2026 (SEP-1865), backed by the MCP-UI project; lets the backend ship real interactive widgets (charts, timelines) that render identically in our own frontend and in any other MCP Apps-capable host (Claude, etc.). |
| Frontend | **React + TypeScript**, working **entirely through MCP** — the app is a custom MCP Host/Client (Streamable HTTP transport), using `@mcp-ui/client`'s `AppRenderer`/`UIResourceRenderer` to render UI resources, and plain React components to render structured tool output for simple views | Satisfies the "one backend for everyone" principle; avoids building/maintaining a second REST API surface. |
| Deployment (v1) | **Local/dev only** — Docker Compose for backend + frontend; MongoDB stays on Atlas (cloud) even in dev since we're using Atlas Vector Search | Fastest path to a working pilot; revisit real hosting (Fly.io/Render/GCP/etc.) once the pilot is validated. |
| Auth | **None for v1** — fully public, read-only | The data is public-record by nature; no need to gate reading it. Personalization (saved location, watchlists, alerts) is a later phase that will introduce accounts. |
| Geography bootstrap | **Marin County, CA + its 11 incorporated cities/towns** (Belvedere, Corte Madera, Fairfax, Larkspur, Mill Valley, Novato, Ross, San Anselmo, San Rafael, Sausalito, Tiburon), plus Marin County itself and stub records for California and the United States | Concrete, well-documented, small (~13 jurisdictions), and we already have real reference data on Novato + Marin County from this session's research to validate the schema against. |

## 4. System Architecture

```
                         ┌───────────────────────────────────────────┐
                         │              MongoDB Atlas                 │
                         │  jurisdictions, bodies, offices, people,    │
                         │  meetings, agenda_items, actions,           │
                         │  vote_records, documents, topics,           │
                         │  embedding_chunks, platform_adapters,       │
                         │  ingestion_runs                             │
                         │  + Atlas Vector Search + 2dsphere index     │
                         └───────────────▲──────────────┬─────────────┘
                                         │              │
                     writes (upserts)    │              │ reads (tools/resources)
                                         │              │
                 ┌───────────────────────┴───┐   ┌──────┴─────────────────────────┐
                 │     Ingestion Pipeline     │   │        MCP Server (Python)      │
                 │  (Python, run on schedule  │   │  FastMCP: tools + resources     │
                 │   or triggered on demand)  │   │  (ui:// MCP Apps resources)     │
                 │                            │   │  + local embedding model        │
                 │  discover → fetch → parse  │   │                                  │
                 │  → normalize → resolve     │   │  Streamable HTTP transport       │
                 │  → embed → store → link    │   └──────────────▲───────────────────┘
                 │                            │                  │ MCP (tools/resources)
                 │  Platform adapters:        │                  │
                 │   granicus / legistar /    │   ┌──────────────┴───────────────────┐
                 │   civicclerk / civicplus / │   │   React + TypeScript Frontend      │
                 │   primegov / custom_html   │   │   (itself an MCP Host/Client)      │
                 └────────────────────────────┘   │   @mcp-ui/client AppRenderer for    │
                                                   │   rich widgets; plain components    │
                                                   │   for lists/search/nav              │
                                                   └──────────────────────────────────────┘
                                                                    ▲
                                                                    │ also reachable by
                                                                    │ any other MCP host
                                                          ┌─────────┴─────────┐
                                                          │  External AI agents │
                                                          │  (Claude, etc.)     │
                                                          └─────────────────────┘
```

Two independent Python processes share the same database and Pydantic models: the **ingestion pipeline**
(writer) and the **MCP server** (reader, mostly). This separation lets us re-run/backfill ingestion without
touching the live query path, and lets the MCP server stay fast and stateless.

## 5. Database Schema (general: town → federal)

The schema is deliberately level-agnostic. A "city council," a "county board of supervisors," a "state
legislative chamber," and a "chamber of Congress" are all just a `governing_body`; a "vote on a use permit
appeal" and "a roll-call vote on a federal bill" are both just an `action` with `vote_records`. This is what
lets us climb the ladder from Novato to the U.S. Congress without a schema rewrite.

### Collections

**`jurisdictions`** — every government entity at any level, self-referencing for hierarchy.
```jsonc
{
  _id, slug: "novato-ca", name: "City of Novato",
  level: "city" | "town" | "county" | "state" | "federal"
       | "special_district" | "school_district" | "tribal_nation" | "joint_powers_authority",
  government_type: "general_law" | "charter" | "home_rule" | null,
  parent_id: ObjectId,          // Novato -> Marin County -> California -> United States
  path: [ObjectId, ...],        // materialized ancestor path, root-first, for fast subtree/ancestor queries
  fips: { state_fips, county_fips, place_fips, geoid },
  population: Number,
  website: String,
  boundary: GeoJSON,            // Polygon/MultiPolygon, 2dsphere-indexed, for point-in-polygon location lookup
  incorporated_date: Date,
  external_ids: { wikipedia, ballotpedia, osm_relation_id, ... },
  civic_platforms: [ { vendor, base_url, detected_at, confidence, notes } ],  // see platform_adapters
  status: "active" | "pilot" | "planned" | "stub",
  sources: [SourceRef], created_at, updated_at
}
```

**`governing_bodies`** — councils, boards, commissions, chambers, committees.
```jsonc
{ _id, jurisdiction_id, name: "City Council", type: "legislative"|"executive"|"judicial"|"advisory"|"commission",
  parent_body_id: null, meeting_cadence: "2nd/4th Tuesday 6:00pm", sources, created_at, updated_at }
```

**`offices`** — seats/positions that people hold over time (not the people themselves).
```jsonc
{ _id, jurisdiction_id, body_id: nullable, title: "District 1 Councilmember" | "Mayor" | "City Manager",
  selection_method: "elected_by_district"|"elected_at_large"|"appointed"|"annually_selected_by_body",
  district: "1" | null, term_length_months: 48, is_rotating_leadership: bool, sources }
```

**`people`** — individuals, independent of any office (so we can track a career across offices/jurisdictions).
```jsonc
{ _id, full_name, slug, bio, external_ids: { wikipedia, ballotpedia }, sources, created_at, updated_at }
```

**`office_tenures`** — who held what office, when. This is the backbone of "searchable by time."
```jsonc
{ _id, office_id, person_id, start_date, end_date: null,
  reason_ended: "term_expired"|"resigned"|"recalled"|"died"|"reorganization"|null,
  is_current: bool, sources }
```

**`meetings`**
```jsonc
{ _id, jurisdiction_id, body_id, scheduled_start, actual_start, location: { name, address, geo },
  meeting_type: "regular"|"special"|"study_session"|"closed_session"|"reorganization",
  status: "scheduled"|"held"|"cancelled"|"continued",
  video_url, external_id,       // vendor-native event/clip id, used for idempotent upsert
  sources }
```

**`agenda_items`**
```jsonc
{ _id, meeting_id, jurisdiction_id, body_id,     // denormalized for query speed
  item_number: "G.2", section: "consent_calendar"|"general_business"|"public_hearing"|"ceremonial"|"closed_session",
  title, description, staff_contact, document_ids: [ObjectId],
  topic_ids: [ObjectId], sources }
```

**`actions`** — the motion/vote/decision layer, attached to an agenda item.
```jsonc
{ _id, agenda_item_id, meeting_id, jurisdiction_id,
  action_type: "motion"|"resolution"|"ordinance"|"proclamation"|"appointment"|"minute_order",
  description, moved_by_office_tenure_id, seconded_by_office_tenure_id,
  outcome: "passed"|"failed"|"tabled"|"continued"|"withdrawn",
  vote_tally: { ayes, noes, abstain, absent, recuse },
  effective_date, document_ids: [ObjectId], sources }
```

**`vote_records`** — individual roll-call votes, enabling per-official voting-history analysis.
```jsonc
{ _id, action_id, office_tenure_id, person_id, vote: "aye"|"no"|"abstain"|"absent"|"recuse" }
```

**`documents`** — agendas, minutes, staff reports, resolutions, ordinances, transcripts.
```jsonc
{ _id, jurisdiction_id, related_type: "meeting"|"agenda_item"|"action", related_id,
  doc_type: "agenda"|"minutes"|"staff_report"|"resolution"|"ordinance"|"transcript"|"video"|"other",
  title, url, retrieved_at, content_hash, extracted_text_ref, mime_type, sources }
```

**`topics`** — curated + auto-discovered political issues/movements, for semantic tagging.
```jsonc
{ _id, slug: "housing", label, description, embedding: [Float], parent_topic_id: null, auto_generated: bool }
```

**`embedding_chunks`** — chunked text + vector, the substrate for semantic search (Atlas Vector Search index lives here).
```jsonc
{ _id, source_type: "agenda_item"|"document"|"meeting_summary", source_id,
  jurisdiction_id, body_id, meeting_id,     // denormalized for pre-filtering vector search
  text, embedding: [Float], model: "bge-small-en-v1.5", created_at }
```

**`platform_adapters`** — the "common software" registry that makes new jurisdictions cheaper over time.
```jsonc
{ _id, vendor: "granicus"|"legistar"|"civicclerk"|"civicplus"|"primegov"|"novusagenda"|"custom_html",
  jurisdiction_id, config: { base_url, client_id, view_id, api_key, selectors },
  capabilities: ["agendas","minutes","video","legislation_api"],
  detected_method: "manual"|"auto_fingerprint", last_verified_at, notes }
```

**`ingestion_runs`** — observability/audit trail for every pipeline execution.
```jsonc
{ _id, jurisdiction_id, adapter_vendor, started_at, finished_at, status: "success"|"partial"|"failed",
  stats: { meetings_found, meetings_upserted, agenda_items_upserted, actions_upserted, errors: [...] },
  triggered_by: "scheduled"|"manual"|"agent_tool" }
```

**`SourceRef`** (embedded shape reused everywhere, not a top-level collection):
```jsonc
{ url, publisher, retrieved_at, ingestion_run_id, method: "api"|"scrape"|"pdf_parse"|"manual", confidence }
```

### Indexing strategy

- **Time**: B-tree indexes on `meetings.scheduled_start`, `actions.effective_date`, compound with `jurisdiction_id`.
- **Government hierarchy**: compound index on `jurisdictions.path` (array) to answer "everything under Marin
  County" in one query; index on `parent_id` for direct children.
- **Geospatial**: `2dsphere` index on `jurisdictions.boundary` for point-in-polygon location resolution.
- **Full text**: Atlas Search index on `agenda_items.title/description` and `documents` extracted text, for
  fast keyword search as a complement to semantic search.
- **Semantic**: Atlas Vector Search index on `embedding_chunks.embedding`, pre-filterable by
  `jurisdiction_id`/`body_id`/date via the same document.

## 6. Ingestion Pipeline

**Stages** (pure functions where possible, orchestrated per jurisdiction + adapter):

1. **Discover** — list meetings (new or changed) for a jurisdiction/body since the last successful run.
2. **Fetch** — pull the raw agenda, minutes, and attachment documents (HTML/PDF/video metadata).
3. **Parse** — vendor-specific extraction into a common intermediate representation (agenda items, roll call,
   motions, outcomes).
4. **Normalize** — map the intermediate representation into canonical schema documents (see §5).
5. **Resolve entities** — match officials mentioned to existing `people`/`office_tenures` records (dedupe,
   create new tenure records on detected changes, e.g. a new mayor after a reorganization meeting).
6. **Embed** — chunk long text (agenda item descriptions, staff reports, minutes) and generate embeddings with
   the local model; write `embedding_chunks`.
7. **Store** — idempotent upsert keyed on vendor `external_id` + content hash, so re-runs are safe and cheap.
8. **Link** — associate agenda items/actions with `topics` (initially via curated keyword/embedding similarity
   rules; later via clustering).

**Adapter pattern** (Python `ABC`):

```python
class PlatformAdapter(ABC):
    vendor: str
    def detect(self, jurisdiction_website: str) -> DetectionResult | None: ...
    def discover_meetings(self, jurisdiction, since: date | None) -> list[RawMeetingRef]: ...
    def fetch_meeting_detail(self, ref: RawMeetingRef) -> RawMeetingDetail: ...
    def fetch_minutes(self, ref: RawMeetingRef) -> RawMinutes: ...
```

**Why this pays off**: our own research this session found that both `novato.gov` and Marin County
(`marin.granicus.com`) run on **Granicus**, and Granicus (and its acquisition Legistar, with a documented
`webapi.legistar.com` REST API) is extremely common among CA local governments. A single well-built
`GranicusAdapter` (HTML/PDF-based, since Granicus's public-facing `AgendaViewer`/`MinutesViewer`/`ViewPublisher`
pages don't expose a documented public API) is likely to cover most, possibly all, of Marin's 11 cities/towns
plus the county — meaning most of Phase 2 (§8) could be pure configuration, not new code. Cities that turn out
to run Legistar, CivicClerk, CivicPlus AgendaCenter, or PrimeGov get their own adapter, built once and reused
across every jurisdiction on that vendor everywhere in the country.

**Detection heuristic** (`detect()`): check the jurisdiction's website for known vendor fingerprints (subdomain
patterns like `*.granicus.com`, `webapi.legistar.com` references, CivicPlus/CivicClerk/PrimeGov script tags or
URL patterns). Long-term this becomes an MCP tool (`propose_new_jurisdiction`) that an agent can call with just
a city name/URL to scaffold a `jurisdictions` + `platform_adapters` record automatically — see Phase 6.

## 7. MCP Server Surface

**Tools** (initial set):

| Tool | Purpose |
|---|---|
| `resolve_location(lat, lng \| address)` | Point-in-polygon lookup against `jurisdictions.boundary` → returns the full jurisdiction stack (city, county, state, federal, special districts) for a location. |
| `get_jurisdiction(slug)` | Fetch a jurisdiction's profile: officeholders, bodies, recent activity summary. |
| `list_jurisdictions(parent_slug?, level?)` | Browse/search the jurisdiction hierarchy. |
| `get_home_summary(jurisdiction_slugs[])` | The "home page" call — recent meetings + top actions/votes + current officeholders across a location's full jurisdiction stack. Returns an MCP-UI resource. |
| `search_meetings(jurisdiction_slug?, body?, date_range?, query?)` | Structured list, plain output. |
| `get_meeting(meeting_id)` | Full agenda + actions + documents for one meeting. |
| `search_actions(query?, jurisdiction_slug?, topic?, date_range?, outcome?)` | Votes/motions/resolutions search. |
| `get_action(action_id)` | One action's full detail incl. roll-call vote records. Returns an MCP-UI resource (vote tally chart). |
| `get_official(person_id)` | Bio, tenure history, voting record. Returns an MCP-UI resource. |
| `semantic_search(query, topic_filter?, jurisdiction_filter?, date_range?)` | Vector search over `embedding_chunks`. |
| `list_topics()` / `get_topic(slug)` | Browse curated issues/movements; trend view. |
| `trigger_ingestion(jurisdiction_slug)` | Admin/agent-triggered pipeline run (Phase 2+, access-controlled later). |

**Resources** (`ui://`, MCP Apps / `text/html;profile=mcp-app`), used only where a rich widget earns its
complexity: `ui://home-summary`, `ui://meeting/{id}`, `ui://action/{id}` (vote tally), `ui://official/{id}`
(profile + voting history chart), `ui://topic/{slug}` (trend over time/jurisdiction). Everything else (browsing
lists, search results, nav) is plain `structuredContent` rendered by ordinary React components — we don't wrap
every screen in an iframe just because we can.

## 8. Frontend

React + TypeScript SPA that is itself an MCP Host/Client (Streamable HTTP transport):

- A thin MCP client wrapper handles connecting, calling tools, and reading resources.
- `@mcp-ui/client`'s `AppRenderer` (with the required sandboxed double-iframe proxy) renders any `ui://`
  resource returned by a tool call.
- Plain React components/routes render structured (non-UI-resource) tool output for jurisdiction browsing,
  search, and navigation.
- **Home page flow**: get the user's location (browser Geolocation API if permitted, else a manual
  city/address entry field — no IP-based inference by default, to avoid a hidden network dependency) →
  call `resolve_location` → call `get_home_summary` → render the returned UI resource.

## 9. Semantic / Embedding Layer

- **What gets embedded**: agenda item titles+descriptions, meeting minutes text, staff report text (chunked),
  and short summaries of actions/votes. Chunk size and overlap TBD during Phase 3 implementation.
- **Model**: a local open-source sentence-embedding model (e.g. a BGE or `sentence-transformers` small/base
  model), run inside the ingestion pipeline (and, for query-time embedding, inside the MCP server process) —
  no external API call, no per-query cost. Swappable behind a small `EmbeddingProvider` interface so we can
  later add a hosted-API or Atlas-Automated-Embedding provider without touching calling code.
- **Topics**: a curated seed taxonomy (e.g. housing, climate/environment, policing & public safety, cannabis
  policy, transportation/infrastructure, budget & taxation, land use & development — informed by real recent
  Marin/Novato agenda items we've already seen, like the Costco gas station appeal and cannabis retail debate)
  plus a later auto-discovery pass (clustering `embedding_chunks`) to surface emergent issues without manual
  curation.

## 10. Extensibility Roadmap (town → federal)

Because `jurisdictions`/`governing_bodies`/`offices`/`meetings`/`actions`/`vote_records` are level-agnostic,
expanding scope is additive, not a redesign:

- **City/Town** (Phase 1–2): Novato → all 11 Marin cities/towns.
- **County** (Phase 1): Marin County Board of Supervisors.
- **Other CA counties/cities** (Phase 4): reuse the adapter registry; onboarding cost should visibly drop.
- **State** (Phase 5): California State Assembly/Senate — new data source (e.g. `leginfo.legislature.ca.gov`),
  same schema (`body` = chamber, `action` = bill vote, `vote_records` = roll call).
- **Federal** (Phase 5+): U.S. Congress — new data source (e.g. congress.gov/GovInfo/ProPublica Congress API),
  same schema again.
- **Special/school districts, JPAs** (opportunistic): already modeled via `level` enum; populate as encountered
  (Marin alone has ~127 local government bodies including school and special districts).

## 11. Phased Milestones

- **Phase 0 — Foundations** *(this document + immediate next steps)*: repo scaffold, Atlas project, local
  embedding model chosen and smoke-tested, FastMCP skeleton, React app skeleton, Pydantic models mirroring §5.
- **Phase 1 — Marin pilot, end to end**: seed `jurisdictions` for US/CA (stubs) + Marin County + Novato; build
  the `GranicusAdapter`; ingest current officeholders + recent meetings/agendas/minutes/votes for both; ship
  the core MCP tools (§7, minus `semantic_search`/`trigger_ingestion`) and the home page + jurisdiction +
  meeting + official views in the frontend. No embeddings yet — structured data first.
- **Phase 2 — Rest of Marin**: onboard the remaining 10 cities/towns, maximizing `GranicusAdapter` reuse;
  populate `platform_adapters` properly; build one-off adapters only where a jurisdiction is on a different
  vendor.
- **Phase 3 — Semantic layer**: embedding pipeline stage, `topics` taxonomy, `semantic_search` tool, topic
  trend UI resource.
- **Phase 4 — Geographic expansion**: additional CA counties/cities, proving the adapter-reuse payoff.
- **Phase 5 — State & federal**: California legislature, then U.S. Congress.
- **Phase 6+**: agent-assisted onboarding (`propose_new_jurisdiction`), accounts/watchlists/alerts, real
  hosting/deployment, auto-discovered topics via clustering.

## 12. Non-Goals for v1

- No user accounts, auth, or personalization.
- No state/federal data (Phase 5+).
- No public write features (comments, petitions, etc.) — read-only civic data.
- No mobile app — responsive web only.
- No paid embedding/LLM API dependency for the core pipeline.

## 13. Open Questions (revisit as we build)

- Exact chunking strategy for embeddings (size/overlap) — decide during Phase 3 against real ingested text.
- Whether `boundary` geometries come from US Census TIGER/Line shapefiles or another authoritative source —
  decide during Phase 1 implementation of `resolve_location`.
- Long-term hosting target (Phase 6) — deferred per the local/dev-first decision.
- Whether/when to add Atlas Automated Embedding as an alternative `EmbeddingProvider` once it exits Public
  Preview.

## 14. Proposed Repo Structure (for the next step, not yet created)

```
what-the-rep/
  MASTER_PLAN.md
  README.md
  backend/
    mcp_server/        # FastMCP app: tools, ui:// resources, prompts
    ingestion/
      adapters/         # base.py, granicus.py, legistar.py, civicclerk.py, ...
      pipeline/          # discover.py, fetch.py, parse.py, normalize.py, resolve.py, embed.py, store.py, link.py
      registry/          # platform detection + jurisdiction seed data
    db/
      models/            # Pydantic schemas mirroring §5
    embeddings/          # local embedding model wrapper (EmbeddingProvider interface)
    tests/
    pyproject.toml
  frontend/
    src/
      mcp-client/        # MCP Streamable HTTP client wrapper
      ui-resources-host/ # AppRenderer + sandbox proxy integration
      components/
      pages/             # Home, Jurisdiction, Meeting, Official, Topic, Search
    package.json
  scripts/
    seed_marin.py        # bootstrap the 13 Phase-1 jurisdiction stubs
  docker-compose.yml      # backend + frontend for local dev (Mongo stays on Atlas)
  .env.example
```
