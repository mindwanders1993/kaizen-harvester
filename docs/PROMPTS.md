# Prompt library — claude.ai Project

Reusable prompts for the judgement work: brainstorming, designing, reviewing, and simulating
scenarios. **None of these produce code.** Building happens in Claude Code; see
[`CLAUDE_WORKFLOW.md`](CLAUDE_WORKFLOW.md) for which surface owns what.

Replace `<angle brackets>` before sending.

---

## How to use these

1. **One chat per decision**, named after the decision — not one rolling megathread.
2. **Open with the mode, not the topic.** "Attack this" and "explore this" pull in opposite
   directions; saying which you want up front is most of the value.
3. **Close with `C1` (handoff)** and paste the result into the repo. The Project is not durable
   memory — a conclusion that stays in a transcript is lost.
4. **Re-upload changed docs**, deleting the old copy first.

---

# 1. Brainstorming — divergent

Use when you don't yet know the shape of the answer. The failure mode here is converging too early
on the first plausible option.

### B1 · Option generation with a forced range
```
I need to decide <decision>. Give me five genuinely different approaches —
not five variations of one. For each: the strongest reason to pick it, and
the condition under which it's clearly wrong. Then tell me which two are
actually live, and why the other three aren't.
```

### B2 · Blind-spot hunt
```
Here's my current thinking on <topic>:
<paste>

What am I not seeing? Specifically: what would someone who has built this
before ask me that I haven't asked myself? Rank by how expensive each one
is to discover late.
```

### B3 · Analogy transfer
```
<problem>. Who else has this exact problem shape, in a different domain?
Name three. For each: what they do about it, and whether the solution
transfers here or breaks on a difference that matters.
```

### B4 · Constraint removal
```
The binding constraint on <component> is <constraint>. Suppose it vanished
tomorrow — what would I build instead?

Now the useful half: which parts of that design are worth building anyway,
because the constraint wasn't actually what made them right?
```

### B5 · Taxonomy from evidence
```
Here are <N> real examples I've seen:
<paste>

Propose a taxonomy that carves these at the joints. Then show me the
examples that sit awkwardly in every version you tried — those are where
the taxonomy is wrong, not where the examples are.
```

---

# 2. Designing — convergent

Use when you know the options and need to commit. The failure mode is designing machinery for a
problem you don't have yet.

### D1 · Decision with a falsifier
```
Open decision: <decision, with doc reference>.

Recommendation first, in one sentence. Then the reasoning. Then: what
evidence would change your mind, and what's the cheapest experiment that
produces that evidence this week?
```

### D2 · Smallest thing I could call instead
```
I'm about to build <component>. Before I do: what's the smallest thing I
could call instead? Name specific libraries or services.

If the honest answer is "nothing exists for this," say so — then tell me
the smallest version I'd have to write, roughly in lines.
```

### D3 · Sequencing by irreversibility
```
<piece of work> has these parts:
<list>

Which decision here is the first irreversible one — expensive to change
after the next three steps? Order the work so that decision lands as late
as possible while still unblocking everything else.
```

### D4 · Define the stage trigger
```
I think I need <machinery>. Define its trigger: what observable condition
means I've hit the wall it addresses? State it as something I could check
in one command or one query.

If I can't observe it yet, I don't need the machinery yet — say so plainly.
```

### D5 · Contract design
```
<Producer> hands <consumer> a file, never a join. Design the contract.

What must be in it so the consumer never needs to ask a follow-up question?
For each field I'd be tempted to leave out — what does omitting it cost?
```

### D6 · Cost model
```
<design>. Walk me through what this costs at 100 units, 10,000, and
1,000,000 — in API calls, tokens, dollars, wall-clock and disk.

Which number breaks first, and at roughly what N?
```

---

# 3. Reviewing — critical

Use on something that already exists. The failure mode is a review that agrees with you.

### R1 · Adversarial pass
```
You wrote the above. Now attack it. You're a skeptical reviewer who thinks
this is over-engineered for <current stage>.

Three strongest objections, ranked. Then say which you actually concede
and which you'd defend.
```

### R2 · Assumption audit
```
Here's <doc or design>:
<paste or reference>

List every assumption it rests on. Mark each: (a) verified — and say how,
(b) assumed but cheap to check, (c) assumed and expensive to check.
Sort by how much breaks if it turns out wrong.
```

### R3 · Steelman the rejected option
```
I rejected <alternative> in favour of <choice>, because <reason>.

Make the strongest case for the thing I rejected. If you still agree with
my choice afterwards, say what would have to be true about my situation
for the rejected option to win instead.
```

### R4 · Pre-mortem
```
It's <timeframe> from now and this project is abandoned. Write the
postmortem.

Rank causes by probability, not severity. For the top one: what's the
cheapest tripwire I could add this week that would have caught it?
```

### R5 · Cross-document consistency
```
Check STATE.md, P1_ARCHITECTURE.md and CONCEPT_NOTES.md against each other.

Where do they disagree? For each conflict: which should I trust given the
precedence order, and what should the stale one say instead?
```

### R6 · The reader who wasn't there
```
Read <doc> as someone joining this project today with no context.

What can't you follow? What would you get wrong? Where does it assume a
conversation you weren't part of?
```

---

# 4. Simulating scenarios — running the design without code

The closest thing to evidence available before anything is built. The failure mode is simulating a
happy path you already believe in.

### S1 · Trace one concrete case end to end
```
Walk one real repo — <owner/name> — through the whole P1 pipeline, step by
step. At each stage: what data exists, what call is made, what it costs,
what the output looks like.

Stop at the first step where you have to guess, and tell me what I haven't
specified.
```

### S2 · Adversarial input
```
I'm the attacker. I control the README of a repo I want P1 to mark VERIFIED
and pass downstream to P2. Write my README.

Then tell me which of my tricks the current design stops, and which it
doesn't.
```

### S3 · Failure injection
```
Simulate these failures against <component>, one at a time:
<e.g. GitHub returns 403 mid-run · the tree is truncated · the model
returns invalid JSON · the process is killed at page 4 of 10>

For each: what happens now, what should happen, and is the gap worth
closing at this stage or is it a later problem?
```

### S4 · Scale simulation
```
This design works at <small N>. Run it forward to <large N>.

What breaks first? Is it a wall I hit gradually or a cliff I fall off?
Which stage-3 trigger in P1_ARCHITECTURE.md §8 does it correspond to?
```

### S5 · Rubric dry-run
```
Here's my rubric:
<paste>

Here are <N> real cases:
<paste>

Grade each, showing your reasoning. Then flag the cases where the rubric
forced an answer you disagree with — those are where the rubric is wrong.
```

### S6 · Reject sampling
```
<N> repos my verifier rejected, with its reasoning:
<paste>

Which rejects are wrong? Is there a systematic bias, or N independent
calls? If there's a pattern, what rule would I have to change?
```

### S7 · Roleplay the human
```
You're me, six months in, opening the curation UI on a Monday with 3,000
repos in it.

Walk me through what I actually do in the first five minutes. Where does
the interface fail me?
```

---

# 5. Closing a session

### C1 · Handoff — use this every time something was decided
```
Write the delta for docs/STATE.md, and if this changes the architecture,
the exact replacement text for the affected section.

Markdown only, no commentary — I'm pasting this into the repo.
```

### C2 · Decision record — when the reasoning matters later
```
Summarise this chat as a decision record: what was decided, what was
rejected and why, what would reverse it, and what's still open.

Under 200 words. This goes into the repo, not back to you.
```

---

# Anti-patterns

Things that waste a session here. All of them belong in Claude Code instead.

| Don't ask | Why | Where it goes |
|---|---|---|
| *"What does my code do?"* | It can't see code and will answer from docs anyway, confidently | Claude Code |
| *"Write the extractor"* | Implementation, and it has no way to test what it writes | Claude Code |
| *"Is this bug in `x.py`?"* | Needs the file, the traceback, and a way to run it | Claude Code |
| Pasting long source files | If you're pasting code, you're in the wrong surface | Claude Code |
| *"Design P2's schema"* — right now | P2's design depends on P1 output that doesn't exist yet | After P1 Stage 2 |
| *"Should I use LangGraph?"* — right now | Framework choice is a §9 question; the MVP makes one stateless call per repo | When the agentic phase starts |
