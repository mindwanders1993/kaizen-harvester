# 🧩 Kaizen Harvester: Low-Level Design (LLD)

This document provides the Low-Level Design (LLD) for Kaizen Harvester, detailing the core Pydantic data models, agent interfaces, prompt specifications, and database schemas required for implementation.

---

## 1. Core Data Models (`core/schemas.py`)

All cross-boundary data transfer is strictly typed using Pydantic models to ensure validation between the Ingress Mesh, Agent Swarm, and Storage Layer.

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class HarvestRecipe(BaseModel):
    name: str
    domain: str
    sources: Dict[str, List[str]]
    filters: Dict[str, Any]
    target_schema: Dict[str, str]

class RawArtifact(BaseModel):
    file_id: str
    source_url: str
    file_path: str
    content: str
    format: str # 'markdown', 'sql', 'jupyter'

class ScoutResult(BaseModel):
    is_candidate: bool
    confidence_score: float
    reason: str
    primary_format: str

class ExtractedRecord(BaseModel):
    # Dynamic fields generated based on recipe's target_schema
    # e.g., title, problem_statement, setup_ddl, solution_sql
    data: Dict[str, Any]
    source_url: str

class CuratedRecord(BaseModel):
    record_id: str
    domain: str
    extracted_data: ExtractedRecord
    difficulty: str
    dialect: str
    quality_score: float
    vector_embedding: Optional[List[float]] = None
```

---

## 2. Ingress Mesh Interfaces (`core/ingress/`)

### 2.1 `BaseFetcher` Protocol
All fetchers implement a standard interface for discovering and downloading artifacts.

```python
from typing import AsyncGenerator

class BaseFetcher:
    async def fetch(self, query: str, filters: dict) -> AsyncGenerator[RawArtifact, None]:
        """Yields RawArtifacts based on search parameters."""
        pass
```

### 2.2 GitHub Fetcher (`core/ingress/github.py`)
- **API**: `https://api.github.com/search/repositories?q={query}`
- **Pagination**: Uses link headers to paginate up to 1,000 results.
- **Cloning Strategy**: Uses `subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", url, tmp_dir])`.
- **File Extraction**: Walks `tmp_dir` for `*.md`, `*.sql`, `*.ipynb`. Drops `node_modules`, `vendor`.

### 2.3 Rate Limiter (`core/ingress/rate_limiter.py`)
- Implements a **Token Bucket** algorithm.
- `consume(tokens=1)` waits if bucket is empty.
- Handles `403 Rate Limit Exceeded` by parsing `x-ratelimit-reset` header and sleeping asynchronously.

---

## 3. Agent Swarm Implementation (`core/agents/`)

The agent swarm is implemented using the official OpenAI/Anthropic SDKs with structured outputs (JSON schema matching).

### 3.1 Scout Agent (`core/agents/scout.py`)

- **LLM Context Window Strategy**: Only sends the first 1,500 characters of a file to determine relevance (cost optimization).
- **Prompt Logic**:
  ```python
  def triage(artifact: RawArtifact) -> ScoutResult:
      prompt = f"""
      Evaluate this file for domain: {recipe.domain}.
      Is it a valid technical challenge/problem statement?
      File: {artifact.file_path}
      Content (Head): {artifact.content[:1500]}
      """
      # LLM call with response_format=ScoutResult
  ```

### 3.2 Extractor Agent (`core/agents/extractor.py`)

- **Dynamic Schema Binding**: Converts `recipe.target_schema` into a JSON Schema for the LLM `response_format` API.
- **AST/Notebook Parsing**: Before sending to the LLM, Jupyter notebooks are parsed via `json.loads` to strip outputs and base64 images, preserving only `source` arrays.

### 3.3 Curator Agent (`core/agents/curator.py`)

**DuckDB Sandbox Execution Loop**:
```python
import duckdb

def verify_sql(setup_ddl: str, solution_sql: str) -> bool:
    con = duckdb.connect(database=':memory:') # Ephemeral, zero side-effects
    try:
        # 1. Execute Schema & Mock Data
        con.execute(setup_ddl)
        
        # 2. Execute Solution Query
        # Wrap in a LIMIT to prevent memory exhaustion on Cartesian joins
        con.execute(f"SELECT * FROM ({solution_sql}) LIMIT 10")
        
        return True
    except Exception as e:
        raise SandBoxExecutionError(str(e))
    finally:
        con.close()
```

---

## 4. Storage & Memory Schemas (`core/memory/`)

### 4.1 LanceDB Vector Table Schema
```python
import pyarrow as pa

# LanceDB Schema
vector_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)), # MiniLM-L6-v2 dimensionality
    pa.field("source_url", pa.string())
])
```
- **Similarity Threshold**: `distance < 0.15` (Cosine).

### 4.2 DuckDB Vault Relational Schema
Stored in `storage/vault.duckdb`.

```sql
CREATE TABLE challenges (
    id UUID PRIMARY KEY,
    domain VARCHAR NOT NULL,
    
    -- Extracted Payload
    title VARCHAR,
    problem_statement TEXT,
    setup_ddl TEXT,
    solution_sql TEXT,
    
    -- Metadata & Enums
    difficulty VARCHAR CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    dialect VARCHAR,
    tags VARCHAR[],
    
    -- Telemetry
    source_urls VARCHAR[],
    quality_score FLOAT,
    created_at TIMESTAMP
);
```

---

## 5. Sequence Execution (CLI Orchestrator)

The CLI runner orchestrates the `asyncio` event loop:

1. `fetcher = GithubFetcher(token)`
2. `async for artifact in fetcher.fetch(recipe.sources['github_queries']):`
3. `scout_res = scout.triage(artifact)`
4. `if scout_res.is_candidate:`
5. `extracted = extractor.extract(artifact, recipe.target_schema)`
6. `verified = curator.verify(extracted)`
7. `if verified:`
8. `is_duplicate = memory.check_vector(verified)`
9. `if not is_duplicate: memory.store(verified)`

Concurrency is bounded using `asyncio.Semaphore(10)` to prevent overwhelming local memory and LLM rate limits.
