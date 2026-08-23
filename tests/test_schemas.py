import pytest
from pydantic import ValidationError

from core.schemas import (
    CuratedRecord,
    DifficultyLevel,
    ExtractedRecord,
    HarvestRecipe,
    HarvestRunStats,
    RawArtifact,
    ScoutResult,
    SQLDialect,
)


class TestHarvestRecipeSchema:
    def test_valid_recipe_creation(self, sample_recipe: HarvestRecipe):
        assert sample_recipe.name == "SQL Challenges Vault"
        assert sample_recipe.domain == "sql"
        assert "github_queries" in sample_recipe.sources
        assert sample_recipe.filters["min_stars"] == 10
        assert "title" in sample_recipe.target_schema

    def test_missing_required_fields_raises_error(self):
        with pytest.raises(ValidationError):
            HarvestRecipe(name="Incomplete Recipe")  # missing domain


class TestRawArtifactSchema:
    def test_valid_raw_artifacts(
        self,
        sample_raw_sql: RawArtifact,
        sample_raw_md: RawArtifact,
        sample_raw_nb: RawArtifact,
    ):
        assert sample_raw_sql.format == "sql"
        assert sample_raw_md.format == "markdown"
        assert sample_raw_nb.format == "jupyter"
        assert len(sample_raw_sql.file_id) > 0
        assert "CREATE TABLE" in sample_raw_sql.content

    def test_invalid_format_raises_error(self):
        with pytest.raises(ValidationError):
            RawArtifact(
                source_url="https://github.com/test",
                file_path="test.xyz",
                content="test content",
                format="unsupported_binary",
            )


class TestScoutResultSchema:
    def test_valid_scout_result(self):
        res = ScoutResult(
            reasoning="File contains problem statement and SQL query.",
            is_candidate=True,
            confidence=0.92,
            primary_format="sql",
            reason="Clear problem structure",
        )
        assert res.is_candidate is True
        assert res.confidence == 0.92
        assert len(res.reasoning) > 0

    def test_confidence_out_of_bounds_raises_error(self):
        with pytest.raises(ValidationError):
            ScoutResult(
                reasoning="test",
                is_candidate=True,
                confidence=1.5,  # must be <= 1.0
                primary_format="sql",
            )

        with pytest.raises(ValidationError):
            ScoutResult(
                reasoning="test",
                is_candidate=True,
                confidence=-0.1,  # must be >= 0.0
                primary_format="sql",
            )

    def test_missing_reasoning_violates_react_contract(self):
        with pytest.raises(ValidationError):
            ScoutResult(
                is_candidate=True,
                confidence=0.8,
                primary_format="sql",
            )


class TestExtractedRecordSchema:
    def test_valid_extracted_record(self):
        record = ExtractedRecord(
            data={
                "title": "Two Sum",
                "difficulty": "Easy",
                "solution_sql": "SELECT 1;",
            },
            source_url="https://github.com/mock/repo",
            raw_content_hash="abc123hash",
        )
        assert record.data["title"] == "Two Sum"
        assert record.source_url == "https://github.com/mock/repo"
        assert record.raw_content_hash == "abc123hash"
        assert record.extracted_at is not None


class TestCuratedRecordSchema:
    def test_valid_curated_record(self, sample_curated_record: CuratedRecord):
        assert sample_curated_record.domain == "sql"
        assert sample_curated_record.title == "Second Highest Salary"
        assert sample_curated_record.difficulty == DifficultyLevel.MEDIUM
        assert sample_curated_record.dialect == SQLDialect.DUCKDB
        assert sample_curated_record.quality_score == 0.98
        assert sample_curated_record.retry_count == 0
        assert len(sample_curated_record.tags) == 3

    def test_serialization_and_deserialization(self, sample_curated_record: CuratedRecord):
        json_data = sample_curated_record.model_dump()
        reconstructed = CuratedRecord.model_validate(json_data)
        assert reconstructed.record_id == sample_curated_record.record_id
        assert reconstructed.title == sample_curated_record.title
        assert reconstructed.difficulty == sample_curated_record.difficulty


class TestHarvestRunStatsSchema:
    def test_harvest_run_stats_defaults(self):
        stats = HarvestRunStats(recipe_name="SQL Challenges Vault")
        assert stats.recipe_name == "SQL Challenges Vault"
        assert stats.total_scanned == 0
        assert stats.total_saved == 0
        assert stats.status == "running"
        assert stats.started_at is not None
        assert stats.completed_at is None
