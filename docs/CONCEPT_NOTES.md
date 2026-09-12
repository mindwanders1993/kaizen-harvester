# Kaizen Harvester — Concept Notes

_Drafted 2026-09-12. One workspace monorepo, three independent sub-projects._
_Supersedes the single-pipeline design in `~/.claude/plans/hi-what-are-skills-foamy-waffle.md`
(the 2026-09-11 design discussion log), which remains the reference for agentic patterns, provider
configuration and the framework evaluation._

---

## 0. Programme overview

**Goal.** A GitHub universal scraper: index anything publicly available on GitHub — interview and
practice material (SQL, Python, DevOps, AWS, GCP, Azure, data science, ML, mathematics), open-source
datasets (cricket, football, COVID), books, courses, learning resources — then ingest selected parts
into a knowledge archive, then generate usable artifacts from that archive on demand.

**Three sub-projects, each end-to-end and independently shippable:**

| | Project | Consumes | Produces | Dominant cost |
|---|---|---|---|---|
| **P1** | GitHub Knowledge Map | GitHub API | scored, human-curated repo map | GitHub API quota |
| **P2** | Ingestion → Archive | repo selections from P1 | knowledge archive | LLM tokens |
| **P3** | Domain Generator Agents | the archive | questions, datasets, artifacts | verification compute |

They have different bottlenecks, which is why they are separate. P1 is metadata-bound and almost
entirely free of LLM cost. P2 is clone-, disk- and LLM-bound. P3 is retrieval- and sandbox-bound.
Fused into one pipeline, the whole thing would move at the speed of the slowest stage.

### Repository shape

```
kaizen-harvester/
├── packages/                  # shared internal libs
│   ├── gh-client/             # search, GraphQL batch, clone, per-endpoint rate limits
│   ├── llm-gateway/           # OpenAI-compatible router: Gemini/OpenRouter/ExpLabs/Ollama
│   └── contracts/             # Pydantic models passed BETWEEN projects
├── projects/
│   ├── p1-map/
│   ├── p2-ingest/
│   └── p3-generate/
│       ├── core/              # retrieval, composition, formatting
│       ├── sql-agent/         ├── python-agent/
│       └── scala-agent/       └── spark-agent/
└── pyproject.toml             # uv workspace root
```

`uv` workspace: one lockfile, per-project dependency sets. `sql-agent` never installs a JVM;
`p1-map` never installs Spark.

### The separation rule

**Each project owns its own database schema, and no project ever SELECTs from another's tables.**
P2 consumes P1 through `packages/contracts` — a published export or read-only view, never a join.
Break this once and the monorepo silently collapses back into one application.

### Cross-cutting concerns (all three)

- **Provenance chain.** `repo → commit SHA → file path → document → knowledge unit → generated
  artifact`. Every link stored. Without the commit SHA, nothing downstream is reproducible.
- **License propagation.** "Publicly available" is not "freely usable". Unlicensed repos are
  all-rights-reserved by default; data repos frequently republish upstream data under its own terms.
  P3 produces derivative works, which is where this bites. Carry the license on every repo,
  document, unit and dataset, and let P3 filter on redistributability. Cheap now, painful later.
- **LLM gateway.** All available providers are OpenAI-compatible (Gemini shim, OpenRouter,
  Experiential Labs, Ollama), so one adapter serves all four. No Anthropic or OpenAI key exists —
  which is why the current code has never made a real LLM call.
- **Budget.** Per-run token and dollar ledger; free tiers (Gemini, Ollama) first, paid on fallback.

---

# Project 1 — GitHub Knowledge Map

### Purpose

Answer *"where is the good material for X on GitHub?"* — and let a human correct the answer —
**before any content is pulled**. P1 is a map, not a scraper: it stores metadata and judgement, never
file contents.

### The constraint that defines this project

Verified live against the GitHub API on 2026-09-12:

| Probe | Result |
|---|---|
| `search/repositories?q=sql` | `total_count: 1,422,028` |
| Requesting result 1001 | `"Only the first 1000 search results are available"` |
| Rate limits (current token) | **search 30/min · code search 10/min** · core 5000/hr · GraphQL 5000/hr |
| `/repositories?since=` | Enumerates by repo id from `mojombo/grit`, unfiltered — not viable |

**You cannot enumerate GitHub. You can only enumerate slices of ≤1000.** So P1's core intelligence is
*query planning*: expand a topic into many facet queries whose union approximates coverage, and
recursively partition any query still reporting more than 1000 results.

Partition axes: star ranges (`stars:>1000`, `stars:200..999`, `stars:50..199` …, subdividing until
each leaf is ≤1000), then `language:`, `topic:`, `in:name`, and `pushed:` windows. This is
deterministic and costs zero tokens. The LLM is needed only for topic expansion.

### Internal architecture

| Component | Type | Role |
|---|---|---|
| **Topic Expander** | LLM | `"SQL"` → synonyms, GitHub topics, adjacent terms (`sql-interview`, `dbms`, `tsql`, `postgresql`). The only LLM-heavy part of P1 |
| **Query Planner** | deterministic | Builds facet queries; recursive star-range partitioning driven by each query's `total_count` |
| **Discovery Workers** | parallel, rate-limited | Execute searches; one token bucket per endpoint class |
| **Enricher** | GraphQL batch | Full metadata ~100 repos/request against the 5000/hr budget — the difference between mapping thousands and hundreds of repos per hour |
| **Scorer** | deterministic | Weighted KPIs; **every component stored, not just the total** |
| **AI Verifier Agent** | LLM | **Mandatory.** Inspects tree & README; emits verdict (VERIFIED/REJECTED), content kind, and P2 extraction strategy hint |
| **Curator (Supervisor)**| human (optional) | Inspect, pin, blacklist, re-tag, or override verdicts via UI/CLI without blocking pipeline |

_For the detailed P1 architecture, see [docs/P1_CONCEPT_NOTES.md](file:///Users/mrrobot/Desktop/Projects/kaizen-harvester/docs/P1_CONCEPT_NOTES.md)._

### Scoring KPIs

Stars · star velocity (stars ÷ repo age) · `pushed_at` recency · contributor count · fork ratio ·
open/closed issue ratio · README size · topic and description match · file-type mix (signals data vs
docs vs code) · license presence and permissiveness. Forks and archived repos excluded by default.

Storing each component separately is what makes the ranking *arguable* — the user can see why a repo
placed where it did, and override it with reason.

### Data model

`repos` · `topics` · `repo_topics` · `repo_scores` (component-level) · `agent_verifications` · `discovery_runs` ·
`user_overrides`. Overrides are a separate table so human judgement survives every re-scoring run and
is never clobbered by a later discovery pass.

### Human-in-the-loop (Optional Supervisory Layer)

Human verification is optional: the pipeline operates autonomously end-to-end. Curators can review
rankings, pin favorites, blacklist noise, or override agent verdicts. This is the project's primary
curation interface and the place a web dashboard is justified.

### Output contract

The curated map: repo identity, metadata, license, topics, score with components, human status
(kept/removed/pinned), and `discovered_at`. This is what P2 consumes.

### Exit gate

1. For one topic, the union of partitioned queries returns materially more distinct repos than a
   single unpartitioned query capped at 1000.
2. A discovery run completes without a 403, with licenses and topics populated.
3. Human edits survive a re-run of the same topic.
4. The top of a ranking is defensible by eye.

### Risks

Broad topics burn search quota (30/min is the real ceiling on breadth) · star-weighted scoring biases
toward popular-but-stale repos, which is why velocity and recency matter · topic taxonomy drifts as
the map grows · GitHub search relevance is opaque and not reproducible over time.

---

# Project 2 — Ingestion → Knowledge Archive

### Purpose

Turn selected repos into structured, verified, categorized knowledge. Input: repo selections from
P1's map. Output: the archive that P3 draws on.

### The central design fact: content-type routing

This is what makes the scraper *universal*, and it is where v1 was structurally stuck: a
`content: str` artifact field plus `read_text()` assume every artifact is UTF-8 text small enough to
fit in a prompt. Cricket, football and COVID repos are parquet and multi-gigabyte CSV. Routing must
exist before the first artifact record is written, because retrofitting it reworks every schema
downstream.

| Content type | Handling | Reaches an LLM? |
|---|---|---|
| Text knowledge — md, ipynb, sql, code | LLM extraction → knowledge units | yes |
| Tabular data — csv, parquet, json, xlsx | **DuckDB profiling**: schema, row count, column stats, sample rows | **no** |
| Documents — pdf, docx | markitdown / docling → text, or catalog-only | sometimes |
| Media and binaries | catalog only | no |

### Internal architecture

| Component | Type | Role |
|---|---|---|
| **Repo Mapper** | ReAct agent | Shallow clone, walk tree, classify *layout* — one-file-per-question, notebook course, data dump, awesome-list — and emit an extraction strategy |
| **Router** | deterministic | File → pipeline, by type and size |
| **Extractor** | LLM | Text → knowledge units. **Must fan out**: one README yields N units, not one |
| **Profiler** | deterministic (DuckDB) | Data files → schema, stats, samples |
| **Categorizer** | LLM | Unit → higher-level category taxonomy |
| **Verifier** | per content type | SQL executes; code runs; claims grounded against source |
| **Deduplicator** | hash + embedding | Exact via content hash, near via vector |
| **Archivist** | deterministic | Draft → commit, only after verification and guards |

### The fan-out requirement

v1's extractor returned a single record per file. Target sources are READMEs holding hundreds of
questions each, so each yielded exactly one item. This is the single biggest ceiling on the archive
and must be fixed as a splitter stage, not a tweak.

**Proposed shape — a two-pass extractor, where the second pass _is_ the fan-out**
_(design note, 2026-09-12. Not active: P2 waits for P1 Stage 2 and ~100 read verdicts.)_

1. **Segment — deterministic.** Split on structural boundaries detectable for free: markdown headers,
   numbered lists, `## Question N` patterns, code fences. Same principle as P1's Structure component —
   cheap signals before expensive ones. A source with *no* repeating structural marker is itself a
   signal about content kind.
2. **Extract — LLM, per segment not per file.** Schema returns `list[KnowledgeUnit]`, never
   `KnowledgeUnit`. Pydantic then forces the fan-out at the type level; an ad-hoc dict return can
   silently collapse to one record, a list-typed signature cannot.

Don't hand-roll the segmenter — `markdown-it-py` (AST) or `unstructured` already chunk hierarchical
documents. Principle 1.

**Deliberately not in the MVP:** confidence thresholds, retry-on-empty-fanout, near-duplicate
collapsing. Chunk on headers, one call per chunk, list-typed output. Fix it when a real repo shows
the fan-out is wrong.

**Open:** the no-structure fallback — one unbroken 10,000-line README with no headers breaks pass 1
entirely. Decide when P2 design actually starts.

### Data model

`documents` (parsed text + provenance) · `knowledge_units` (question, practice rule, code pattern,
concept) · `datasets` (schema, stats, file manifest — no contents) · `categories` ·
`ingestion_runs`. Every row carries `repo`, `commit_sha`, `path`, `license`, `content_hash`.

### Exit gate

1. A fixture repo produces N unique verified knowledge units; re-running adds zero.
2. A data repo produces a dataset catalog entry with real schema and stats, and **zero bytes of it
   reach an LLM prompt**.
3. Every stored unit traces back to repo + commit SHA + path + license.

### Risks

Extraction quality varies wildly by repo layout · LLM cost is the dominant cost and scales with repo
size · licence contamination enters here and surfaces in P3 · large clones consume disk fast.

---

# Project 3 — Domain Generator Agents

### Purpose

Produce usable artifacts on demand from the archive: *"create 10 hard SQL questions for
KaizenCodes"*, *"create Python questions"*. Not one generator — a **family** of per-domain agents:
`sql-agent`, `python-agent`, `scala-agent`, `spark-agent`, with more to follow.

### What actually separates them

Not the prompting — retrieval, composition, formatting and LLM routing are identical across all
four. It is the **verification runtime**, and that difference is heavy:

| Agent | Verification | Weight |
|---|---|---|
| SQL | DuckDB in-process | light, no container |
| Python | pytest in a sandbox | medium |
| Scala | scalac / sbt | heavy — JVM, slow compiles |
| Spark | spark-submit | heaviest — JVM + Spark runtime |

**Shape: one shared core, N thin deployables**, each with its own verifier and sandbox image. Adding
`rust-agent` later is then a new verifier, not a new codebase. This keeps a retrieval bug fixed in
one place while ensuring `sql-agent` never drags in a JVM.

### Internal architecture (per agent)

| Component | Shared or per-domain | Role |
|---|---|---|
| **Request Interpreter** | shared | NL request → spec: count, difficulty, topics, output format |
| **Retriever** | shared | Archive query + semantic search → candidate source units |
| **Composer** | shared | Draft items grounded in retrieved units |
| **Verifier** | **per-domain** | Execute, compile or test in the domain runtime |
| **Corrector** | shared, bounded | Self-correction loop on verification failure, max 2–3 rounds |
| **Novelty check** | shared | Do not regenerate what the target already contains |
| **Formatter** | **per-domain** | Emit in target schema (KaizenCodes, JSONL, markdown) |

### Exit gate

A request yields N items, every one passing its domain verifier, every one provenance-linked to
archive units, and none duplicating content already in the target.

### Risks

**Generation vs reproduction** — if the composer copies a source question nearly verbatim, the
licence of the source repo governs the output; novelty checking is a legal control, not just a
quality one · verification depth is shallow by nature (it compiles ≠ it is correct) · JVM sandboxes
are slow enough to shape the UX for Scala and Spark.

---

## Next step

Deep dive on **Project 1** — query planner design, scoring model, data model, and the human curation
surface.

### Assumptions carried in (correct any that are wrong)

1. ~~Existing `core/agents/` + `core/memory/` becomes the seed of **p2-ingest**~~ — **overtaken by
   events, 2026-09-12.** v1 was deleted rather than harvested for parts; it had never made a real
   model call, so there was nothing proven to seed from. Every project is now new code. The repo
   keeps its name and is the `uv` workspace root.
2. One web UI, scoped to P1 map editing. **Superseded:** Datasette over the SQLite file is the
   curation UI — see `P1_ARCHITECTURE.md` §7. Do not write a UI.
3. Postgres for P1 (the map is edited from a UI while discovery runs in background — the concurrent
   writer case DuckDB cannot serve). **Deferred:** SQLite until something actually writes
   concurrently with the crawler (§8 stage triggers). DuckDB retained for P2 data profiling.
4. Build order P1 → P2 → P3. **Holds.**

### Still open from the earlier design doc

Orchestration framework (LangGraph + PydanticAI vs PydanticAI + DBOS) — not needed until P2 ·
per-run budget defaults · the KaizenCodes skills side-track.
