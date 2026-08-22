---
name: dev_env
description: Standard operating procedures for configuring and diagnosing the Kaizen Harvester local runtime environment, API credentials, and storage directories.
---

# Kaizen Harvester Dev Environment Skill (`dev_env`)

## 🎯 Purpose
Use this skill to configure virtual environments, validate API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`), check local storage integrity (`storage/lancedb` and `storage/vault.duckdb`), and troubleshoot dependency issues.

---

## 🚀 Environment Setup

### 1. Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Required Environment Variables

Create or update `.env` in the project root:

```bash
# LLM Providers for Agent Swarm
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."

# GitHub API Token (increases rate limit from 60 to 5,000 req/hr)
GITHUB_TOKEN="ghp_..."

# Storage Config
HARVESTER_STORAGE_DIR="./storage"
```

---

## 🔍 Health & Storage Diagnostics

```bash
# 1. Check CLI status and record counts
python cli.py stats

# 2. Test recipe dry-run
python cli.py run --recipe recipes/sql_challenges.yaml

# 3. Verify DuckDB file integrity
python -c "import duckdb; con = duckdb.connect('storage/vault.duckdb'); print(con.execute('SHOW TABLES').fetchall())"

# 4. Verify LanceDB vector store
python -c "import lancedb; db = lancedb.connect('storage/lancedb'); print(db.table_names())"
```
