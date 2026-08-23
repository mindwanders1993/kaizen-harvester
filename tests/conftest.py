from pathlib import Path
from typing import Any, TypeVar

import duckdb
import pytest
from pydantic import BaseModel

from core.schemas import (
    CuratedRecord,
    DifficultyLevel,
    ExtractedRecord,
    HarvestRecipe,
    RawArtifact,
    ScoutResult,
    SQLDialect,
)

MOCK_DATA_DIR = Path(__file__).parent / "mock_data"

T = TypeVar("T", bound=BaseModel)


class MockLLMClient:
    """Deterministic Mock LLM Client for testing Scout, Extractor, and Curator agents without live API calls."""

    def __init__(self, default_response: Any = None):
        self.default_response = default_response
        self.call_history = []

    def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        override_data: dict[str, Any] = None,
    ) -> T:
        self.call_history.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model,
            }
        )

        if override_data:
            return response_model.model_validate(override_data)

        if self.default_response:
            if isinstance(self.default_response, response_model):
                return self.default_response
            if isinstance(self.default_response, dict):
                return response_model.model_validate(self.default_response)

        # Default fallback responses per model type
        if response_model == ScoutResult:
            return ScoutResult(
                reasoning="Mock chain-of-thought analysis: Content has SQL problem headers and DDL.",
                is_candidate=True,
                confidence=0.95,
                primary_format="sql",
                reason="Valid SQL interview problem found",
            )

        if response_model == ExtractedRecord:
            return ExtractedRecord(
                data={
                    "title": "Mock Second Highest Salary",
                    "problem_statement": "Write a SQL query to get the second highest salary.",
                    "setup_ddl": "CREATE TABLE Employee (id INT, salary INT); INSERT INTO Employee VALUES (1, 100), (2, 200);",
                    "solution_sql": "SELECT MAX(salary) FROM Employee WHERE salary < (SELECT MAX(salary) FROM Employee);",
                    "dialect": "PostgreSQL",
                    "difficulty": "Medium",
                },
                source_url="https://github.com/mock/repo",
            )

        from core.agents.extractor import RawExtractionPayload

        if response_model == RawExtractionPayload:
            return RawExtractionPayload(
                title="Mock Second Highest Salary",
                problem_statement="Write a SQL query to get the second highest salary.",
                setup_ddl="CREATE TABLE Employee (id INT, salary INT); INSERT INTO Employee VALUES (1, 100), (2, 200);",
                solution_sql="SELECT MAX(salary) FROM Employee WHERE salary < (SELECT MAX(salary) FROM Employee);",
                dialect="DuckDB",
                difficulty="Medium",
                category="Aggregations",
                tags=["salary", "max"],
            )

        raise ValueError(f"No mock handler configured for response model: {response_model}")


@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def test_db() -> duckdb.DuckDBPyConnection:
    """Provides a fresh, ephemeral in-memory DuckDB connection with initialized schemas."""
    con = duckdb.connect(database=":memory:")
    con.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id VARCHAR PRIMARY KEY,
            domain VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            problem_statement TEXT NOT NULL,
            setup_ddl TEXT,
            solution_sql TEXT,
            difficulty VARCHAR,
            dialect VARCHAR,
            category VARCHAR,
            tags VARCHAR[],
            source_urls VARCHAR[],
            sandbox_output TEXT,
            quality_score FLOAT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS harvest_runs (
            run_id VARCHAR PRIMARY KEY,
            recipe_name VARCHAR,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_scanned INTEGER DEFAULT 0,
            total_extracted INTEGER DEFAULT 0,
            total_deduped INTEGER DEFAULT 0,
            total_saved INTEGER DEFAULT 0,
            status VARCHAR DEFAULT 'running'
        );
    """)
    yield con
    con.close()


@pytest.fixture
def sample_recipe() -> HarvestRecipe:
    return HarvestRecipe(
        name="SQL Challenges Vault",
        domain="sql",
        description="Ingest SQL practice problems",
        sources={
            "github_queries": ["topic:sql-interview-questions stars:>10"],
            "direct_repos": ["https://github.com/faizanxmulla/sql-portfolio.git"],
        },
        filters={
            "min_stars": 10,
            "exclude_paths": ["node_modules/**", "vendor/**", ".git/**"],
        },
        target_schema={
            "title": "string",
            "problem_statement": "string",
            "setup_ddl": "string",
            "solution_sql": "string",
            "dialect": "enum[PostgreSQL, MySQL, DuckDB]",
            "difficulty": "enum[Easy, Medium, Hard]",
        },
    )


@pytest.fixture
def sample_raw_sql() -> RawArtifact:
    sql_path = MOCK_DATA_DIR / "sample_sql.sql"
    return RawArtifact(
        source_url="https://github.com/mock/sql-repo",
        file_path="problems/second_highest_salary.sql",
        content=sql_path.read_text(encoding="utf-8"),
        format="sql",
        metadata={"repo_stars": 150},
    )


@pytest.fixture
def sample_raw_md() -> RawArtifact:
    md_path = MOCK_DATA_DIR / "sample_md.md"
    return RawArtifact(
        source_url="https://github.com/mock/md-repo",
        file_path="challenges/consecutive_numbers.md",
        content=md_path.read_text(encoding="utf-8"),
        format="markdown",
        metadata={"repo_stars": 85},
    )


@pytest.fixture
def sample_raw_nb() -> RawArtifact:
    nb_path = MOCK_DATA_DIR / "sample_nb.ipynb"
    return RawArtifact(
        source_url="https://github.com/mock/nb-repo",
        file_path="notebooks/department_highest_salary.ipynb",
        content=nb_path.read_text(encoding="utf-8"),
        format="jupyter",
        metadata={"repo_stars": 420},
    )


@pytest.fixture
def sample_curated_record() -> CuratedRecord:
    return CuratedRecord(
        domain="sql",
        title="Second Highest Salary",
        problem_statement="Write a SQL query to get the second highest salary.",
        setup_ddl="CREATE TABLE Employee (id INT, salary INT); INSERT INTO Employee VALUES (1, 100), (2, 200), (3, 300);",
        solution_sql="SELECT MAX(salary) AS SecondHighestSalary FROM Employee WHERE salary < (SELECT MAX(salary) FROM Employee);",
        difficulty=DifficultyLevel.MEDIUM,
        dialect=SQLDialect.DUCKDB,
        category="Aggregations",
        tags=["subquery", "max", "salary"],
        source_urls=["https://github.com/faizanxmulla/sql-portfolio"],
        sandbox_output='[{"SecondHighestSalary": 200}]',
        quality_score=0.98,
        retry_count=0,
    )
