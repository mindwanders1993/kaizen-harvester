# 📜 Declarative Harvesting Recipes Guide

## 1. Overview

In **Kaizen Harvester**, all knowledge extraction jobs are defined declaratively using **Harvesting Recipes** (`recipes/*.yaml`). 

A recipe specifies:
1. **Metadata**: The vault name, domain identifier, and purpose.
2. **Sources**: Where the Ingress Mesh should look (GitHub queries, direct Git repository URLs, web documentation URLs, or local directory paths).
3. **Ingress Filters**: Rules for file extensions, minimum repository stars, and path exclusions.
4. **Target Schema**: The exact structured fields, types, and enumerated constraints that the Extractor and Curator agents must produce.

---

## 2. Recipe Specification & Schema Definition

A standard recipe file uses standard YAML with the following top-level keys:

```yaml
# 1. Metadata
name: "SQL Challenges Vault"          # Human-readable title
domain: "sql"                         # Domain identifier (used in database indexing)
description: "Ingests SQL problems"   # Optional descriptive overview

# 2. Ingress Sources
sources:
  github_queries:
    - "topic:sql-interview-questions stars:>10"
    - "topic:leetcode-sql stars:>20"
  direct_repos:
    - "https://github.com/faizanxmulla/sql-portfolio.git"
    - "https://github.com/shawlu95/Beyond-LeetCode-SQL.git"
  file_patterns:
    - "*.sql"
    - "*.md"
    - "*.ipynb"

# 3. Ingress Filtering Rules
filters:
  min_stars: 10
  exclude_paths:
    - "node_modules/**"
    - "vendor/**"
    - ".git/**"

# 4. Target Extraction Schema
target_schema:
  title: string
  problem_statement: string
  setup_ddl: string
  solution_sql: string
  dialect: enum[PostgreSQL, MySQL, DuckDB, Spark SQL]
  difficulty: enum[Easy, Medium, Hard]
  tags: list[string]
```

---

## 3. Supported Schema Field Types

The Extractor and Curator agents parse the `target_schema` map and enforce type validation on all extracted JSON records:

| Schema Type | Description | Example Extracted Value |
|:---|:---|:---|
| `string` | Single-line or short text string | `"Second Highest Salary"` |
| `text` | Multi-line formatted markdown or text block | `"Write an SQL query to report the second highest salary..."` |
| `enum[...]` | Strict categorical choice from a defined list | `enum[PostgreSQL, MySQL, DuckDB]` -> `"PostgreSQL"` |
| `list[string]` | Array of strings | `["window-functions", "cte", "ranking"]` |
| `integer` | Numerical whole number | `42` |
| `float` | Floating-point decimal value | `0.95` |
| `boolean` | True / False indicator | `true` |

---

## 4. Production Recipe Examples

### Example 1: SQL Challenges Vault (`recipes/sql_challenges.yaml`)

This recipe targets SQL interview questions and platform solutions:

```yaml
name: "SQL Challenges Vault"
domain: "sql"
sources:
  github_queries:
    - "topic:sql-interview-questions stars:>10"
    - "path:*.sql 'OVER (PARTITION BY' stars:>15"
  direct_repos:
    - "https://github.com/faizanxmulla/sql-portfolio.git"
    - "https://github.com/quantumudit/DataLemur-SQL-Challenges.git"
    - "https://github.com/TeslaNik/stratascratch-SQL.git"
target_schema:
  title: string
  problem_statement: string
  setup_ddl: string
  solution_sql: string
  dialect: enum[PostgreSQL, MySQL, DuckDB, Spark SQL]
  difficulty: enum[Easy, Medium, Hard]
  category: enum[CTEs, Window Functions, Aggregations, Joins, Date/Time, Gaps & Islands]
```

---

### Example 2: Data Engineering Patterns Vault (`recipes/data_engineering.yaml`)

This recipe harvests production Data Engineering snippets, PySpark optimizations, and Medallion architecture patterns:

```yaml
name: "Data Engineering Architecture Patterns"
domain: "data_engineering"
sources:
  github_queries:
    - "topic:pyspark-recipes stars:>25"
    - "topic:delta-lake-patterns stars:>15"
  file_patterns:
    - "*.py"
    - "*.ipynb"
    - "*.md"
target_schema:
  pattern_name: string
  framework: enum[PySpark, Spark SQL, DuckDB, Polars, dbt]
  problem_context: string
  code_snippet: string
  complexity: enum[Intermediate, Advanced, Production-Critical]
  tags: list[string]
```

---

### Example 3: System Design & Architecture Vault (`recipes/system_design.yaml`)

This recipe ingests high-scale architectural decision records, system design case studies, and trade-off analyses:

```yaml
name: "System Design & Architecture Playbook"
domain: "system_design"
sources:
  github_queries:
    - "topic:system-design-case-studies stars:>50"
target_schema:
  system_name: string
  core_requirements: string
  architecture_diagram_desc: string
  data_storage_strategy: string
  scaling_bottlenecks: string
  trade_offs: string
```

---

## 5. Executing and Validating Recipes via CLI

To inspect a recipe and view its source discovery plan and target schema in the terminal before execution:

```bash
python cli.py run --recipe recipes/sql_challenges.yaml
```

The CLI renders formatted tables summarizing the plan:

```
╭───────────────── Initializing Sovereign Knowledge Harvester ─────────────────╮
│ Target: SQL Challenges Vault (sql)                                            │
╰───────────────────────────────────────────────────────────────────────────────╯
                                 Harvest Sources                                 
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Source Type         ┃ Target/Query                                           ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Github Queries      │ topic:sql-interview-questions stars:>10                │
└─────────────────────┴────────────────────────────────────────────────────────┘
                           Target Schema (Extraction Goal)                       
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field               ┃ Type/Enum                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ title               │ string                                                 │
│ problem_statement   │ string                                                 │
│ setup_ddl           │ string                                                 │
│ solution_sql        │ string                                                 │
│ dialect             │ enum[PostgreSQL, MySQL, DuckDB]                        │
│ difficulty          │ enum[Easy, Medium, Hard]                               │
└─────────────────────┴────────────────────────────────────────────────────────┘
```
