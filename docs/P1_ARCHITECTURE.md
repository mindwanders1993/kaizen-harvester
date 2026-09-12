# Project 1 — GitHub Knowledge Map
## High-Level Architecture

_Version 1.0 · 2026-09-12 · Status: ready to build_
_Derived from a 7-round Claude↔Gemini design debate and a 6-seat, 4-lineage round-table review._

---

## 1. What P1 is

> P1 answers **"which GitHub repos are worth harvesting for topic X?"** — and lets a human correct
> the answer — **before a single repository is cloned.**

It is a **librarian building a card catalogue**, not a truck moving books. Project 2 is the truck.

| | |
|---|---|
| **Consumes** | GitHub Search API, GraphQL API, Git Trees API |
| **Produces** | A scored, machine-verified, human-curated repo map |
| **Never does** | Clone repos · download data files · store code · extract content |
| **Binding constraint** | GitHub API quotas |

---

## 2. Scope boundary

| In scope (P1) | Out of scope (P2 / P3) |
|---|---|
| Finding repos by topic | Cloning repos |
| Metadata enrichment | Parsing file contents |
| Scoring and ranking | Extracting knowledge units |
| Judging *"is this real material?"* | Judging *"is this question good?"* |
| Human curation of the map | Profiling datasets |
| Exporting a selection list | Generating anything |

**The hard rule:** P1 reads two small files per repo — the file tree and the README. Nothing else.
If you find yourself wanting a third, that's P2's job.

---

## 3. The constraint that shapes everything

Verified live against the GitHub API:

| Probe | Result |
|---|---|
| `search/repositories?q=sql` | `total_count: 1,422,028` |
| Requesting result #1001 | `"Only the first 1000 search results are available"` |
| Search rate limit | **30 requests / minute** |
| Core REST (trees, readme, repos) | **5,000 requests / hour** |
| GraphQL | 5,000 points / hour (~1–2 points per 100-repo batch) |

Two consequences drive the entire design:

1. **You cannot enumerate GitHub. You can only enumerate slices of ≤1000.**
   → hence the Query Planner.
2. **Discovery (≈60k repos/hr) massively outruns inspection (5,000 repos/hr).**
   → hence the Gate. It is a throughput valve, not an optimisation.

---

## 4. Design principles

1. **Don't reinvent the wheel.** Before writing a component, ask: *what is the smallest thing I can
   call instead?* Write code only where nobody has solved this exact problem.
2. **Metadata before content.** Spend cheap signals first, expensive ones last.
3. **Deterministic by default; an LLM only where judgement is genuinely required.** Counting `.ipynb`
   files is not judgement. Deciding "is this a real question bank or a homework dump" is.
4. **Fetch once, derive many times.** Every network fetch is saved to disk keyed by `commit_sha`.
   Scoring, verification and re-verification are pure functions over saved evidence.
5. **Human overrides are sacred.** They live in their own table and no automated run may overwrite them.
6. **Everything traces to a commit SHA.** No SHA, no provenance, no downstream reproducibility.
7. **Add machinery when you hit the wall it addresses — never before.**

---

## 5. MVP architecture — the pipeline

```
┌─ INPUT ───────────────────────────────────────────────────────────────┐
│  topics.yaml     "sql-interview", "python-practice", "pandas", ...    │
└──────────────────────────────┬────────────────────────────────────────┘
                               ▼
                   ┌────────────────────────┐
                   │ 1. QUERY PLANNER       │   1 topic → N bounded queries
                   │    ours · ~60 lines    │   beats the 1000-result cap
                   └───────────┬────────────┘
                               │  topic:sql-interview stars:>=50 created:2019..2020
                               ▼
                   ┌────────────────────────┐
                   │ 2. DISCOVERY           │   GitHub Search API
                   │    + rate limiter      │   25 req/min (margin under 30)
                   └───────────┬────────────┘
                               │  repo ids
                               ▼
                   ┌────────────────────────┐
                   │ 3. ENRICHER            │   GitHub GraphQL, 100 repos/call
                   │                        │   stars · dates · license · SHA
                   └───────────┬────────────┘
                               │
                               ▼
                   ┌────────────────────────┐
                   │ 4. GATE   S_meta       │   pure arithmetic · 0 API cost
                   │    ours · ~40 lines    │   THE THROUGHPUT VALVE
                   └───────────┬────────────┘
                               │  survivors only
                               ▼
                   ┌────────────────────────┐
                   │ 5. INSPECTOR           │   2 Core calls: tree + README
                   │                        │   ⇨ writes bundle to disk
                   └───────────┬────────────┘
                               │  bundle{commit_sha}
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   ┌────────────────────┐          ┌─────────────────────────┐
   │ 6a. STRUCTURE      │          │ 6b. VERIFIER            │
   │     ours · ~30 ln  │          │     LLM + pydantic      │
   │  file-type counts  │          │  real material? kind?   │
   │  extraction signals│          │  quality? confidence?   │
   └──────────┬─────────┘          └────────────┬────────────┘
              └────────────────┬────────────────┘
                               ▼
                   ┌────────────────────────┐
                   │ 7. STORE               │   SQLite → Postgres later
                   │    repos · scores      │   overrides in own table
                   │    verdicts · overrides│
                   └───────────┬────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   ┌────────────────────┐          ┌─────────────────────────┐
   │ 8. CURATE          │          │ 9. EXPORT               │
   │    Datasette       │          │  JSONL → Parquet        │
   │  browse·pin·remove │          │  pydantic contract      │
   │  blacklist·re-tag  │          └────────────┬────────────┘
   └────────────────────┘                       ▼
                                          PROJECT 2
```

### Component reference

| # | Component | Job | Exists because |
|---|---|---|---|
| 1 | **Query Planner** | Splits one topic into queries each returning ≤1000 | Search caps at 1000; one query reaches 0.07% of matches |
| 2 | **Discovery** | Runs searches under a token bucket | GitHub's index is the only free topical filter over all of GitHub |
| 3 | **Enricher** | Batch metadata, 100 repos per GraphQL call | 100 REST calls would cost 100 of your 5,000/hr |
| 4 | **Gate** | Scores from metadata alone, admits the top slice | You discover ~12× faster than you can inspect |
| 5 | **Inspector** | Fetches tree + README, **saves both to disk** | Saved evidence makes every later step free and replayable |
| 6a | **Structure** | Counts file types → extraction signals | Separates a question bank from a `node_modules` dump. No LLM needed |
| 6b | **Verifier** | Judges whether this is genuine practice material | Metadata can't tell "200 SQL problems" from "my bootcamp homework" |
| 7 | **Store** | Repos, scores, verdicts, human overrides | Overrides isolated so re-runs never clobber them |
| 8 | **Curate** | Browse, pin, blacklist, re-tag | The primary human interface |
| 9 | **Export** | Hands kept rows to P2 as a file | P2 must never query P1's database |

### The scoring model

**Stage 1 — `S_meta`** (zero Core calls, decides who gets inspected):

| Component | Formula |
|---|---|
| Popularity | `log10(stars+1)·0.7 + log10(forks+1)·0.3` |
| Velocity | `min(1.0, log10(stars+1) / (log10(age_days+30) × 1.5))` |
| Freshness | `exp(-ln2/365 × days_since_push)` — 1-year half-life |
| Maintenance | `(closed+1)/(open+closed+2)` — Laplace smoothed |

**Stage 2 — `S_final`** adds `S_struct` (file-type ratio) and the LLM verdict, post-inspection.

Every component is stored separately with a `weights_version` stamp, so a ranking is always arguable.

**Not in the score:** license (a redistribution flag for P3, not a quality signal) ·
`mentionableUsers` (proxies org size, structurally biased against the solo-maintainer repos we want).

### Default filters

- Archived repos excluded.
- Forks excluded **unless** `stargazers_count >= 100` — maintained forks of abandoned classics
  routinely surpass the original. Evaluated straight from search results, zero extra API calls.
- Historical `stars:0..9` tail never enumerated; recent low-star assets caught by
  `stars:<10 created:>NOW-90d`.

---

## 6. Data model

```
repos              github_id PK · full_name · clone_url · default_branch · commit_sha
                   license_spdx · is_redistributable · stars · forks · open_issues
                   created_at · pushed_at · is_fork · raw_metadata · first_seen · last_synced

repo_scores        repo_id · weights_version · s_pop · s_vel · s_fresh · s_maint
                   s_struct · s_total · scored_at            [append-only]

verifications      repo_id · verified_at · verdict · confidence · quality_rating
                   content_kind · extraction_signals · reasoning · model_name
                   prompt_version · raw_output                [append-only]

user_overrides     repo_id · status(PINNED|REMOVED|BLACKLISTED|FORCED_VERIFIED)
                   notes · custom_tags · updated_at          [never auto-written]

topics             slug PK · display_name · seed_keywords · topics_version
repo_topics        repo_id · topic_slug · source(api|query|human)

discovery_runs     run_id · topic · started_at · status · repos_found · api_calls_used
discovery_queries  query_id · run_id · query_string · total_count · is_leaf
                   status · pages_completed · last_seen_id    [resumability]
```

**Effective status** = human override if present, else LLM verdict. Human always wins.

---

## 7. Technology — the reuse ledger

### Services we call instead of building

| Instead of building | We call | Saves |
|---|---|---|
| A crawler + full-text index of GitHub | **GitHub Search API** | Years. The biggest non-decision in the project |
| Per-repo metadata fetching | **GitHub GraphQL API** | 100× fewer requests |
| A license scanner | **GitHub `license.spdx_id`** (runs `licensee`) | GitHub already ran it |
| A judgement model | **Gemini Flash** / **local Ollama** | Free tiers, structured output |

### Libraries we import

| Need | Tool |
|---|---|
| HTTP | `httpx` |
| LLM access | `openai` SDK with swapped `base_url` — all four providers are OpenAI-compatible |
| Structured output | Gemini native `responseSchema` + `pydantic` |
| Retries / backoff | `tenacity` |
| Storage | `sqlite3` → `SQLAlchemy` + Postgres later |
| **The entire curation UI** | **`datasette`** — point it at the SQLite file. Do not write a UI |
| CLI | `typer` |
| Terminal output | `rich` |
| Parquet (later) | `pyarrow` |

### Ideas we copy — the code stays where it is

| Source | What we take | Why not the code |
|---|---|---|
| **SEART GHS** (`seart-group/ghs`, MIT, MSR 2021) | `created:` date-bisection to beat the 1000 cap | Java/Spring service; the idea is ~40 lines of Python |
| **OpenSSF Scorecard** | GraphQL alias batching (`repo0:`, `repo1:` …) | Go, security-focused |
| **OpenSSF criticality_score** | Weighted-log composite scoring | Take the maths, not the binary |
| **CHAOSS** | Freshness decay and responsiveness metric definitions | It's a spec, not a library |
| **Munaiah et al. / `reaper`** | Seven "engineered project" dimensions — real project vs homework dump | The peer-reviewed version of what our Verifier does |

### Deliberately rejected

| Rejected | Why |
|---|---|
| GHTorrent | Collection stopped ~July 2019. Dead |
| `bigquery-public-data.github_repos` | Stale snapshot; useless for "what exists now" |
| GH Archive as primary discovery | Events carry repo *slugs*, not topics — misses `kdn251/interviews` entirely |
| Libraries.io SourceRank | 2025 research documents reliability decay |
| `chaoss/augur` | End-of-life |
| LangChain / LangGraph **for the MVP** | The MVP makes one stateless LLM call per repo. A framework adds failure modes, not capability |
| A hand-written web UI | Datasette is free |

> **Caveat on reuse:** borrowing a formula means inheriting its assumptions. `criticality_score` was
> designed for infrastructure libraries, not interview question banks. Copy it, then check it against
> your own data.

---

## 8. Build sequence

| Stage | Target | Deliverable |
|---|---|---|
| **0** | One evening | 3 throwaway scripts: Gemini key works → GitHub token works → one real verdict on one real repo printed to screen |
| **1** | One weekend, ~150 lines | One topic hardcoded · SQLite · `stars>=50` as the whole gate · top 100 repos · tree+README saved to disk · one LLM call each · live progress. **Done when 100 real rows exist** |
| **2** | Days | Datasette over the SQLite file. Browse, pin, blacklist, re-tag. Overrides table |
| **3** | As needed | Add each piece only on hitting its wall (below) |

### Stage 3 triggers

| Add | Only when |
|---|---|
| `created:` bisection + cached partition tree | A topic genuinely exceeds 1000 results and you want the tail |
| Two-stage `S_meta` gate | Core quota actually binds (>5k repos/hr to inspect) |
| Append-only tables + `weights_version` | You re-score often enough to want to diff runs |
| Postgres | Something writes concurrently with the crawler |
| Parquet + pydantic contract | P2 exists as a separate process |
| Budget circuit breaker | You have actually blown a quota once |
| Golden eval fixture | You've seen enough real verdicts to know what "wrong" looks like |

**Rationale:** the previous version of this tool shipped a database with one mock row because no API
key was ever wired up. Stage 0 exists to make that impossible to repeat.

---

## 9. Phase 2 — agentic evolution (after the MVP works)

The pipeline is the foundation, not a throwaway. Agentic P1 keeps components 2, 3, 5 and 7 unchanged
and replaces the *decision-making* around them.

| Pipeline | Agentic replacement | What it unlocks |
|---|---|---|
| Query Planner (fixed recursion) | **Topic Strategist** — plans, observes yield, reformulates, decides when a topic is exhausted | Abandons a query returning ORM libraries instead of grinding its date slices |
| *(nothing)* | **Lead Follower** — reads awesome-lists, follows curated links | **Breaks the 1000-cap entirely.** Curated links resolve via Core (5,000/hr), *not* search. Highest-value single addition |
| Verifier (one-shot) | **Investigator** — decides what evidence it needs, opens sample files, terminates when confident | Fixes "a README is insufficient evidence" and "a repo can be 90% junk" |
| *(nothing)* | **Auditor** — samples its own rejects, hunts systematic bias | Closes the one gap flagged FATAL in review: false rejects are invisible by construction |
| *(nothing)* | **Curator Liaison** — infers the rule behind your overrides, proposes it back | Your curation compounds instead of repeating |
| Static `topics.yaml` | **Taxonomist** — proposes new topics from observed clusters | Taxonomy grows from evidence |

**Frameworks become justified here:** PydanticAI for typed agents; LangGraph if the plan→act→observe
loop needs checkpointed resume. Not before.

**What agentic costs:** determinism (log trajectories so runs are replayable even if unpredictable) ·
a sharply escalated injection surface (the Lead Follower *acts on* attacker-controlled text — allowlist
targets to `github.com/{owner}/{repo}`, cap follow depth, never let followed content alter the goal) ·
unbounded loops (hard caps on tool calls per repo and per topic).

---

## 10. Known pitfalls — do not reintroduce

Four defects found in review. Each is cheap to avoid and expensive to discover later.

1. **Never gate on file count.** A rule like *"override VERIFIED if the tree has <3 substantive files"*
   fires hardest on single-large-markdown hubs — which is `kdn251/interviews` and
   `yangshun/tech-interview-handbook`, exactly the repos this system exists to find. It also loses to
   real attackers: three files of boilerplate defeats it. Keep XML delimiting of untrusted README text;
   drop the file-count heuristic.
2. **Sample your rejects.** Eyeball 10 per run from stage 1. A false reject is invisible by
   construction, so without sampling a biased Verifier entrenches a permanent blind spot.
3. **Save the tree *and* the README together**, keyed by `commit_sha`. Saving only the README means
   re-verification still re-spends a Core call for the deterministic half — defeating its own purpose.
4. **Derive extraction signals from the tree, not from the LLM.** Counting `.ipynb` / `.csv` /
   dominant `.md` is deterministic. Routing it through the model makes it injection-steerable and
   propagates a steered value into P2. Export counts as fact; the strategy hint is advisory.

Also: `git/trees?recursive=1` truncates at ~100k entries, and an attacker can *force* truncation.
Record `tree_truncated` as a first-class fact.

---

## 11. Open decisions

| # | Question | Needed by |
|---|---|---|
| 1 | **Is the repository the right unit?** The goal is questions and datasets, which live *inside* repos. Middle path: emit candidate artifact paths from the tree alongside the repo verdict — cheap, gives P2 a head start | Before P2 design |
| 2 | **Which model tier runs bulk verification?** Gemini free tiers cap on requests/day and likely can't sustain volume. Local Ollama (`qwen2.5-coder:7b`) may need to be Tier 1 with Gemini as escalation — the inverse of the original plan | Stage 3 |
| 3 | **τ: fixed threshold or topic-relative quantile?** A quantile adapts to topic size but reintroduces per-run drift — the exact property that got EWM rejected. Unresolved; two coherent positions | Stage 3 |
| 4 | **Leaf re-probe cadence.** Partition intervals are immutable but membership isn't; a cached leaf that measured 940 can later cross 1000 and silently truncate | Stage 3 |

---

## 12. Definition of done

P1 is complete when:

1. **Partitioning works** — the union of bisected leaves for one major topic exceeds 1000 distinct
   repos, with no HTTP 403.
2. **Scoring is transparent** — 500+ repos scored with every component stored and `weights_version` stamped.
3. **Verification is measured** — ≥85% F1 against a committed golden set of hand-labelled repos,
   built *after* seeing real verdicts, replayable in CI from saved bundles.
4. **Re-runs are safe** — human overrides and verification history survive; a run killed at page 4 of
   a 10-page leaf resumes at page 5 with zero duplicate inserts.
5. **Export is valid** — every exported row carries a non-null `commit_sha` and validates against the
   contract.
6. **A human can actually use it** — you can open the map, sort it, and blacklist a repo in under 10 seconds.
