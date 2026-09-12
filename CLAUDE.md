# Kaizen Harvester

Three independent sub-projects in one repo. **Only Project 1 is in scope right now.**

| | Project | Status |
|---|---|---|
| **P1** | GitHub Knowledge Map — find & score repos worth harvesting | **active** |
| **P2** | Ingestion → Knowledge Archive | not started |
| **P3** | Domain Generator Agents (SQL/Python/Scala/Spark) | not started |

## Current state — read before editing anything

`core/`, `cli.py`, `recipes/` and `storage/` are **v1 legacy**. P1 is a **fresh rebuild**, not an
extension of them. Do not refactor `core/` to fit the new design, and do not assume its patterns are
current. Treat it as reference only.

Why v1 failed: it authenticates only against `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
(`core/agents/base.py`), neither of which exists here. Every "successful" run used a mock LLM, so
`storage/vault.duckdb` holds one fabricated record. **Stage 0 of the new build exists specifically to
make that impossible to repeat: prove a real model call works before building anything on top of it.**

## Documentation map

| Doc | Authoritative for |
|---|---|
| `docs/P1_ARCHITECTURE.md` | **P1 architecture of record.** Start here |
| `docs/CONCEPT_NOTES.md` | The three-project programme and how they separate |
| `docs/P1_CONCEPT_NOTES.md` | Earlier P1 spec — superseded where it conflicts with `P1_ARCHITECTURE.md` |
| `.agents/AGENTS.md` | Workflow and git model (shared with the Antigravity CLI) |
| `docs/HLD.md`, `docs/LLD.md`, `docs/agent_swarm.md` | v1 design — historical |

When `P1_CONCEPT_NOTES.md` and `P1_ARCHITECTURE.md` disagree, the architecture doc wins.

## Environment

- Python **3.13** in `./venv` (note: `pyproject.toml` still targets `py310`)
- `./venv/bin/pytest` · `./venv/bin/ruff` — do not assume they're on `PATH`

```bash
./venv/bin/pytest                  # tests (asyncio_mode = auto)
./venv/bin/ruff check .            # lint  (line-length 120, rules E/F/I)
./venv/bin/ruff format .           # format
```

## LLM providers — verify before designing around one

**No `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` exists.** `requirements.txt` lists `openai` and
`anthropic`; that is misleading legacy.

Currently available in this shell:

| Provider | Env var | Status |
|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | **set** |
| Ollama (local) | none needed | **running** — `qwen2.5-coder:7b`, `llama3.1:8b`, `mistral:7b`, `deepseek-r1:14b`, `gemma4:12b-mlx` |
| Gemini | `GOOGLE_API_KEY` | **unset here** — design docs assume it; confirm before relying on it |
| Experiential Labs | `EXPLABS_API_KEY` | unset |

`GITHUB_TOKEN` is **set**.

All four providers are OpenAI-compatible — use the `openai` SDK with a swapped `base_url`. One
adapter, not four clients. Bulk verification volume likely exceeds Gemini's free-tier daily cap, so
local Ollama is the realistic Tier 1 with a hosted model as escalation.

## Git

Full model in `.agents/AGENTS.md`. The non-negotiables:

- Branch from `dev`, never `main`. Name `feat/<description>`. PRs target `dev` (`--base dev`).
- **HARD RULE: never merge `dev` → `main` from the CLI.** That release merge is done by the user in
  the GitHub web UI only.
- Never reuse a merged branch — start fresh from `dev`.
- Conventional Commits (`feat(scope): …`).

## Design principles

1. **Don't reinvent the wheel.** Before writing a component, ask *what is the smallest thing I can
   call instead?* Write code only where nobody has solved this exact problem. Datasette is the
   curation UI. GitHub's search index is the topical index. Don't rebuild either.
2. **Metadata before content.** Cheap signals first, expensive ones last.
3. **An LLM only where judgement is required.** Counting `.ipynb` files is not judgement.
4. **Fetch once, derive many times.** Every fetch is saved to disk keyed by `commit_sha`; scoring and
   verification are pure functions over saved evidence.
5. **Human overrides are sacred** — own table, never auto-written.
6. **Add machinery when you hit the wall it addresses, never before.** See the stage triggers in
   `docs/P1_ARCHITECTURE.md` §8.

## Known pitfalls — do not reintroduce

These were found in design review. Each is cheap to avoid and expensive to rediscover.

1. **Never gate on file count.** "Reject if the tree has <3 substantive files" fires hardest on
   single-large-markdown hubs — `kdn251/interviews`, `yangshun/tech-interview-handbook` — which are
   exactly the repos P1 exists to find. Keep XML-delimiting of untrusted README text; drop the count.
2. **Sample your rejects.** A false reject is invisible by construction. Eyeball ~10 per run or a
   biased verifier entrenches a permanent blind spot.
3. **Save the tree *and* the README together**, keyed by `commit_sha`. Saving only the README means
   re-verification still re-spends a Core API call, defeating its own purpose.
4. **Derive extraction signals from the tree, not from the LLM.** Counting `.ipynb`/`.csv`/dominant
   `.md` is deterministic. Routing it through the model makes it injection-steerable.

Also: `git/trees?recursive=1` truncates at ~100k entries and truncation can be forced by an attacker.
Record `tree_truncated` as a first-class fact.

## GitHub API budget

Search **30/min** · Core REST **5,000/hr** · GraphQL 5,000 points/hr · **search returns at most 1,000
results per query** regardless of `total_count`. Discovery outruns inspection ~12×, so the score gate
before tree-fetch is load-bearing, not an optimisation.

## Conventions

- Pydantic for every boundary — LLM output, API responses, the P1→P2 export contract.
- `commit_sha` is never nullable. No SHA, no provenance.
- No cross-project database reads. P1 hands P2 a file, never a view or a join.
