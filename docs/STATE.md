# Kaizen Harvester — current state

_Updated: 2026-09-12_

> This file is the handoff token between Claude Code (which sees the repo) and claude.ai design
> sessions (which see only docs). Keep it under ~40 lines and re-upload it to the Project whenever it
> changes. If it's stale, both surfaces are reasoning about a system that doesn't exist.

## Active

**P1, Stage 0 — not started.** Branch: `chore/remove-v1-legacy`.

v1 has been deleted (recoverable at tag `v1-archive`). `projects/p1-map/` holds a package skeleton and
nothing else. **No real LLM call has ever been made in this repo.**

## Decided since last update

- v1 deleted rather than refactored — it shipped one fabricated row and every doc describing it was a
  hazard to future design sessions — `README.md`, `CLAUDE.md`
- `uv` workspace adopted now, `projects/p1-map` as the only member — moving an empty tree is free,
  moving a working pipeline later is not — `pyproject.toml`
- `packages/`, `p2-ingest`, `p3-generate` deliberately **not** scaffolded — principle 7 — `docs/CONCEPT_NOTES.md`
- Stage 0 is a throwaway script calling the `openai` SDK against OpenRouter's or Ollama's
  `base_url` — no provider abstraction, no base class. A provider layer is stage-3 machinery
  and there is not yet one working call to abstract over — `CLAUDE.md`
- Stage 0 is provider-agnostic: either OpenRouter or Ollama clears it, so pick whichever
  verifies fastest today. This does **not** settle open decision 2 — `docs/P1_ARCHITECTURE.md` §11.2

## Open right now

Eight decisions, none blocking Stage 0. Highest value first:

1. **What does "good" mean concretely?** The Verifier needs a rubric — is a curated awesome-list
   VERIFIED, or only material with actual Q&A? (`intent.md` Q3) — *blocks Stage 1*
2. **Which provider runs the verdict?** OpenRouter or local Ollama (`intent.md` Q1, architecture §11.2)
3. **Which topic actually?** `sql-interview` is assumed, may be a placeholder (`intent.md` Q2)
4. **How do I know the verdicts are good?** No eval by design at this stage (`intent.md` Q4)
5. Is the repository the right unit, or should P1 emit candidate artifact paths? (architecture §11.1)
6. τ: fixed threshold or topic-relative quantile? (architecture §11.3)
7. Leaf re-probe cadence (architecture §11.4)
8. Does `.agents/` stay the single skill source long-term, or converge on `.claude/`?

## Next action

**Stage 0.** Three throwaway scripts, deleted once they've proven the point:
provider key works → GitHub token works → one real verdict on one real repo printed to screen.

Decision 1 (the rubric) is the best use of a claude.ai design session in the meantime — it's pure
judgement and needs no code.

## Frozen

P2, P3 — designed in `docs/CONCEPT_NOTES.md`, not started. P2 concept work waits until P1 Stage 2 is
done and ~100 real verdicts have been read.
