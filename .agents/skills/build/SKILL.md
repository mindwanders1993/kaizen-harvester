---
name: build
description: Use this skill after a plan is approved. It executes the Loop Engineering process (Build -> Test -> Reflect) until the code is 100% verified.
---

# Phase 2: Loop Engineering (Build, Test, Reflect)

When activated, execute these steps iteratively until successful:

1. **Build**: Implement the agreed-upon plan using surgical code edits.

2. **Test (Quality Gate)**: Run the following verification commands from the project root (`/Users/mrrobot/Desktop/Projects/kaizen-harvester`):

   ```bash
   # 1. Activate venv
   source venv/bin/activate

   # 2. Code formatting & linting
   ruff check --fix . && ruff format .

   # 3. Unit test suite
   pytest

   # 4. Dry-run CLI check
   python cli.py stats
   python cli.py run --recipe recipes/sql_challenges.yaml
   ```

3. **Reflect**:
   - If tests **FAIL**: Do not guess blindly. Read the logs/tracebacks, form a hypothesis, fix the code surgically, and return to Step 2.
   - If `ruff` auto-fixed files: Show a brief summary of what was formatted.
   - If tests **PASS**: Proceed to Step 4.

4. **Context Cleanup**: Summarize the changes made so far to consolidate memory and avoid context bloat.

5. **Pause and Prompt**:
   Output the following to the user and WAIT for their response:
   > "Build and quality gates passed 100%. Options:
   > [1] Approve (Proceed to Commit)
   > [2] Refactor Code
   > [3] Add more tests"
