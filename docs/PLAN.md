# 🏗️ Kaizen Harvester: Master Implementation Plan

> **Engineering Principles Embedded Throughout:**
> - **Karpathy**: Simplicity First. No orchestration frameworks (no LangChain, no CrewAI). Native Python + Pydantic + official SDKs only.
> - **Loop Engineering**: Every phase concludes with a mandatory `Build → Test → Reflect` gate before progression.
> - **REACT (Reason + Act)**: Every LLM-powered agent emits explicit `reasoning` before emitting `action` data.
> - **Harness Engineering**: Test harnesses (mocks, fixtures, sandboxes) are built **before** core logic in each phase.

---

## 📊 System Overview

```
kaizen-harvester/
├── cli.py                          # CLI Orchestrator (Rich UI, async pipeline runner)
├── core/
│   ├── schemas.py                  # Pydantic data contracts (all cross-boundary types)
│   ├── ingress/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseFetcher protocol
│   │   ├── github.py               # GitHub Search + Shallow Clone
│   │   ├── web.py                  # Web/URL fetcher (aiohttp)
│   │   └── rate_limiter.py         # Token Bucket + exponential backoff
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseAgent interface + LLM client factory
│   │   ├── scout.py                # Scout Agent: heuristic + LLM triage
│   │   ├── extractor.py            # Extractor Agent: LLM schema extraction
│   │   ├── curator.py              # Curator Agent: DuckDB sandbox + difficulty rating
│   │   └── prompts/
│   │       ├── scout_system.txt    # Scout system prompt (REACT style)
│   │       ├── extractor_system.txt
│   │       └── curator_system.txt
│   └── memory/
│       ├── __init__.py
│       ├── duckdb_store.py         # Relational vault: init, insert, query, export
│       └── lancedb_store.py        # Vector memory: embed, dedup, store
├── recipes/
│   └── sql_challenges.yaml
├── storage/
│   ├── lancedb/                    # LanceDB vector table files (auto-created)
│   └── vault.duckdb                # DuckDB relational catalog (auto-created)
├── tests/
│   ├── conftest.py                 # Fixtures, mock LLM clients, DuckDB :memory:
│   ├── mock_data/
│   │   ├── sample_sql.sql          # Test SQL file artifact
│   │   ├── sample_md.md            # Test Markdown artifact
│   │   └── sample_nb.ipynb         # Test Jupyter Notebook artifact
│   ├── test_schemas.py
│   ├── test_ingress.py
│   ├── test_agents.py
│   └── test_memory.py
└── docs/
    ├── HLD.md
    ├── LLD.md
    └── PLAN.md                     # This document
```

---

## 🔗 Phase Dependency Chain

```
Phase 1 (Schemas + Harness)
    ↓
Phase 2 (Memory Vault)
    ↓
Phase 3 (Agent Swarm)
    ↓
Phase 4 (Ingress Mesh)
    ↓
Phase 5 (CLI Orchestrator)
    ↓
Phase 6 (Integration + End-to-End)
```

**Each phase is independently testable and has its own exit gate.**

---

## Phase 1: Core Schemas + Harness Engineering

**Objective**: Define all cross-boundary data contracts and build the test fixtures/mocks before any logic is written. This is the foundation every other module depends on.

### Harness Engineering First

Before writing logic in any subsequent phase, `tests/conftest.py` must have:

1. **Mock LLM Client** — a `MockLLMClient` that returns deterministic JSON fixtures for Scout, Extractor, and Curator calls without touching any real API.
2. **DuckDB `:memory:` Fixture** — a `test_db` pytest fixture that creates a fresh in-memory DuckDB store per test.
3. **Mock Artifact Fixtures** — `RawArtifact` instances loaded from `tests/mock_data/` files.
4. **Mock GitHub Responses** — pre-recorded API response JSON fixtures (to avoid live network calls in CI).

### Module: `core/schemas.py`

All data exchanged between modules is validated through Pydantic. No raw dicts across boundaries.

```
HarvestRecipe       ← Loaded from recipes/*.yaml
RawArtifact         ← Output of Ingress Mesh (per file)
ScoutResult         ← Output of Scout Agent (per RawArtifact)
ExtractedRecord     ← Output of Extractor Agent (per RawArtifact)
CuratedRecord       ← Output of Curator Agent (per ExtractedRecord)
VaultRecord         ← What gets persisted in DuckDB
HarvestRunStats     ← Telemetry for CLI stats display
```

Key design decisions:
- `ScoutResult` includes a `reasoning: str` field (REACT principle — explicit chain-of-thought before decision).
- `ExtractedRecord.data` is typed as `Dict[str, Any]` and validated against the recipe's `target_schema` at runtime.
- `CuratedRecord` carries `sandbox_output: str` (the DuckDB query result preview) and `retry_count: int`.

### Phase 1 Exit Gate
```bash
source venv/bin/activate
ruff check --fix . && ruff format .
pytest tests/test_schemas.py -v
# Expected: All schema validation tests pass
```

---

## Phase 2: Memory & Vault Layer

**Objective**: Build the persistence and deduplication layer before the agents need it. Agents must have somewhere to write validated data. Memory is built first, not last.

### Module: `core/memory/duckdb_store.py`

**Responsibilities**:
- `init_db(path: str)` — Creates `storage/vault.duckdb` and runs DDL migrations.
- `insert_challenge(record: CuratedRecord)` — Upserts a record into the `challenges` table.
- `merge_source(record_id: str, source_url: str)` — Appends a new source to `source_urls[]` (duplicate merge).
- `get_stats() -> HarvestRunStats` — Returns count breakdown by difficulty and dialect.
- `export_jsonl(output_path: str)` — Runs `COPY challenges TO output_path (FORMAT JSON)`.

**Full DuckDB Schema**:
```sql
CREATE TABLE IF NOT EXISTS challenges (
    id          VARCHAR PRIMARY KEY,        -- UUID as string
    domain      VARCHAR NOT NULL,
    title       VARCHAR NOT NULL,
    problem_statement TEXT NOT NULL,
    setup_ddl   TEXT,
    solution_sql TEXT,
    difficulty  VARCHAR CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    dialect     VARCHAR,
    category    VARCHAR,
    tags        VARCHAR[],
    source_urls VARCHAR[],
    sandbox_output  TEXT,                   -- Preview of DuckDB execution result
    quality_score   FLOAT,
    retry_count     INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS harvest_runs (
    run_id      VARCHAR PRIMARY KEY,
    recipe_name VARCHAR,
    started_at  TIMESTAMP,
    completed_at TIMESTAMP,
    total_scanned   INTEGER DEFAULT 0,
    total_extracted INTEGER DEFAULT 0,
    total_deduped   INTEGER DEFAULT 0,
    total_saved     INTEGER DEFAULT 0,
    status      VARCHAR DEFAULT 'running'
);
```

### Module: `core/memory/lancedb_store.py`

**Responsibilities**:
- `init_table(path: str)` — Connects to `storage/lancedb/` and creates the `challenges` vector table.
- `embed_text(text: str) -> List[float]` — Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dims). Runs locally on CPU.
- `is_duplicate(vector: List[float], threshold: float = 0.15) -> tuple[bool, str | None]` — Returns `(True, existing_id)` if a near-match is found.
- `add_record(record_id: str, vector: List[float], source_url: str)` — Adds to the vector table.

**Deduplication Logic**:
```
cosine_distance < 0.15  → Exact/near-exact duplicate  → Reject, merge source attribution
cosine_distance 0.15–0.35 → Related variation          → Flag for human review
cosine_distance > 0.35  → Novel record                 → Approved for insertion
```

### Phase 2 Exit Gate
```bash
pytest tests/test_memory.py -v
# Tests: init_db creates tables, insert_challenge stores and retrieves,
#        is_duplicate returns True for identical strings,
#        is_duplicate returns False for completely different strings
```

---

## Phase 3: Agent Swarm

**Objective**: Build the three-agent intelligence pipeline. Each agent uses REACT-style prompting (explicit Reasoning step before the Action output). Agents use native SDKs only — no frameworks.

### Design: Agent Concurrency Model

```
Pipeline per file:
  Scout(artifact) → [if approved] → Extractor(artifact) → Curator(extracted)
  
Outer concurrency:
  asyncio.Semaphore(10) bounds concurrent file processing
  → Prevents rate limit exhaustion on LLM APIs
  → Prevents memory exhaustion on LanceDB embedding calls
```

### Module: `core/agents/base.py`

**LLM Client Factory** — selects provider based on env vars:
```python
def get_llm_client():
    if os.getenv("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    return openai.OpenAI()


def llm_structured_call(client, system: str, user: str, response_model: type[BaseModel]) -> BaseModel:
    """Wraps provider-specific structured output calls into a unified interface."""
```

### Module: `core/agents/scout.py`

**Strategy**: Two-stage — fast heuristics first (zero LLM cost), then LLM reasoning for ambiguous cases only.

**Stage 1 — Heuristics (deterministic, no LLM)**:
- REJECT: path contains `node_modules`, `vendor`, `.github`, `dist/`
- REJECT: filename in `{LICENSE, CHANGELOG, package.json, tsconfig.json, .gitignore}`
- REJECT: file size > 100KB (avoids context window overflow)
- CANDIDATE: extension in `{.sql, .md, .ipynb}` AND file contains SQL keywords (`SELECT`, `CREATE TABLE`, `INSERT`)
- AMBIGUOUS: everything else → send to LLM

**Stage 2 — LLM REACT Triage (ambiguous files only)**:

System prompt pattern (`prompts/scout_system.txt`):
```
You are the Scout Agent for Kaizen Harvester.

Your job is to evaluate if a raw file contains a valid technical challenge
for the domain: {domain}.

Reason step-by-step:
1. What does the file path suggest?
2. Does the content contain a problem statement, SQL DDL, or solution code?
3. Is this content original challenge material or boilerplate/config?

Respond ONLY with valid JSON matching this schema:
{
  "reasoning": "<your chain-of-thought>",
  "is_candidate": true | false,
  "confidence": 0.0–1.0,
  "primary_format": "markdown" | "sql" | "jupyter" | "code"
}
```

**Cost Optimization**: Only the first 1,500 characters of file content are sent to the LLM.

### Module: `core/agents/extractor.py`

**Strategy**: Dynamic schema injection. The recipe's `target_schema` is converted into a JSON schema and injected into the prompt at runtime. This makes Extractor **domain-agnostic**.

System prompt pattern (`prompts/extractor_system.txt`):
```
You are the Extractor Agent for Kaizen Harvester.

Your job is to parse raw unstructured content and extract structured data
matching the target schema below EXACTLY.

Target Schema:
{target_schema_json}

Rules:
- Separate setup DDL (CREATE TABLE, INSERT INTO) from solution SQL (SELECT...).
- The problem_statement must be self-contained markdown.
- If a field cannot be found, set it to null. Do not hallucinate values.

Reason step-by-step before extracting:
1. What format is this content? (markdown, sql file, notebook cell)
2. Where is the problem description?
3. Where is the DDL setup vs. the solution query?

Respond ONLY with valid JSON matching the schema.
```

**Notebook Preprocessing**: Before passing to LLM, `.ipynb` files are parsed to extract only `cell.source` arrays (strips outputs, base64 images, execution counts). This can reduce context from 200KB to under 10KB.

### Module: `core/agents/curator.py`

This is the **Loop Engineering** core. It implements the `Execute → Verify → Self-Correct` inner loop.

```
Input: ExtractedRecord
Loop (max 3 iterations):
    1. VALIDATE schema fields (required keys present, enums valid)
    2. EXECUTE setup_ddl + solution_sql in DuckDB :memory: sandbox
    3. If PASS:
         - Assign difficulty, dialect, quality_score
         - Capture sandbox_output (first 10 rows)
         - Return CuratedRecord
    4. If FAIL:
         - Capture duckdb.Error trace
         - Send error + original content back to Extractor for correction
         - Increment retry_count
    5. If retry_count >= 3: Mark as FAILED, log, skip
```

**DuckDB Sandbox Safety**:
- Wraps solution in `SELECT * FROM (...) LIMIT 10` to prevent memory exhaustion.
- Blocks dangerous keywords: `ATTACH`, `COPY`, `INSTALL`, `LOAD`, `PRAGMA`.
- Runs in subprocess isolation if `SAFE_SANDBOX=true` env is set.

**Difficulty Classification Logic** (heuristic, no LLM cost):
```python
def classify_difficulty(sql: str) -> str:
    sql_upper = sql.upper()
    hard_patterns = ["ROW_NUMBER", "RANK(", "DENSE_RANK", "LAG(", "LEAD(", "RECURSIVE", "QUALIFY"]
    medium_patterns = ["WITH ", "LEFT JOIN", "DATE_TRUNC", "CASE WHEN"]
    if any(p in sql_upper for p in hard_patterns):
        return "Hard"
    if any(p in sql_upper for p in medium_patterns):
        return "Medium"
    return "Easy"
```

### Phase 3 Exit Gate
```bash
pytest tests/test_agents.py -v
# Tests:
#   Scout correctly rejects LICENSE files and config files
#   Scout correctly approves sample_sql.sql and sample_md.md
#   Extractor correctly maps content to target_schema fields (uses MockLLMClient)
#   Curator PASSES valid SQL, FAILS invalid SQL, retries and self-corrects
```

---

## Phase 4: Ingress Mesh

**Objective**: Build the collectors. The ingress mesh is the only module that touches external networks.

### Module: `core/ingress/rate_limiter.py`

**Token Bucket** implementation:
- `capacity`: max tokens (default: 10 for GitHub API bursts)
- `refill_rate`: tokens per second (default: 1.38 for 5,000/hr authenticated)
- `async consume(tokens=1)`: waits if bucket is empty
- Handles `403 x-ratelimit-reset` header → sleeps until reset timestamp

### Module: `core/ingress/github.py`

**GithubFetcher** class:

```
search_repositories(query: str, min_stars: int) -> List[RepoMeta]
    → GET https://api.github.com/search/repositories?q={query}+stars:>{min_stars}
    → Paginates using Link header until all results fetched

clone_and_extract(repo_url: str, filters: dict) -> AsyncGenerator[RawArtifact]:
    → git clone --depth 1 --filter=blob:none {url} {tmp_dir}
    → Walk tmp_dir for files matching filters.file_patterns
    → Skip files matching filters.exclude_paths
    → Yield RawArtifact per file
    → Cleanup tmp_dir after all artifacts yielded
```

**File Format Detection**:
```python
def detect_format(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {"sql": "sql", ".md": "markdown", ".ipynb": "jupyter"}.get(ext, "code")
```

### Module: `core/ingress/web.py`

`WebFetcher` — Simple `aiohttp` client for fetching web-based resources:
- Fetches raw URLs and treats the response body as a markdown artifact.
- Used for documentation pages or external problem sets.

### Phase 4 Exit Gate
```bash
pytest tests/test_ingress.py -v
# Tests:
#   RateLimiter delays correctly under mock clock (no real sleep)
#   GithubFetcher parses mock API response and yields correct RepoMeta objects
#   clone_and_extract yields RawArtifacts from a mock local repo directory
```

---

## Phase 5: CLI Orchestrator

**Objective**: Wire the pipeline together. Replace all `TODO` stubs in `cli.py` with real pipeline execution and Rich progress bars.

### `cli.py` Pipeline Architecture

```
cli.py run
    ↓
load_recipe(recipe_path) → HarvestRecipe
    ↓
display_harvest_plan(recipe)          # Already implemented
    ↓
asyncio.run(run_pipeline(recipe))
    ├── GithubFetcher yields RawArtifacts
    ├── asyncio.Semaphore(10) bounds concurrency
    └── Per artifact:
        ├── scout.triage(artifact)
        ├── [if approved] extractor.extract(artifact, recipe.target_schema)
        ├── [if extracted] curator.curate(extracted)
        ├── [if curated] lancedb.is_duplicate(vector)
        └── [if unique] duckdb.insert_challenge(record)
    ↓
display_run_summary(stats)
```

**Rich Progress Bar** setup:
```python
with Progress(
    SpinnerColumn(),
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Harvesting...", total=total_files)
    # Update inside pipeline loop
```

### Phase 5 Exit Gate
```bash
python cli.py run --recipe recipes/sql_challenges.yaml
# Confirm: Rich progress bar renders without crashing
# Confirm: Pipeline wires correctly with agents and memory
```

---

## Phase 6: Integration + End-to-End Validation

**Objective**: Full pipeline smoke test against a real (small) GitHub repository.

### Integration Test Plan
1. Pick one small, stable GitHub repo from `docs/knowledge_base/repo_catalog.md` (e.g., `faizanxmulla/sql-portfolio`).
2. Run: `python cli.py run --recipe recipes/sql_challenges.yaml --limit 3`
3. Verify:
   - `python cli.py stats` shows `DuckDB: 3 records` (or fewer if duplicates found).
   - `storage/vault.duckdb` exists and is queryable.
   - `storage/lancedb/` directory is populated with vector data.
4. Run: `python cli.py run --recipe recipes/sql_challenges.yaml --limit 3` again.
5. Verify: `stats` shows same count (LanceDB correctly deduplicated repeated run).

### Automated Verification
```bash
source venv/bin/activate
ruff check --fix . && ruff format .
pytest -v --tb=short
python cli.py stats
```

---

## 📦 Dependency Management

All dependencies are already in `requirements.txt`. For development and testing, add:

```
# Testing
pytest
pytest-asyncio
pytest-mock
ruff

# Dev only (not production)
black  # optional, ruff format handles this
```

No additional runtime dependencies are needed. The plan uses only:
- `openai` / `anthropic` (already in requirements)
- `lancedb` + `sentence-transformers` (already in requirements)
- `duckdb` (already in requirements)
- `pyyaml`, `rich`, `aiohttp` (already in requirements)

---

## 🚦 Master Phase Checklist

| Phase | Deliverables | Exit Gate Command | Status |
|:---|:---|:---|:---|
| **1** | `core/schemas.py`, `tests/conftest.py`, `tests/mock_data/` | `pytest tests/test_schemas.py -v` | ✅ Completed |
| **2** | `core/memory/duckdb_store.py`, `core/memory/lancedb_store.py` | `pytest tests/test_memory.py -v` | ✅ Completed |
| **3** | `core/agents/scout.py`, `extractor.py`, `curator.py`, `prompts/` | `pytest tests/test_agents.py -v` | ✅ Completed |
| **4** | `core/ingress/rate_limiter.py`, `github.py`, `web.py` | `pytest tests/test_ingress.py -v` | ✅ Completed |
| **5** | `cli.py` (full pipeline wired) | `python cli.py run --recipe ... --limit 3` | ⬜ Pending |
| **6** | End-to-end integration with real GitHub repo | `pytest -v && python cli.py stats` | ⬜ Pending |
