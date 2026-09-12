# Intent 001 — P1 MVP: a real, browsable repo map

_Status: DRAFT — awaiting originator's corrections_
_Created: 2026-09-12 · Owner: @mrrobot_

## Problem

I cannot currently answer *"where is the good SQL interview material on GitHub?"* without manually
searching and reading repos. GitHub's search returns 1.4M results for `sql`, ranked by an opaque
relevance function, with no way to tell a genuine 200-question bank from a bootcamp homework dump
except by opening each one.

The previous attempt at solving this (`core/`, v1) produced a database with **one fabricated record**
because it was built top-down — schemas, agents, memory tiers and a CLI all landed before any real
model call was ever made. It was never wired to a working API key, and the failure was invisible
because a mock LLM returned plausible output.

## Proposed outcome

A local SQLite database holding **~100 real GitHub repositories** for one topic, each with:

- real metadata from the GitHub API (stars, dates, license, `commit_sha`)
- its file tree and README saved to disk, keyed by `commit_sha`
- a verdict from a **real LLM call** — is this genuine practice material, what kind, how good
- a place for my own overrides that survives re-runs

…and a way to **browse and edit it** without writing a UI.

Success is visible, not inferred: I open the database and see 100 rows about repos I recognise, with
judgements I can argue with.

## Affected users and systems

| | |
|---|---|
| **User** | Me, solo. No team, no other consumers yet |
| **Systems touched** | GitHub Search + Core REST APIs · an LLM provider · local SQLite · local disk for evidence bundles |
| **Not touched** | P2 · P3 · any cloud infrastructure. (v1 `core/` was deleted on 2026-09-12; recoverable at tag `v1-archive`) |
| **Downstream** | P2 will eventually consume this map — but no contract is owed until P2 exists |

## Constraints

1. **Must make a real model call in the first session.** Not a mock, not a stub. This is the specific
   failure being corrected.
2. **Provider reality:** `GOOGLE_API_KEY` is not set in this environment. Available today are
   OpenRouter and local Ollama (`qwen2.5-coder:7b` and others). The design assumed Gemini — that
   assumption must be resolved before, not during, the build.
3. **One weekend of effort, roughly 150 lines.** If it needs Postgres, a migration layer, a partition
   tree or a rate-limiter to produce its first row, the scope is wrong.
4. **One topic, hardcoded.** `sql-interview`. Generalisation is a later problem.
5. **No partitioning.** The top ~100 repos by stars are nowhere near the 1,000-result cap.
6. **Evidence is saved, never re-fetched.** Tree and README to disk together, keyed by `commit_sha`,
   so re-judging with a better model costs zero API calls.
7. **Do not build a curation UI.** Point Datasette at the SQLite file.

## Explicitly out of scope

Query planner · `created:` bisection · two-stage scoring gate · GraphQL batch enrichment · append-only
tables · budget circuit breaker · Parquet export · Pydantic contract package · golden eval fixture ·
agentic components · anything in `docs/P1_ARCHITECTURE.md` §9.

These are all designed and waiting in the architecture doc. Each gets built when it hits the wall it
addresses (§8 stage triggers) — not before.

## Open questions

1. **Which provider runs the verdict?** OpenRouter (hosted, costs money, fast) or local Ollama (free,
   unlimited, slower, weaker)? At 100 repos either works. The answer matters for stage 3, not here —
   but picking one now avoids blocking.
2. **Which topic actually?** `sql-interview` is assumed. Is that the topic you most want answered
   first, or is it a placeholder?
3. **What does "good" mean concretely?** The verifier needs a rubric. Is a curated awesome-list of
   SQL resources VERIFIED, or is only material with actual questions-and-answers in it?
4. **How do I know the verdicts are any good?** There is no eval at this stage by design. The
   proposed substitute: read all 100 verdicts myself once. That is feasible at 100 and impossible at
   10,000 — so what replaces it later is a stage-3 question.

## Definition of done

- [ ] A real LLM verdict on a real repo printed to screen, before any schema exists *(Stage 0)*
- [ ] `harvest.db` contains ~100 rows for `sql-interview`, all from real API responses
- [ ] Every row has a non-null `commit_sha` and a saved evidence bundle on disk
- [ ] `datasette harvest.db` opens and I can sort, filter and blacklist a repo in under 10 seconds
- [ ] I have read all ~100 verdicts and can say whether the top 10 are actually good
