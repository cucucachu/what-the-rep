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
| Python package manager | **`uv`** (Astral) for dependency management, virtualenvs, and running scripts/tests (`uv sync`, `uv run pytest`, `uv add <pkg>`), with `pyproject.toml` + a committed `uv.lock` as the source of truth for both the `backend/` package and any top-level `scripts/` | Single fast tool for venv + resolution + lockfile + running commands, avoids juggling `pip`/`venv`/`pip-tools` separately; reproducible installs via the lockfile across dev machines and CI. |
| UI delivery from backend | **MCP Apps / MCP-UI** (`ui://` resources, `_meta.ui.resourceUri` on tools, `text/html;profile=mcp-app` resources) via Python `mcp-ui-server` helpers | Officially standardized in 2026 (SEP-1865), backed by the MCP-UI project; lets the backend ship real interactive widgets (charts, timelines) that render identically in our own frontend and in any other MCP Apps-capable host (Claude, etc.). |
| Frontend | **React + TypeScript**, working **entirely through MCP** — the app is a custom MCP Host/Client (Streamable HTTP transport), using `@mcp-ui/client`'s `AppRenderer`/`UIResourceRenderer` to render UI resources, and plain React components to render structured tool output for simple views | Satisfies the "one backend for everyone" principle; avoids building/maintaining a second REST API surface. |
| Deployment (v1) | **Local/dev only** — Docker Compose for backend + frontend; MongoDB stays on Atlas (cloud) even in dev since we're using Atlas Vector Search | Fastest path to a working pilot; revisit real hosting (Fly.io/Render/GCP/etc.) once the pilot is validated. |
| Auth | **None for v1** — fully public, read-only | The data is public-record by nature; no need to gate reading it. Personalization (saved location, watchlists, alerts) is a later phase that will introduce accounts. |
| Geography bootstrap | **Marin County, CA + its 11 incorporated cities/towns** (Belvedere, Corte Madera, Fairfax, Larkspur, Mill Valley, Novato, Ross, San Anselmo, San Rafael, Sausalito, Tiburon), plus Marin County itself and stub records for California and the United States | Concrete, well-documented, small (~13 jurisdictions), and we already have real reference data on Novato + Marin County from this session's research to validate the schema against. |
| Agentic layer | **LangChain `deepagents`** (a LangGraph-based agent harness) running server-side in the Python backend, consuming our *own* MCP tools via `langchain-mcp-adapters`' `MultiServerMCPClient`, and exposed back out as a single **`ask_agent`** MCP tool. LLM provider: **Anthropic Claude API**, key held server-side only, never sent to the browser. | Gives a production-grade agent loop (planning, sub-agents, context management, human-in-the-loop tool approval) without hand-rolling one, and keeps the "one backend, one MCP interface" principle intact — the frontend never talks to Claude directly or holds a key, it just calls one more tool. Confirmed during research: Anthropic has no ephemeral/scoped-token mechanism for the plain Messages API usable by anonymous browser sessions (Workload Identity Federation only federates a *workload's own* cloud IdP identity), so a public, no-auth app cannot safely call Claude directly from the browser with our key. See §8. |
| Rate limiting / abuse prevention | **Tiered, IP-keyed rate limiting** at the MCP server's HTTP layer (in-memory token buckets for the v1 single-instance deployment), plus a **persisted daily budget cap** for `ask_agent` stored in MongoDB. Expensive/mutating tools (`trigger_ingestion`, future `propose_new_jurisdiction`) are disabled or admin-gated, not publicly callable. | We have no accounts to attach per-user limits to, and `ask_agent` calls a paid API — needs abuse/runaway-cost protection from day one, not bolted on after a bill shock. See §9. |
| Testing | **Backend**: `pytest` + `pytest-asyncio`; `mongomock` or a dockerized MongoDB instance for DB-touching tests; recorded HTML/PDF fixtures (VCR-style) for scraper/adapter tests, so parsing logic is tested against real captured markup without live network calls in CI. **Frontend**: `Vitest` + React Testing Library for component/unit tests; `Playwright` for end-to-end/integration tests against a real running backend. | Locked in during MVP issue-planning (2026-07-06) so every implementation ticket has an unambiguous, consistent testing convention from the start. |

## 4. System Architecture

```
                         ┌───────────────────────────────────────────┐
                         │              MongoDB Atlas                 │
                         │  jurisdictions, bodies, offices, people,    │
                         │  meetings, agenda_items, actions,           │
                         │  vote_records, documents, topics,           │
                         │  embedding_chunks, platform_adapters,       │
                         │  ingestion_runs, agent_usage_daily          │
                         │  + Atlas Vector Search + 2dsphere index     │
                         └───────────────▲──────────────┬─────────────┘
                                         │              │
                     writes (upserts)    │              │ reads (tools/resources) +
                                         │              │ budget-cap read/write
                 ┌───────────────────────┴───┐   ┌──────┴─────────────────────────────────────┐
                 │     Ingestion Pipeline     │   │            MCP Server (Python, FastMCP)      │
                 │  (Python, run on schedule  │   │  ┌─────────────────────────────────────────┐ │
                 │   or triggered on demand)  │   │  │ Rate limiter (per-IP) + budget guard (§9)│ │
                 │                            │   │  └─────────────────────────────────────────┘ │
                 │  discover → fetch → parse  │   │  Structured tools + ui:// resources (§7)      │
                 │  → normalize → resolve     │   │  ask_agent tool (§8) ──────┐                  │
                 │  → embed → store → link    │   │                            ▼                  │
                 │                            │   │                 Deep Agent (deepagents +       │
                 │  Platform adapters:        │   │                 LangGraph), in-process,         │
                 │   granicus / legistar /    │   │                 calls this server's own tools    │
                 │   civicclerk / civicplus / │   │                 via langchain-mcp-adapters         │
                 │   primegov / custom_html   │   │                            │                        │
                 └────────────────────────────┘   │                            ▼                        │
                                                   │                 Anthropic Claude API                │
                                                   │                 (server-held key, never in browser)  │
                                                   │  Streamable HTTP transport                            │
                                                   └──────────────▲─────────────────────────────────────────┘
                                                                  │ MCP (tools/resources)
                                                   ┌──────────────┴───────────────────┐
                                                   │   React + TypeScript Frontend      │
                                                   │   (itself an MCP Host/Client)      │
                                                   │   @mcp-ui/client AppRenderer for    │
                                                   │   rich widgets; plain components    │
                                                   │   for lists/search/nav; calls        │
                                                   │   ask_agent like any other tool      │
                                                   └──────────────────────────────────────┘
                                                                    ▲
                                                                    │ also reachable by
                                                                    │ any other MCP host
                                                          ┌─────────┴─────────┐
                                                          │  External AI agents │
                                                          │  (Claude Desktop,   │
                                                          │   Cursor, etc. —    │
                                                          │   their own key)    │
                                                          └─────────────────────┘
```

Two independent Python processes share the same database and Pydantic models: the **ingestion pipeline**
(writer) and the **MCP server** (reader, mostly, plus the agent's occasional `trigger_ingestion` call once that
tool is enabled). This separation lets us re-run/backfill ingestion without touching the live query path, and
lets the MCP server stay fast and stateless. Note the frontend never gains a second interface — `ask_agent` is
just another MCP tool call from its point of view; all the LLM/agent complexity is hidden behind the MCP
boundary, server-side.

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
plus the county — meaning most of Phase 2 (§13) could be pure configuration, not new code. Cities that turn out
to run Legistar, CivicClerk, CivicPlus AgendaCenter, or PrimeGov get their own adapter, built once and reused
across every jurisdiction on that vendor everywhere in the country.

**Detection heuristic** (`detect()`): check the jurisdiction's website for known vendor fingerprints (subdomain
patterns like `*.granicus.com`, `webapi.legistar.com` references, CivicPlus/CivicClerk/PrimeGov script tags or
URL patterns). Long-term this becomes an MCP tool (`propose_new_jurisdiction`) that an agent can call with just
a city name/URL to scaffold a `jurisdictions` + `platform_adapters` record automatically — see Phase 7+ (§13).

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
| `ask_agent(question, jurisdiction_context?)` | The one agentic tool — see §8. Backed by a server-side deep agent; strictly rate-limited/budget-capped (§9). |
| `trigger_ingestion(jurisdiction_slug)` | Pipeline run trigger. **Disabled/admin-only in v1** (no auth to gate it properly yet — see §9) — revisit once we have real access control. |

**Resources** (`ui://`, MCP Apps / `text/html;profile=mcp-app`), used only where a rich widget earns its
complexity: `ui://home-summary`, `ui://meeting/{id}`, `ui://action/{id}` (vote tally), `ui://official/{id}`
(profile + voting history chart), `ui://topic/{slug}` (trend over time/jurisdiction). Everything else (browsing
lists, search results, nav) is plain `structuredContent` rendered by ordinary React components — we don't wrap
every screen in an iframe just because we can.

## 8. Agentic Layer: `ask_agent`

This section resolves a design question worked through in detail during planning: how to give the app a real
agentic/conversational mode without either (a) exposing our Anthropic API key in the browser, or (b) breaking
the "frontend talks only to our MCP server" principle by bolting on a second, agent-specific backend interface.

### Why the browser can't call Claude directly

Anthropic supports direct browser→API calls via the `anthropic-dangerous-direct-browser-access` header, but
that requires embedding a real API key in client code — viable only for "bring your own key" tools where the
*user's own* key sits in their own browser. Anthropic's other non-static-key auth mechanism, **Workload
Identity Federation**, exchanges a *workload's own* cloud-IdP identity (AWS/GCP/Azure/K8s/OIDC) for a
short-lived Anthropic token — it authenticates a server we control, not an anonymous browser tab, so it doesn't
help here either. Unlike Gemini Live or OpenAI Realtime, Anthropic has no "mint a short-lived, scoped token for
an anonymous client" mechanism for the plain Messages API. **Conclusion: the Claude API call must happen
server-side, behind our key, for a public multi-tenant app.** (A future "bring your own key" power-user mode
is a possible later addition, but is not the default — see §14.)

### Design: the agent lives behind one more MCP tool, not beside the MCP server

- **Framework**: [`deepagents`](https://github.com/langchain-ai/deepagents) (LangChain/LangGraph's opinionated
  agent harness) running **inside the Python MCP server process** (or a sibling process it calls in-process —
  implementation detail, not a second public interface either way).
- **Tools available to the deep agent**: the *same* tools defined in §7, loaded via `langchain-mcp-adapters`'
  `MultiServerMCPClient` pointed at our own MCP endpoint. This means there is exactly one implementation of
  "search meetings," "get an official's voting history," etc. — used identically by external agents, our own
  frontend's direct tool calls, and our own backend agent. No duplicate tool logic.
- **Model**: Anthropic Claude, called with a server-held `ANTHROPIC_API_KEY` (env var / secrets manager) —
  never sent to, or readable from, the browser.
- **Exposure**: the deep agent itself is wrapped in a single new tool, `ask_agent(question, jurisdiction_context?)`,
  registered on our MCP server. From the frontend's perspective, asking the agent a question is just another
  MCP tool call — it doesn't know or care that an LLM and a multi-step agent loop are involved. This keeps
  Guiding Principle #4 ("one backend serves both humans and agents") intact even though we've added an LLM.
- **Streaming**: MCP's token-level/streaming primitives ("tasks") are still experimental as of this writing.
  For v1, `ask_agent` is a synchronous request/response tool call (optionally with MCP progress notifications
  for coarse status like "Searching meetings…" while the agent works) rather than token-by-token streaming.
  This is simpler to build and arguably more in keeping with a "minimal" UI — revisit once MCP task/streaming
  primitives mature.
- **Bonus, essentially free**: because our MCP server is a standard remote MCP server, anyone can already point
  their *own* MCP host (Claude Desktop, Claude.ai custom connectors, Cursor, etc.) at it and get a fully
  agentic experience using their own account/subscription — no key-exposure risk to us, no extra engineering.
  Worth surfacing in docs/UI as "connect this to your own AI assistant" once we have a stable public URL.

## 9. Rate Limiting & Abuse Prevention

Because v1 has no accounts (§3), we can't attach limits to a user — every anonymous caller looks the same, and
one of our tools (`ask_agent`) calls a paid external API. This needs guardrails from day one, not after a bill
shock or an outage.

### Tiers, by cost

| Tier | Tools | v1 default limit (tunable via env) |
|---|---|---|
| Read-only / DB-only | `resolve_location`, `get_jurisdiction`, `list_jurisdictions`, `get_home_summary`, `search_meetings`, `get_meeting`, `search_actions`, `get_action`, `get_official`, `list_topics`, `get_topic` | Generous — e.g. 60 requests/min and 1,000/day per IP. |
| Semantic search | `semantic_search` | Moderate — e.g. 20 requests/min per IP (embeds the query text, then a vector search). |
| Agentic (paid LLM) | `ask_agent` | Strict per-IP cap (e.g. 5/hour) **and** a global daily budget cap shared across all callers (e.g. a max call count or estimated-token spend per day). Once the global cap is hit, respond with a graceful "high demand, please try search instead" message rather than an error. |
| Mutating / admin | `trigger_ingestion`, future `propose_new_jurisdiction` | Not publicly reachable in v1 — disabled or gated behind a separate admin secret header, independent of the per-IP limiter. Real per-user access control arrives with accounts (Phase 7+). |

### Implementation

- **Per-IP limiting**: middleware in front of the MCP server's HTTP (Streamable HTTP) transport, keyed by
  client IP, using a token-bucket/sliding-window algorithm. v1 keeps this **in-memory** since we're running a
  single backend instance locally; the moment we run more than one instance (Phase 7+ real hosting), this
  needs to move to a shared store (e.g. Redis) so limits are consistent across instances. Documented as an
  explicit upgrade step, not a surprise.
- **Global agent budget guard**: unlike the per-IP limiter, this must be authoritative and survive restarts, so
  it's backed by MongoDB, not memory: a small `agent_usage_daily` collection (`{ _id: "2026-07-06",
  ask_agent_calls, estimated_tokens, updated_at }`), incremented atomically on every `ask_agent` call. Cheap
  enough to hit MongoDB for this, since `ask_agent` calls are inherently low-frequency compared to structured
  tool calls.
- **Basic hygiene alongside rate limiting**: request body size limits, per-connection concurrency caps, and
  sane timeouts on every tool (especially `ask_agent`, which can otherwise run long agent loops indefinitely).
- **What app-level limiting does *not* solve**: real volumetric DDoS protection belongs at the network/CDN
  edge (e.g. Cloudflare or equivalent), which we don't have in the v1 local/dev deployment. This is flagged
  explicitly as a prerequisite for real public hosting (Phase 7+), not something app code alone can fully
  solve — see §15.

## 10. Frontend

React + TypeScript SPA that is itself an MCP Host/Client (Streamable HTTP transport):

- A thin MCP client wrapper handles connecting, calling tools, and reading resources.
- `@mcp-ui/client`'s `AppRenderer` (with the required sandboxed double-iframe proxy) renders any `ui://`
  resource returned by a tool call.
- Plain React components/routes render structured (non-UI-resource) tool output for jurisdiction browsing,
  search, and navigation.
- **Home page flow**: get the user's location — **browser Geolocation API first** (if permitted), **then
  IP-based geolocation as an automatic fallback** (revised 2026-07-06; supersedes the original "no IP-based
  inference by default" stance since a fully manual flow was judged too much friction for the home-page
  first-run experience), **then a manual city/address entry field** as the last resort if both fail — →
  call `resolve_location` → call `get_home_summary` → render the returned UI resource. Revisit this if
  IP-based geolocation proves too inaccurate in practice (it's typically city/ZIP-level, which is enough to
  resolve a city/county but not precise enough for, e.g., district-level jurisdiction lookups).
- **Agentic mode**: a minimal chat-style affordance that calls `ask_agent` like any other tool — no separate
  client, no separate connection, no awareness that an LLM is involved on the other end.

## 11. Semantic / Embedding Layer

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

## 12. Extensibility Roadmap (town → federal)

Because `jurisdictions`/`governing_bodies`/`offices`/`meetings`/`actions`/`vote_records` are level-agnostic,
expanding scope is additive, not a redesign:

- **City/Town** (Phase 1–2): Novato → all 11 Marin cities/towns.
- **County** (Phase 1): Marin County Board of Supervisors.
- **Other CA counties/cities** (Phase 5): reuse the adapter registry; onboarding cost should visibly drop.
- **State** (Phase 6): California State Assembly/Senate — new data source (e.g. `leginfo.legislature.ca.gov`),
  same schema (`body` = chamber, `action` = bill vote, `vote_records` = roll call).
- **Federal** (Phase 6+): U.S. Congress — new data source (e.g. congress.gov/GovInfo/ProPublica Congress API),
  same schema again.
- **Special/school districts, JPAs** (opportunistic): already modeled via `level` enum; populate as encountered
  (Marin alone has ~127 local government bodies including school and special districts).

## 13. Phased Milestones

- **Phase 0 — Foundations** *(this document + immediate next steps)*: repo scaffold, Atlas project, local
  embedding model chosen and smoke-tested, FastMCP skeleton, React app skeleton, Pydantic models mirroring §5.
- **Phase 1 — Marin pilot, end to end**: seed `jurisdictions` for US/CA (stubs) + Marin County + Novato; build
  the `GranicusAdapter`; ingest current officeholders + recent meetings/agendas/minutes/votes for both; ship
  the core MCP tools (§7, minus `semantic_search`/`ask_agent`/`trigger_ingestion`) and the home page +
  jurisdiction + meeting + official views in the frontend. No embeddings, no agent yet — structured data first.
  Basic per-IP rate limiting on the read-only tier goes in now, even though the expensive tier doesn't exist
  yet — cheap to add early, awkward to retrofit.
- **Phase 2 — Rest of Marin**: onboard the remaining 10 cities/towns, maximizing `GranicusAdapter` reuse;
  populate `platform_adapters` properly; build one-off adapters only where a jurisdiction is on a different
  vendor.
- **Phase 3 — Semantic layer**: embedding pipeline stage, `topics` taxonomy, `semantic_search` tool, topic
  trend UI resource.
- **Phase 4 — Agentic layer & rate limiting hardening**: wire up `deepagents` + `langchain-mcp-adapters` against
  our own MCP tools, ship the `ask_agent` tool and its minimal chat affordance in the frontend (§8); stand up
  the tiered rate limiter and the `agent_usage_daily` budget guard (§9) before this tool is reachable publicly.
- **Phase 5 — Geographic expansion**: additional CA counties/cities, proving the adapter-reuse payoff.
- **Phase 6 — State & federal**: California legislature, then U.S. Congress.
- **Phase 7+**: agent-assisted onboarding (`propose_new_jurisdiction`, now safely admin-gated), accounts/
  watchlists/alerts, real hosting/deployment behind a CDN/WAF (upgrading the rate limiter to a shared store at
  the same time), auto-discovered topics via clustering.

## 14. Non-Goals for v1

- No user accounts, auth, or personalization.
- No state/federal data (Phase 6+).
- No public write features (comments, petitions, etc.) — read-only civic data.
- No mobile app — responsive web only.
- No paid embedding/LLM API dependency for the core ingestion/search pipeline (the agentic layer is the one
  deliberate exception, and it's budget-capped — see §8–9).
- No "bring your own API key" mode in v1 — `ask_agent` always uses our server-held key, budget-capped for
  everyone. BYOK is a possible later power-user addition, not a v1 requirement.

## 15. Open Questions (revisit as we build)

- Exact chunking strategy for embeddings (size/overlap) — decide during Phase 3 against real ingested text.
- ~~Whether `boundary` geometries come from US Census TIGER/Line shapefiles or another authoritative source~~
  — **decided (2026-07-06): US Census TIGER/Line shapefiles**, loaded for Novato + Marin County for the MVP
  scope; revisit only if TIGER/Line proves insufficient (e.g. missing/inaccurate boundaries) when expanding
  to the rest of Marin's cities/towns in Phase 2.
- Long-term hosting target (Phase 7+) — deferred per the local/dev-first decision, but real hosting must bring
  CDN/WAF-level DDoS protection and a shared (Redis) rate-limit store, not just app-level limiting (§9).
- Whether/when to add Atlas Automated Embedding as an alternative `EmbeddingProvider` once it exits Public
  Preview.
- Exact v1 numeric rate-limit/budget values in §9 are starting defaults — tune against real usage once
  `ask_agent` ships in Phase 4.
- Whether MCP's experimental "tasks"/streaming primitives are mature enough by Phase 4 to give `ask_agent`
  incremental output instead of request/response.

## 16. Proposed Repo Structure (for the next step, not yet created)

```
what-the-rep/
  MASTER_PLAN.md
  README.md
  backend/
    mcp_server/        # FastMCP app: tools, ui:// resources, prompts
      middleware/        # rate_limiter.py, budget_guard.py (§9)
    agent/              # deepagents setup, MultiServerMCPClient config, ask_agent tool (§8)
    ingestion/
      adapters/         # base.py, granicus.py, legistar.py, civicclerk.py, ...
      pipeline/          # discover.py, fetch.py, parse.py, normalize.py, resolve.py, embed.py, store.py, link.py
      registry/          # platform detection + jurisdiction seed data
    db/
      models/            # Pydantic schemas mirroring §5, incl. agent_usage_daily
    embeddings/          # local embedding model wrapper (EmbeddingProvider interface)
    tests/
    pyproject.toml      # dependencies managed with uv; uv.lock committed alongside
  frontend/
    src/
      mcp-client/        # MCP Streamable HTTP client wrapper
      ui-resources-host/ # AppRenderer + sandbox proxy integration
      components/
      pages/             # Home, Jurisdiction, Meeting, Official, Topic, Search
      agent-chat/         # minimal ask_agent chat affordance
    package.json
  scripts/
    seed_marin.py        # bootstrap the 13 Phase-1 jurisdiction stubs
  docker-compose.yml      # backend + frontend for local dev (Mongo stays on Atlas)
  .env.example             # ANTHROPIC_API_KEY, rate-limit tuning vars, etc.
```
