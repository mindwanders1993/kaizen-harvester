# Working across Claude surfaces

_How Kaizen Harvester gets built, from concept to production._

The organising idea is one sentence: **the repo is the memory bus.** claude.ai can't see your code;
Claude Code can't see your chats. Anything that must survive gets written into `docs/`. Every tool
assignment below follows from that.

---

## 1. Tool assignment

| Surface | Owns | Must NOT be used for |
|---|---|---|
| **claude.ai Project** | Concept, research, adversarial design review, rubric authoring, resolving open decisions | Anything about what the code *currently does* — it can't see code and will answer confidently anyway |
| **Claude Code CLI** | Planning, building, testing, reviewing, running the pipeline | Open-ended design debate — burns context on file reads to answer pure-judgement questions |
| **Claude Code on web** (claude.ai/code) | Away-from-desk work that touches the repo | Long build sessions |
| **`/code-review`, `/security-review`** | Gate before every PR to `dev`. Security review matters here — the Verifier eats attacker-controlled README text | — |
| **Datasette** | The P1 curation UI | Don't write a UI. Settled in `P1_ARCHITECTURE.md` §7 |
| **GitHub PR review action** | Second pass on `feat/* → dev` | The `dev → main` merge — user's, web UI only |

**Not yet, and why:** MCP servers — `gh` CLI + `GITHUB_TOKEN` already cover GitHub; a SQLite MCP
earns its place when `harvest.db` is being queried conversationally every day. Claude in Chrome —
nothing in this programme is browser-shaped. The Anthropic API directly — no key here; the LLM gateway
targets OpenRouter/Ollama, and Claude is reachable through OpenRouter if ever wanted.

---

## 2. The phase loop

Each phase has a **gate artifact** committed to the repo. That's what makes handoffs between mutually
blind surfaces survivable.

| # | Phase | Surface | Gate artifact |
|---|---|---|---|
| 1 | **Concept** — problem, why now, out of scope | claude.ai Project | `docs/sdlc/NNN-slug/intent.md` |
| 2 | **Research** — prior art, what to call instead of build | claude.ai Project | *Reuse ledger* section in `intent.md` |
| 3 | **Design** — architecture delta, adversarial review | claude.ai Project | edit to `docs/P1_ARCHITECTURE.md` |
| 4 | **Plan** — file-level strategy | Claude Code, plan mode | `docs/sdlc/NNN-slug/plan.md` |
| 5 | **Build** — `feat/*` off `dev` | Claude Code CLI | code + tests |
| 6 | **Review** — `/code-review`, then `/security-review` | Claude Code | findings applied |
| 7 | **PR** — `--base dev` | Claude Code + action | merged to `dev` |
| 8 | **Operate** — run, curate, sample rejects | Datasette + Claude Code | `docs/STATE.md` updated |
| 9 | **Release** — `dev → main` | **User, GitHub web UI only** | tag |

`docs/sdlc/001-p1-mvp/intent.md` is the first instance. Add `plan.md` beside each `intent.md`, and
phases 1–4 become a paper trail worth re-reading when P2 starts.

---

## 3. The claude.ai Project

**One Project, not three.** The cross-cutting concerns — separation rule, provenance chain, license
propagation, LLM gateway — span all three sub-projects. Split when P2 design begins and the Project
starts conflating P1's *"is this repo worth harvesting?"* with P2's *"is this knowledge unit good?"*.

### Knowledge — upload exactly these six

`CLAUDE.md` · `docs/CONCEPT_NOTES.md` · `docs/P1_ARCHITECTURE.md` · `docs/sdlc/001-p1-mvp/intent.md` ·
`docs/STATE.md` · `.agents/AGENTS.md`

Leave out `docs/P1_CONCEPT_NOTES.md` — superseded where it conflicts with the architecture doc, and
two overlapping specs get silently averaged.

**Refresh discipline:** when a doc changes, **delete the old copy before uploading the new one.** Two
versions of `P1_ARCHITECTURE.md` in knowledge is the most common way Projects go quietly wrong —
answers averaged across contradictory specs, with no warning.

### Custom instructions — paste as-is

> You are my design partner on **Kaizen Harvester** — a three-project programme. P1 maps GitHub repos
> worth harvesting; P2 ingests selected repos into a knowledge archive; P3 generates verified artifacts
> from that archive. **Only P1 is active.** P2 and P3 are designed but not started; treat questions about
> them as concept work and say so.
>
> **Your role is judgement, not implementation.** I build in Claude Code at the terminal. Here, pressure-test
> decisions, surface what I've missed, help me write specs. Don't write implementation code unless I ask;
> a short sketch to make a point is fine.
>
> **Source precedence** (higher wins on conflict):
> 1. What I say in this chat
> 2. `STATE.md` — where the build actually is today
> 3. `P1_ARCHITECTURE.md` — the architecture of record
> 4. `CONCEPT_NOTES.md` — the programme and the separation rule
> 5. `CLAUDE.md` — environment and hard rules
>
> The previous version of this system was deleted, not extended. If I describe code that doesn't match the
> docs above, say so rather than reconciling it.
>
> **Non-negotiable context:**
> - No `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` exists. `GOOGLE_API_KEY` is unset. Available: OpenRouter
>   (`OPENROUTER_API_KEY`) and local Ollama. `GITHUB_TOKEN` is set.
> - v1 shipped a database with one fabricated row because it ran on a mock LLM. Every proposal must be
>   checkable against something real.
> - GitHub: search 30 req/min · Core REST 5,000/hr · search returns **at most 1,000 results per query**,
>   whatever `total_count` says.
> - No project ever SELECTs from another project's tables. P1 hands P2 a file, never a view or a join.
>
> **How to answer:**
> - Lead with a recommendation, then the reasoning. No option surveys.
> - Always name the cheapest existing thing I could call instead of building.
> - Apply "add machinery when you hit the wall it addresses, never before" — tell me when I'm designing
>   stage-3 machinery at stage 1, or P2 machinery before P1 ships.
> - Disagree with me directly when I'm wrong. Flag the assumption you're least sure of.
> - You cannot see code and cannot run anything. Never assert what the code currently does — say
>   "verify in Claude Code."
> - When a chat resolves something, end with a markdown block I can paste straight into the repo.

### Chat hygiene

One chat per decision, named after it — not one rolling megathread. The eight open decisions in
`docs/STATE.md` are eight natural chats.

**The Project is not durable memory.** The moment a chat resolves something, paste its closing block
into the repo. A conclusion that stays in a transcript is lost.

### Guardrail tests

After pasting the instructions, confirm the setup works:

| Ask | Correct behaviour |
|---|---|
| *"Should I extend `core/agents/base.py`?"* | Says that code no longer exists |
| *"What does the gate do in my code right now?"* | Describes the **designed** gate; tells you to verify in Claude Code |
| *"Let's design P2's extractor fan-out."* | Engages, but flags that P1 hasn't produced the evidence P2's design needs |

---

## 4. `docs/STATE.md`

The one file that makes two blind surfaces cooperate, and what makes away-from-desk work possible.
Under ~40 lines, re-uploaded to the Project whenever it changes. See the file itself for the shape.

---

## 5. Claude Code setup

**a. The `dev → main` rule is enforced mechanically.** A `PreToolUse` hook in `.claude/settings.json`
rejects `git merge` / `gh pr merge` targeting `main`. It was an instruction before, and instructions
get missed under context pressure.

**b. `/fewer-permission-prompts`** — run once; writes an allowlist for the read-only calls approved
constantly (`uv run pytest`, `uv run ruff`, `gh pr view`, `git status`).

**c. Don't duplicate skills.** `.agents/skills/` is the single source, shared with the Antigravity CLI.
`CLAUDE.md` points Claude Code at it. Two drifting workflow definitions is the failure mode to avoid.

**d. One project skill worth writing when Stage 1 lands** — `/sample-rejects`: pull 10 rejected repos
with their verdicts, formatted for review. This is pitfall 2 from the architecture doc, the one
flagged FATAL, and it needs to be one keystroke or it won't happen.

**e. Git worktrees** become useful when P2 starts and a P1 fix is in flight while P2 scaffolds.

---

## 6. Away from the terminal

Two surfaces; picking wrong wastes the session.

- **Thinking, no repo access** → the claude.ai Project in the mobile app. Design debate, rubric work,
  reject sampling from pasted output, pre-mortems.
- **Touching the repo** → **Claude Code on the web** (claude.ai/code). Runs against the repo in the
  cloud, so "read the failing test and tell me what's wrong" actually works.

Close every mobile Project session with prompt **G** below, then paste at the desk. Otherwise the
session evaporates.

---

## 7. Prompt library

**A. Resolve an open decision**
```
Open decision §11.2: which model tier runs bulk verification — local Ollama
qwen2.5-coder:7b, or OpenRouter hosted. Recommendation first. Then: what evidence
would change it, and what's the cheapest experiment that produces that evidence?
```

**B. Adversarial pass** — recreates a two-model debate solo
```
You wrote the above. Now attack it. You're a skeptical reviewer who thinks this is
over-engineered for a 100-repo MVP. Three strongest objections, ranked. Then say
which you actually concede.
```

**C. Pre-mortem** — the pattern that would have caught v1
```
It's three months out and this is abandoned. Write the postmortem. Rank causes by
probability, not severity. For the top one: what cheap tripwire this week catches it?
```

**D. Rubric authoring** — `intent.md` Q3, blocking Stage 1, pure judgement
```
My Verifier must decide "is this genuine practice material?" I need a rubric precise
enough that two people grading the same repo agree. Edge cases: a curated awesome-list
of SQL links; 200 questions with no answers; a course syllabus; one 5,000-line README
of Q&A. Give the rubric, then the three repos most likely to be graded wrongly by it.
```

**E. Reject sampling** — pitfall 2, ideal for mobile
```
Ten repos my verifier rejected, with reasoning: <paste>
Which rejects are wrong? Is there a systematic bias, or ten independent calls?
```

**F. Contract design** — when P2 starts; the separation rule is where monorepos die
```
P1 hands P2 a file, never a join. Design the export contract. What must be in it so
P2 never needs to ask P1 a follow-up question? What's the cost of getting it wrong?
```

**G. Handoff** — end every session that decided something
```
Write the delta for docs/STATE.md and, if this changes the architecture, the exact
replacement text for the affected section. Markdown only, no commentary.
```

---

## 8. Phasing across P1 / P2 / P3

| Milestone | Trigger |
|---|---|
| **P1 Stage 0** — one real LLM call, one real verdict, printed to screen | now |
| P1 Stage 1 — 100 real rows | Stage 0 passes |
| P1 Stage 2 — Datasette curation | 100 rows exist |
| **P2 concept work** | P1 Stage 2 done *and* ~100 verdicts read |
| P3 concept work | P2 produces its first verified knowledge unit |
| Split the claude.ai Project | P2 design begins |
| `packages/` + full `uv` workspace | P2 needs a second project to exist |

The temptation is to design P2 and P3 now — they're the interesting parts and the docs make them feel
close. Resist it specifically because **P2's design depends on facts P1 hasn't produced yet**: what
fraction of verified repos are single-README hubs, how often the tree truncates, whether
`extraction_signals` is actually predictive. Designing P2 against guesses is how you get a second
`core/`.
