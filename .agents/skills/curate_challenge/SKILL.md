---
name: curate_challenge
description: Interactive artisanal extraction, DuckDB sandboxing, dialect normalization, and quality curation of a single challenge.
---

# Kaizen Harvester Single Challenge Curation Skill (`curate_challenge`)

## 🎯 Purpose
The `curate_challenge` skill provides an interactive co-design and quality assurance workflow for authoring, curating, and testing a single high-value challenge or domain artifact.

---

## 🚦 Operational Workflow

### Step 1: Candidate Selection
- Select a specific candidate file or raw problem statement from `storage/raw_buffer/` or a user-provided snippet.

### Step 2: Extraction & Dialect Normalization
- Extractor Agent parses the problem statement, setup DDL, and solution SQL.
- Checks against [`references/duckdb_gotchas.md`](file:///Users/mrrobot/Desktop/Projects/kaizen-harvester/.agents/skills/curate_challenge/references/duckdb_gotchas.md) for known dialect quirks (integer division, date truncation, string splitting, window functions).

### Step 3: Empirical DuckDB Sandbox Verification
- Runs the generated DDL and Solution SQL in an in-memory DuckDB instance.
- Displays the sample output table to the user.

### Step 4: LanceDB Deduplication & Approval
- Checks vector distance against the existing LanceDB knowledge vault.
- Prompts the user:
  > "Challenge verified in DuckDB sandbox with zero errors. Options:
  > [1] Approve & Save to Vault
  > [2] Edit Problem Narrative / SQL
  > [3] Reject"
