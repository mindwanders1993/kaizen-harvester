---
name: test
description: Test orchestration skill for Kaizen Harvester. Covers unit testing, agent mock execution, DuckDB sandboxing, and LanceDB vector deduplication verification.
---

# Kaizen Harvester Test Orchestration Skill (`test`)

## 🎯 Purpose
Run, diagnose, and manage the full test suite for Kaizen Harvester:
- Ingress fetcher mocks and rate-limit backoff tests.
- Agent swarm parsing and schema extraction tests.
- DuckDB SQL execution and sandboxing verification.
- LanceDB vector similarity distance and deduplication threshold tests.

All commands should be executed from the **project root**: `/Users/mrrobot/Desktop/Projects/kaizen-harvester`.

---

## 🧪 Test Execution Commands

### 1. Run Full Test Suite:
```bash
source venv/bin/activate && pytest
```

### 2. Run with Verbose Output & Tracebacks:
```bash
source venv/bin/activate && pytest -vv --tb=short
```

### 3. Run Specific Subsystem Tests:
```bash
# Ingress tests
source venv/bin/activate && pytest tests/test_ingress.py -v

# Agent Swarm tests (Scout, Extractor, Curator)
source venv/bin/activate && pytest tests/test_agents.py -v

# Storage & Deduplication tests (LanceDB & DuckDB)
source venv/bin/activate && pytest tests/test_memory.py -v
```

---

## 🔍 Common Diagnostics

### Linting & Formatting Issues:
```bash
source venv/bin/activate && ruff check --fix . && ruff format .
```

### LanceDB / Vector Mocks:
Tests should mock heavy embedding calls or use lightweight test embeddings (e.g. dummy 384-dimensional vectors) during CI/CD to prevent network latency.

### DuckDB Sandbox Isolation:
Ensure all DuckDB tests execute against in-memory instances (`duckdb.connect(":memory:")`) to avoid mutating `storage/vault.duckdb`.
