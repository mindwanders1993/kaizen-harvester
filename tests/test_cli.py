import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cli import (
    display_harvest_plan,
    display_run_summary,
    display_stats,
    load_recipe,
    run_pipeline,
)
from core.agents.base import LLMClientWrapper
from core.agents.curator import CuratorAgent
from core.agents.extractor import ExtractorAgent
from core.agents.scout import ScoutAgent
from core.memory.duckdb_store import DuckDBStore
from core.memory.lancedb_store import LanceDBStore
from core.schemas import HarvestRecipe, HarvestRunStats, RawArtifact


class TestCLI:
    def test_load_recipe_valid(self):
        recipe = load_recipe("recipes/sql_challenges.yaml")
        assert isinstance(recipe, HarvestRecipe)
        assert recipe.name == "SQL Challenges Vault"
        assert recipe.domain == "sql"

    def test_load_recipe_not_found(self):
        with pytest.raises(SystemExit):
            load_recipe("non_existent_recipe.yaml")

    def test_display_harvest_plan(self, sample_recipe: HarvestRecipe):
        display_harvest_plan(sample_recipe)

    def test_display_stats_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.duckdb")
            vector_path = os.path.join(tmp_dir, "lancedb")
            display_stats(db_path=db_path, vector_path=vector_path)

    def test_display_run_summary(self):
        stats = HarvestRunStats(
            recipe_name="Test Recipe",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            total_scanned=10,
            total_extracted=5,
            total_deduped=2,
            total_saved=3,
            status="completed",
        )
        display_run_summary(stats)

    @pytest.mark.asyncio
    async def test_run_pipeline_mocked(self, mock_llm):
        test_recipe = HarvestRecipe(
            name="Test SQL Recipe",
            domain="sql",
            sources={"github_queries": ["topic:sql"]},
            target_schema={
                "title": "string",
                "problem_statement": "string",
                "setup_ddl": "string",
                "solution_sql": "string",
            },
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.duckdb")
            vector_path = os.path.join(tmp_dir, "lancedb")

            duckdb_store = DuckDBStore(db_path=db_path)
            lancedb_store = LanceDBStore(db_path=vector_path)

            llm_wrapper = LLMClientWrapper(mock_client=mock_llm)
            scout = ScoutAgent(llm_client=llm_wrapper)
            extractor = ExtractorAgent(llm_client=llm_wrapper)
            curator = CuratorAgent(extractor=extractor)

            candidate_artifact = RawArtifact(
                source_url="https://github.com/mock/repo",
                file_path="problems/query.sql",
                content="-- Problem: Find 2nd highest salary\nCREATE TABLE Employee(id INT, salary INT);\nINSERT INTO Employee VALUES(1, 100);\nSELECT MAX(salary) FROM Employee;",
                format="sql",
            )
            license_artifact = RawArtifact(
                source_url="https://github.com/mock/repo",
                file_path="LICENSE",
                content="MIT License",
                format="code",
            )

            async def fake_fetch(*args, **kwargs):
                yield candidate_artifact
                yield license_artifact

            with patch("core.ingress.github.GithubFetcher.fetch", side_effect=fake_fetch):
                stats = await run_pipeline(
                    recipe=test_recipe,
                    limit=10,
                    concurrency=2,
                    db_path=db_path,
                    vector_path=vector_path,
                    scout_agent=scout,
                    extractor_agent=extractor,
                    curator_agent=curator,
                    duckdb_store=duckdb_store,
                    lancedb_store=lancedb_store,
                )

            assert stats.total_scanned == 2
            assert stats.total_extracted == 1
            assert stats.total_saved == 1
            assert stats.status == "completed"

            # Check persistence
            vault_stats = duckdb_store.get_stats()
            assert vault_stats["total_challenges"] == 1
            assert lancedb_store.count() == 1

            duckdb_store.close()
