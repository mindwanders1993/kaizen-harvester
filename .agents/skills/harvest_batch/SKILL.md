---
name: harvest_batch
description: Autonomous multi-agent factory loop (Scout -> Extractor -> Curator -> LanceDB -> DuckDB) that processes batches of candidate files with self-correction and minimal chat interruption.
---

# Kaizen Harvester Batch Agent Swarm Skill (`harvest_batch`)

## 🎯 Purpose
The `harvest_batch` skill runs the autonomous **Scout ➔ Extractor ➔ Curator ➔ Memory Vault** loop over a batch of 5–20 candidate files from the ingress buffer. It operates in the background with zero conversational interruption per item, self-corrects SQL errors, deduplicates against LanceDB, and presents a single Macro Batch Summary table upon completion.

---

## 🚦 Operational Workflow (Autonomous Background Loop)

### Phase 1: Batch Intake & Triage
1. Read candidate files from `storage/raw_buffer/` or the target recipe.
2. Scout Agent performs heuristic triage, discarding boilerplate and noise.
3. Select the target batch size (e.g. 10 candidate problems).

---

### Phase 2: Autonomous Multi-Agent Kaizen Loop
For each candidate item, execute the following enclosed loop in the background:

1. **Extractor Agent**:
   - Parses unstructured markdown / notebook / SQL into the recipe's `target_schema`.
   - Isolates `setup_ddl` from `solution_sql`.
2. **Curator Agent (DuckDB Sandbox)**:
   - Spawns in-memory DuckDB sandbox.
   - Executes DDL + Solution SQL.
   - If execution fails, returns error trace to Extractor for autonomous self-correction (up to 2 retries).
3. **LanceDB Vector Deduplication**:
   - Computes embedding with `sentence-transformers`.
   - Checks cosine distance. If `< 0.15`, merges source attribution and skips duplicate insertion.
4. **DuckDB Vault Storage**:
   - Inserts validated, unique record into `storage/vault.duckdb`.

---

### Phase 3: Macro Batch Review
Once all items in the batch are processed:
1. Generate a unified Markdown summary table showing:
   - Item ID / Title
   - Difficulty & Dialect
   - DuckDB Sandbox Status (`PASS` / `FAIL`)
   - LanceDB Deduplication Action (`INSERTED` / `DEDUP_MERGED`)
2. Present prompt:
   > "Batch processing complete. [N] records harvested and stored in DuckDB vault. Options:
   > [1] Process Next Batch
   > [2] View Vault Statistics (`cli.py stats`)
   > [3] Export to JSONL / Parquet
   > [4] Done for now"
