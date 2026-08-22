---
name: ingest_recipe
description: Ingress skill that loads declarative YAML recipes, queries GitHub or web endpoints, and fetches raw candidate artifacts into the local buffer.
---

# Kaizen Harvester Recipe Ingress Skill (`ingest_recipe`)

## 🎯 Purpose
The `ingest_recipe` skill executes the declarative source search and shallow fetch operations defined in a recipe (`recipes/*.yaml`). It handles GitHub search queries, repository cloning (`--depth 1`), rate limiting, and buffering candidate files into `storage/raw_buffer/`.

---

## 🚦 Operational Workflow

### 1. Load Recipe & Inspect Targets
- Load the specified YAML recipe (e.g. `recipes/sql_challenges.yaml`).
- Parse the `sources` block (GitHub queries, direct repo URLs, web endpoints).
- Parse the `filters` block (star thresholds, excluded file paths).

### 2. Fetch Candidate Artifacts
- Execute GitHub API searches using `GITHUB_TOKEN`.
- Clone or download candidate `.sql`, `.md`, `.ipynb` files.
- Save artifacts to the raw staging buffer: `storage/raw_buffer/<run_id>/`.

### 3. Summarize Ingress
- Report total repositories scanned, candidate files collected, and API rate limits remaining.
- Prompt the user:
  > "Ingress complete. [X] files collected in buffer. Options:
  > [1] Proceed to Multi-Agent Swarm Extraction (`harvest_batch`)
  > [2] Add more sources to recipe
  > [3] Cancel"
