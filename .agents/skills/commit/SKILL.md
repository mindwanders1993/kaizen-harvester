---
name: commit
description: Use this skill after the build phase is approved. It prepares a git diff, drafts a conventional commit, and commits the code upon approval.
---

# Phase 3: Verification & Commit

When activated, execute these steps:

1. **Review**: Run `git status` and `git diff` to review the changes. Ensure no scratch files, temp parquet/db logs, or unrequested changes are included.

2. **Draft Message**: Create a Conventional Commit message (`type(scope): concise description`).
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
   - Examples: `feat(ingress): add github search rate limiter`, `feat(agents): implement scout triage heuristics`.

3. **Pause and Prompt**:
   Output the following to the user and WAIT for their response:
   > "Please review the proposed commit.
   > Message: `<proposed-message>`
   > Options:
   > [1] Approve (Commit changes)
   > [2] Edit Message"

4. **Execute**: If approved, run `git add <files>` and `git commit -m "<message>"`.

5. **Pre-Commit Hook Failure Protocol**:
   If `git commit` is rejected by pre-commit hooks (Ruff / Black), do NOT re-run blindly:
   - Run auto-remediation: `uv run ruff check --fix . && ruff format .`
   - Show the user what was auto-fixed via `git diff`.
   - Re-stage and commit.

6. **Self-Learning Prompt**:
   Output:
   > "Commit successful. Options:
   > [1] Proceed to PR
   > [2] Done (Stay on branch)
   >
   > *Kaizen Check: Did we encounter any workflow friction today? Should I update my `.agents/` knowledge base to improve for next time?*"
