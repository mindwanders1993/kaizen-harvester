# Kaizen Harvester Kaizen Governor

You are operating within the **Kaizen Harvester** (`kaizen-harvester`) repository. We use a Goal-Driven, Context & Loop Engineering methodology based on Kaizen and Karpathy principles (Simplicity First, Surgical Changes).

---

## 🚦 Operational Workflow (Strict Protocol)

You must guide the user through the following chained phases for any feature or fix. Do not skip phases unless explicitly requested by the user:

1. **Plan**: Activate the `plan` skill to analyze requirements, inspect existing `core/` modules, and propose a surgical strategy.
2. **Build**: Activate the `build` skill to implement code and run test loops (`pytest`, `ruff`, dry-run checks).
3. **Commit**: Activate the `commit` skill to review diffs and create conventional commits.
4. **PR**: Activate the `pr` skill to generate a structured PR body and push to GitHub.

---

## 🌿 Git Branching & Staging Model (`feature → dev → main`)

- **`dev` (Staging / Integration)**: Primary development branch.
  - All new feature/fix/chore branches branch from `dev` (`git checkout dev && git pull origin dev && git checkout -b feat/<description>`).
  - Feature PRs target **`dev`** (`--base dev`).
- **`main` (Production Releases)**:
  - Changes are tested and verified end-to-end on `dev` before releasing.
- **🚫 HARD RULE: `dev → main` Merge**:
  - The agent must **NEVER** merge `dev` into `main` via terminal / CLI (`gh pr merge` or `git merge`).
  - The `dev → main` release merge MUST ALWAYS be performed manually by the user from the **GitHub Web UI**.
- **Never reuse a merged branch**: Always start fresh from `dev`.

---

## 🤖 Swarm Architecture & Execution Model

Kaizen Harvester relies on a modular agent swarm architecture:
- **`core/ingress`**: Source collectors (GitHub API queries, cloner, web mesh).
- **`core/agents`**: Specialized multi-agent swarm:
  - **Scout Agent**: Heuristic triage and relevance filtering.
  - **Extractor Agent**: LLM-driven structured extraction into recipe target schemas.
  - **Curator Agent**: Sandboxed execution, SQL verification via DuckDB, and difficulty rating.
- **`core/memory`**: Dual-tier storage (LanceDB vector deduplication + DuckDB relational catalog).
- **`recipes/`**: Declarative YAML harvesting specifications.

---

## 📚 Available Skills

| Skill | When to Use |
|:---|:---|
| `plan` | Starting any new feature, bug fix, or core module enhancement. |
| `build` | Implementing an approved plan (includes linting, formatting, and pytest loops). |
| `commit` | After build is approved — stages, drafts, and commits with Conventional Commits. |
| `pr` | Pushes branch and opens PR via GitHub CLI targeting `dev`. |
| `test` | Running and debugging unit tests, agent mocks, DuckDB sandbox, and vector tests. |
| `dev_env` | Setting up venv, validating environment variables (`OPENAI_API_KEY`, `GITHUB_TOKEN`), checking LanceDB/DuckDB. |
| `ingest_recipe` | Running declarative YAML recipes to discover and buffer raw target files. |
| `harvest_batch` | Autonomous multi-agent factory loop (Scout -> Extractor -> Curator -> LanceDB -> DuckDB) for bulk extraction. |
| `curate_challenge` | Interactive artisanal extraction, DuckDB sandboxing, and quality curation of a single challenge. |

---

## ⚠️ Token & Context Monitoring

You do not have a raw token counter, but you MUST manage context bloat:
- Periodically clear your scratchpads and avoid dumping large raw files or vector arrays into chat context.
- At the end of the **Build** phase, summarize your actions concisely.
- Explicitly prompt the user: *"Notice: If token usage in your UI is getting high, we can use the `/goal` command to start a fresh, focused session using our current summary."*

---

## 🔄 Interactive Chaining & Self-Learning

- **Prompt Options**: At the end of every phase, provide explicit bracketed options to the user (e.g., `[1] Approve to Build, [2] Ideate, [3] Reject`). Wait for their selection before proceeding.
- **Continuous Improvement**: During the Commit/PR phase, ask the user if this workflow could be improved. If so, you are authorized to edit these `.agents/` files to update your own knowledge base.
