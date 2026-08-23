from pathlib import Path

import pytest

from core.memory.duckdb_store import DuckDBStore
from core.memory.lancedb_store import LanceDBStore
from core.schemas import (
    CuratedRecord,
    DifficultyLevel,
    HarvestRunStats,
    SQLDialect,
)


class TestDuckDBStore:
    @pytest.fixture
    def duck_store(self, tmp_path: Path):
        db_file = str(tmp_path / "test_vault.duckdb")
        store = DuckDBStore(db_path=db_file)
        yield store
        store.close()

    def test_insert_and_get_challenge(self, duck_store: DuckDBStore, sample_curated_record: CuratedRecord):
        rec_id = duck_store.insert_challenge(sample_curated_record)
        assert rec_id == sample_curated_record.record_id

        retrieved = duck_store.get_challenge(rec_id)
        assert retrieved is not None
        assert retrieved.title == sample_curated_record.title
        assert retrieved.problem_statement == sample_curated_record.problem_statement
        assert retrieved.difficulty == DifficultyLevel.MEDIUM
        assert retrieved.dialect == SQLDialect.DUCKDB
        assert retrieved.quality_score == pytest.approx(sample_curated_record.quality_score)

    def test_merge_source_url(self, duck_store: DuckDBStore, sample_curated_record: CuratedRecord):
        rec_id = duck_store.insert_challenge(sample_curated_record)
        assert len(sample_curated_record.source_urls) == 1

        duck_store.merge_source(rec_id, "https://github.com/datalemur/problems")
        retrieved = duck_store.get_challenge(rec_id)
        assert len(retrieved.source_urls) == 2
        assert "https://github.com/datalemur/problems" in retrieved.source_urls

        # Duplicate merge should not add again
        duck_store.merge_source(rec_id, "https://github.com/datalemur/problems")
        retrieved_again = duck_store.get_challenge(rec_id)
        assert len(retrieved_again.source_urls) == 2

    def test_vault_stats_aggregation(self, duck_store: DuckDBStore):
        rec1 = CuratedRecord(
            domain="sql",
            title="Problem 1",
            problem_statement="Desc 1",
            difficulty=DifficultyLevel.EASY,
            dialect=SQLDialect.POSTGRESQL,
            category="Basics",
        )
        rec2 = CuratedRecord(
            domain="sql",
            title="Problem 2",
            problem_statement="Desc 2",
            difficulty=DifficultyLevel.HARD,
            dialect=SQLDialect.DUCKDB,
            category="Window Functions",
        )
        rec3 = CuratedRecord(
            domain="sql",
            title="Problem 3",
            problem_statement="Desc 3",
            difficulty=DifficultyLevel.EASY,
            dialect=SQLDialect.POSTGRESQL,
            category="Basics",
        )

        duck_store.insert_challenge(rec1)
        duck_store.insert_challenge(rec2)
        duck_store.insert_challenge(rec3)

        stats = duck_store.get_stats()
        assert stats["total_challenges"] == 3
        assert stats["by_difficulty"]["Easy"] == 2
        assert stats["by_difficulty"]["Hard"] == 1
        assert stats["by_dialect"]["PostgreSQL"] == 2
        assert stats["by_dialect"]["DuckDB"] == 1
        assert stats["by_category"]["Basics"] == 2

    def test_export_jsonl_and_parquet(
        self, duck_store: DuckDBStore, sample_curated_record: CuratedRecord, tmp_path: Path
    ):
        duck_store.insert_challenge(sample_curated_record)

        jsonl_out = str(tmp_path / "exports" / "challenges.jsonl")
        parquet_out = str(tmp_path / "exports" / "challenges.parquet")

        duck_store.export_jsonl(jsonl_out)
        duck_store.export_parquet(parquet_out)

        assert Path(jsonl_out).exists()
        assert Path(parquet_out).exists()
        assert Path(jsonl_out).stat().st_size > 0
        assert Path(parquet_out).stat().st_size > 0

    def test_harvest_run_telemetry(self, duck_store: DuckDBStore):
        run = HarvestRunStats(
            recipe_name="SQL Vault",
            total_scanned=50,
            total_extracted=20,
            total_deduped=5,
            total_saved=15,
            status="completed",
        )
        duck_store.record_harvest_run(run)

        # Update telemetry
        run.total_saved = 16
        duck_store.record_harvest_run(run)


class TestLanceDBStore:
    @pytest.fixture
    def lancedb_store(self, tmp_path: Path):
        db_dir = str(tmp_path / "lancedb_test")
        return LanceDBStore(db_path=db_dir, table_name="test_challenges_vector")

    def test_embed_text_dimensions(self, lancedb_store: LanceDBStore):
        vector = lancedb_store.embed_text("Write a query to calculate second highest salary")
        assert isinstance(vector, list)
        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)

    def test_empty_table_deduplication(self, lancedb_store: LanceDBStore):
        vector = lancedb_store.embed_text("Sample problem")
        is_dup, match_id, distance = lancedb_store.is_duplicate(vector)
        assert is_dup is False
        assert match_id is None
        assert distance == 1.0

    def test_add_and_near_duplicate_detection(self, lancedb_store: LanceDBStore):
        text1 = "Write a SQL query to get the second highest salary from the Employee table."
        vec1 = lancedb_store.embed_text(text1)
        lancedb_store.add_record(record_id="rec-001", vector=vec1, source_url="https://github.com/source1", text=text1)
        assert lancedb_store.count() == 1

        # Identical text check
        is_dup, match_id, distance = lancedb_store.is_duplicate(vec1, threshold=0.15)
        assert is_dup is True
        assert match_id == "rec-001"
        assert distance < 0.05

        # Paraphrased version
        text2 = "Find the 2nd highest salary of employees in Employee table."
        vec2 = lancedb_store.embed_text(text2)
        is_dup2, match_id2, dist2 = lancedb_store.is_duplicate(vec2, threshold=0.25)
        assert is_dup2 is True
        assert match_id2 == "rec-001"
        assert dist2 < 0.25

    def test_distinct_problem_is_not_duplicate(self, lancedb_store: LanceDBStore):
        text1 = "Write a SQL query to find second highest salary."
        vec1 = lancedb_store.embed_text(text1)
        lancedb_store.add_record(record_id="rec-001", vector=vec1, source_url="https://github.com/source1")

        # Completely unrelated problem
        text3 = "Find all users who placed more than 5 orders in December 2024 using window functions."
        vec3 = lancedb_store.embed_text(text3)
        is_dup, match_id, distance = lancedb_store.is_duplicate(vec3, threshold=0.15)
        assert is_dup is False
        assert distance > 0.35
