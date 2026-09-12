---
name: plan
description: Use this skill to initiate a new feature or fix. It analyzes the codebase and creates a surgical implementation plan for user approval.
---

# Phase 1: Context & Plan Engineering

When activated, execute these steps:

1. **Understand Goal**: Read the user's request. Ask clarifying questions if the goal, scope, or recipe target is ambiguous.
2. **Context Gathering**: Read `docs/P1_ARCHITECTURE.md` (architecture of record) and `docs/STATE.md` (where the build actually is). Then view relevant files under `projects/p1-map/`. Never reference `core/`, `cli.py` or `recipes/` — they were deleted with v1.
3. **Draft Plan**: Create a markdown artifact outlining:
   - **Goal**: One sentence summary.
   - **Branch**: Proposed branch name created off `dev` (e.g., `feat/...`, `fix/...`, `chore/...`).
   - **Files to Modify**: Exact list of target files.
   - **Karpathy Check**: Confirm this is the simplest viable approach (Surgical Changes, zero speculative complexity).
4. **Pause and Prompt**: 
   Output the following to the user and WAIT for their response:
   > "Here is the plan. Options: 
   > [1] Approve (Proceed to Build)
   > [2] Ideate (Modify Plan)
   > [3] Reject"
