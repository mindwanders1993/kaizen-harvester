# Kaizen Harvester — Kaizen Governor

You are operating within the **Kaizen Harvester** (`kaizen-harvester`) repository. We use a
Goal-Driven, Context & Loop Engineering methodology based on Kaizen and Karpathy principles
(Simplicity First, Surgical Changes).

---

## 📍 Current state — read before editing anything

Three sub-projects, **only P1 is active**:

| | Project | Status |
|---|---|---|
| **P1** | GitHub Knowledge Map — find & score repos worth harvesting | **active — Stage 0** |
| **P2** | Ingestion → Knowledge Archive | not started |
| **P3** | Domain Generator Agents (SQL/Python/Scala/Spark) | not started |

The v1 multi-agent harvester (`core/`, `cli.py`, `recipes/`) was **deleted**, not extended. It shipped
a database with one fabricated record because it ran on a mock LLM and was never wired to a real key.
It is recoverable at the `v1-archive` tag. Do not resurrect its patterns.

**P1 lives in `projects/p1-map/`.** Nothing exists there yet beyond the package skeleton.

---

## 🚦 Operational Workflow (Strict Protocol)

Guide the user through these chained phases for any feature or fix. Do not skip unless asked:

1. **Plan** — activate the `plan` skill: analyse requirements and propose a surgical strategy.
2. **Build** — activate the `build` skill: implement and run test loops (`uv run pytest`, `uv run ruff`).
3. **Commit** — activate the `commit` skill: review diffs, create conventional commits.
4. **PR** — activate the `pr` skill: generate a structured PR body and push, targeting `dev`.

---

## 🌿 Git Branching & Staging Model (`feature → dev → main`)

- **`dev` (Staging / Integration)** — primary development branch.
  - All new branches come off `dev`: `git checkout dev && git pull origin dev && git checkout -b feat/<description>`.
  - Feature PRs target **`dev`** (`--base dev`).
- **`main` (Production Releases)** — changes are verified end-to-end on `dev` before release.
- **🚫 HARD RULE: `dev → main` merge.**
  - Never merge `dev` into `main` via terminal/CLI (`gh pr merge` or `git merge`).
  - That release merge is performed **by the user, in the GitHub web UI, only.**
  - This is enforced mechanically by a `PreToolUse` hook in `.claude/settings.json`.
- **Never reuse a merged branch** — always start fresh from `dev`.
- Conventional Commits (`feat(scope): …`).

---

## 🏗️ P1 Architecture

`docs/P1_ARCHITECTURE.md` is the architecture of record. The pipeline:

| # | Component | Type | Job |
|---|---|---|---|
| 1 | **Query Planner** | deterministic | One topic → N bounded queries; beats the 1000-result cap |
| 2 | **Discovery** | rate-limited | GitHub Search API at 25 req/min (margin under 30) |
| 3 | **Enricher** | GraphQL | Batch metadata, 100 repos per call |
| 4 | **Gate** (`S_meta`) | deterministic | Pure arithmetic, zero API cost. **The throughput valve** |
| 5 | **Inspector** | 2 Core calls | Tree + README → **saved to disk keyed by `commit_sha`** |
| 6a | **Structure** | deterministic | File-type counts → extraction signals |
| 6b | **Verifier** | LLM + pydantic | Is this genuine practice material? kind? quality? |
| 7 | **Store** | SQLite | repos · scores · verdicts · overrides (own table) |
| 8 | **Curate** | Datasette | Browse, pin, blacklist, re-tag. **Do not write a UI** |
| 9 | **Export** | JSONL | Hands kept rows to P2 as a file, never a join |

**Design principles:** don't reinvent the wheel · metadata before content · an LLM only where
judgement is required · fetch once, derive many times · human overrides are sacred · add machinery
when you hit the wall it addresses, never before.

---

## 📚 Available Skills

| Skill | When to Use |
|:---|:---|
| `plan` | Starting any new feature, fix, or component. |
| `build` | Implementing an approved plan (lint, format, pytest loops). |
| `commit` | After build is approved — stages, drafts, conventional commits. |
| `pr` | Pushes branch and opens PR via `gh`, targeting `dev`. |
| `test` | Running and debugging tests. |
| `dev_env` | Setting up the `uv` workspace and validating provider credentials. |

---

## ⚠️ Token & Context Monitoring

You do not have a raw token counter, but you MUST manage context bloat:
- Clear scratchpads periodically; never dump large raw files into chat context.
- At the end of the **Build** phase, summarise your actions concisely.
- Prompt the user: *"If token usage is getting high, we can start a fresh focused session from the
  current summary in `docs/STATE.md`."*

---

## 🔄 Interactive Chaining & Self-Learning

- **Prompt Options**: end every phase with explicit bracketed options
  (e.g. `[1] Approve to Build, [2] Ideate, [3] Reject`). Wait for the selection.
- **Continuous Improvement**: during Commit/PR, ask whether this workflow could be improved. If so,
  you are authorised to edit these `.agents/` files to update your own knowledge base.
- **Record decisions.** When a phase settles something, write it to `docs/STATE.md`. It is the handoff
  token between this repo and design sessions on claude.ai.
