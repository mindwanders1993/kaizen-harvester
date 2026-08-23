import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DifficultyLevel(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    UNKNOWN = "Unknown"


class SQLDialect(str, Enum):
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    DUCKDB = "DuckDB"
    SPARK_SQL = "Spark SQL"
    SNOWFLAKE = "Snowflake"
    BIGQUERY = "BigQuery"
    MULTI_DIALECT = "Multi-dialect"


class HarvestRecipe(BaseModel):
    name: str = Field(..., description="Human-readable title of the harvesting vault")
    domain: str = Field(..., description="Target domain identifier, e.g. 'sql'")
    description: str | None = Field(None, description="Optional recipe overview")
    sources: dict[str, list[str]] = Field(
        default_factory=dict, description="Source targets (github_queries, direct_repos, etc.)"
    )
    filters: dict[str, Any] = Field(
        default_factory=dict, description="Ingress filters (min_stars, exclude_paths, etc.)"
    )
    target_schema: dict[str, str] = Field(default_factory=dict, description="Expected schema fields and types/enums")


class RawArtifact(BaseModel):
    file_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the raw artifact"
    )
    source_url: str = Field(..., description="Origin repository or web URL")
    file_path: str = Field(..., description="Relative or absolute file path within source")
    content: str = Field(..., description="Raw text, SQL, or notebook content")
    format: str = Field(..., description="Format category: 'sql', 'markdown', 'jupyter', or 'code'")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional provenance metadata")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        valid_formats = {"sql", "markdown", "jupyter", "code"}
        if v.lower() not in valid_formats:
            raise ValueError(f"Invalid format '{v}'. Must be one of {valid_formats}")
        return v.lower()


class ScoutResult(BaseModel):
    reasoning: str = Field(..., description="REACT step: Explicit chain-of-thought analysis of file relevance")
    is_candidate: bool = Field(..., description="True if the artifact contains domain challenge content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    primary_format: str = Field(..., description="Detected format ('sql', 'markdown', 'jupyter', 'code')")
    reason: str | None = Field(None, description="Short summary reason for triage decision")


class ExtractedRecord(BaseModel):
    data: dict[str, Any] = Field(..., description="Structured dictionary conforming to recipe target_schema")
    source_url: str = Field(..., description="Origin repository URL or source identifier")
    raw_content_hash: str | None = Field(None, description="SHA256 hash of raw source content for verification")
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of extraction"
    )


class CuratedRecord(BaseModel):
    record_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Primary identifier for the challenge"
    )
    domain: str = Field(..., description="Domain identifier (e.g. 'sql')")
    title: str = Field(..., description="Challenge title")
    problem_statement: str = Field(..., description="Markdown problem statement")
    setup_ddl: str | None = Field(None, description="Clean DDL script for table setup and mock data")
    solution_sql: str | None = Field(None, description="Ground truth solution SQL query")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.UNKNOWN, description="Assigned difficulty level")
    dialect: SQLDialect = Field(default=SQLDialect.DUCKDB, description="SQL dialect compatibility")
    category: str | None = Field(None, description="Topic or category (e.g. CTEs, Window Functions)")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    source_urls: list[str] = Field(default_factory=list, description="List of source URLs where this problem was found")
    sandbox_output: str | None = Field(None, description="Preview of execution output from DuckDB sandbox")
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Quality rating score")
    retry_count: int = Field(default=0, ge=0, description="Number of self-correction retries during curation")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    vector_embedding: list[float] | None = Field(None, description="Dense vector embedding for deduplication")


# VaultRecord is the persistent representation in DuckDB
VaultRecord = CuratedRecord


class HarvestRunStats(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique run identifier")
    recipe_name: str = Field(..., description="Recipe name being executed")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Start timestamp")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    total_scanned: int = Field(default=0, ge=0, description="Total files scanned by ingress/scout")
    total_extracted: int = Field(default=0, ge=0, description="Total candidates successfully extracted")
    total_deduped: int = Field(default=0, ge=0, description="Total duplicate candidates discarded/merged")
    total_saved: int = Field(default=0, ge=0, description="Total unique records saved to vault")
    status: str = Field(default="running", description="Status ('running', 'completed', 'failed')")
