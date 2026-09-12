# Kaizen Harvester

A GitHub universal scraper, built as **three independent sub-projects**: find the material, ingest it,
then generate from it.

| | Project | Consumes | Produces | Status |
|---|---|---|---|---|
| **P1** | GitHub Knowledge Map | GitHub API | scored, human-curated repo map | **active — Stage 0** |
| **P2** | Ingestion → Knowledge Archive | repo selections from P1 | the knowledge archive | not started |
| **P3** | Domain Generator Agents | the archive | questions, datasets, artifacts | not started |

They are separate because they have different bottlenecks. P1 is metadata-bound and almost free of LLM
cost; P2 is clone-, disk- and LLM-bound; P3 is retrieval- and sandbox-bound. Fused into one pipeline,
the whole thing would move at the speed of the slowest stage.

**The separation rule:** each project owns its own schema, and no project ever SELECTs from another's
tables. P1 hands P2 a file, never a view or a join.

---

## P1 — what it does

> Answers **"which GitHub repos are worth harvesting for topic X?"** — and lets a human correct the
> answer — **before a single repository is cloned.**

It is a librarian building a card catalogue, not a truck moving books. P2 is the truck.

P1 reads two small files per repo: the file tree and the README. Both are saved to disk keyed by
`commit_sha`, so scoring and re-verification are pure functions over saved evidence and cost nothing
to replay.

```
topics.yaml → Query Planner → Discovery → Enricher → Gate (S_meta)
                                                       ↓ survivors
                                            Inspector (tree + README → disk)
                                                       ↓
                                    Structure (deterministic) + Verifier (LLM)
                                                       ↓
                                            Store → Datasette curation → Export to P2
```

## Status

Stage 0: prove a real model call works before building anything on top of it. Nothing else exists yet.

The previous version of this tool (`v1`, tagged `v1-archive`) shipped a database containing **one
fabricated record** — it was built top-down, never wired to a working API key, and a mock LLM returned
plausible output the whole way. It was removed rather than extended. Stage 0 exists specifically to
make that failure impossible to repeat.

## Documentation

| Doc | Authoritative for |
|---|---|
| [`docs/P1_ARCHITECTURE.md`](docs/P1_ARCHITECTURE.md) | **P1 architecture of record.** Start here |
| [`docs/CONCEPT_NOTES.md`](docs/CONCEPT_NOTES.md) | The three-project programme and how they separate |
| [`docs/STATE.md`](docs/STATE.md) | Where the build actually is today |
| [`docs/CLAUDE_WORKFLOW.md`](docs/CLAUDE_WORKFLOW.md) | How this is built across Claude surfaces |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | Prompt library for design sessions — brainstorm, design, review, simulate |
| [`docs/sdlc/`](docs/sdlc/) | Per-work-item intent and plan |
| [`.agents/AGENTS.md`](.agents/AGENTS.md) | Workflow and git model |

## Development

Python 3.13, [`uv`](https://docs.astral.sh/uv/) workspace.

```bash
uv sync                      # install workspace + dev dependencies
uv run pytest                # tests
uv run ruff check .          # lint  (line-length 120, rules E/F/I)
uv run ruff format .         # format
```

### Environment

| Provider | Env var | Status |
|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | set |
| Ollama (local) | none needed | running |
| Gemini | `GOOGLE_API_KEY` | unset |
| GitHub | `GITHUB_TOKEN` | set |

All providers are OpenAI-compatible — one adapter with a swapped `base_url`, not four clients.

## Licence

Unlicensed / all rights reserved. Note that "publicly available" is not "freely usable": P1 carries
each repo's SPDX licence so P3 can filter on redistributability.
