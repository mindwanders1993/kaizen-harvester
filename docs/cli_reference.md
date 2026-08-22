# 🖥️ CLI Reference & Operations Manual

## 1. Overview

The **Kaizen Harvester CLI** (`cli.py`) provides an intuitive, high-performance command-line interface built with `argparse` and `rich`. It manages harvesting jobs, displays formatted execution plans, inspects storage stats, and tracks agent telemetry.

---

## 2. Command Syntax & Options

```bash
python cli.py <action> [options]
```

### Supported Actions:

| Action | Description | Required Arguments |
|:---|:---|:---|
| `run` | Executes a harvesting workflow against a recipe. | `--recipe <path>` |
| `stats` | Displays statistics for the LanceDB vector store and DuckDB records. | None |

---

## 3. Command Breakdown

### 3.1 `run` Action

Executes the 3-stage harvesting pipeline: Ingress Mesh -> Agent Swarm -> Memory Vault.

```bash
python cli.py run --recipe recipes/sql_challenges.yaml
```

#### CLI Flags:

| Flag | Type | Description |
|:---|:---|:---|
| `--recipe` | `string` | **(Required)** Path to the YAML harvesting recipe file. |
| `--dry-run` | `flag` | Parses sources and displays candidate queue without executing LLM extraction or writing to databases. |
| `--limit` | `int` | Maximum number of items/files to harvest in a single run (useful for testing). |
| `--verbose` | `flag` | Enables debug logging for individual agent steps and network calls. |

#### Execution Output Flow:

1. **Header Panel**: Displays harvest target name and domain.
2. **Sources Table**: Lists all target GitHub queries, direct repos, and web URLs.
3. **Target Schema Table**: Summarizes expected JSON fields, types, and enums.
4. **Pipeline Step Indicators**:
   - `Step 1: Starting Ingress Mesh...`
   - `Step 2: Spinning up Agent Swarm...`
   - `Step 3: Checking LanceDB Vault...`
5. **Completion Summary**: Reports harvested, deduplicated, and stored record counts.

---

### 3.2 `stats` Action

Provides an instant health check and summary of stored knowledge assets.

```bash
python cli.py stats
```

#### Sample Output:

```
╭──────────────── Vault Statistics ────────────────╮
│ LanceDB: 1,420 vectors                           │
│ DuckDB:  1,420 records (SQL Challenges)          │
│ Breakdown:                                       │
│   • Easy:   412                                  │
│   • Medium: 718                                  │
│   • Hard:   290                                  │
╰──────────────────────────────────────────────────╯
```

---

## 4. Environment Variables

Kaizen Harvester uses standard environment variables for API authentication and storage paths:

| Variable | Description | Default |
|:---|:---|:---|
| `OPENAI_API_KEY` | OpenAI API key (for GPT-4o / embeddings) | None |
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude 3.7 Sonnet) | None |
| `GITHUB_TOKEN` | GitHub Personal Access Token (for rate limits up to 5,000 req/hr) | None |
| `HARVESTER_STORAGE_DIR` | Custom directory for databases & vectors | `./storage` |
| `EMBEDDING_MODEL` | Hugging Face / SentenceTransformer model name | `all-MiniLM-L6-v2` |

---

## 5. Exit Codes & Error Handling

| Exit Code | Reason | Resolution |
|:---|:---|:---|
| `0` | Success | Normal termination. |
| `1` | Invalid Recipe / Missing Argument | Check `--recipe` path or YAML syntax in recipe file. |
| `2` | API Rate Limit / Network Failure | Verify `GITHUB_TOKEN` or network connectivity. |
| `3` | Database / Storage Failure | Check write permissions in `storage/` directory. |
