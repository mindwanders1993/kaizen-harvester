from core.agents.base import LLMClientWrapper
from core.agents.curator import CuratorAgent
from core.agents.extractor import ExtractorAgent
from core.agents.scout import ScoutAgent
from core.schemas import (
    DifficultyLevel,
    ExtractedRecord,
    RawArtifact,
    SQLDialect,
)


class TestScoutAgent:
    def test_heuristic_rejection_license_and_configs(self):
        scout = ScoutAgent()

        license_art = RawArtifact(
            source_url="https://github.com/test",
            file_path="LICENSE",
            content="MIT License Copyright (c) 2026",
            format="code",
        )
        res = scout.triage(license_art)
        assert res.is_candidate is False
        assert res.confidence == 1.0

        pkg_art = RawArtifact(
            source_url="https://github.com/test",
            file_path="package.json",
            content='{"name": "test-pkg"}',
            format="code",
        )
        res2 = scout.triage(pkg_art)
        assert res2.is_candidate is False

    def test_heuristic_rejection_vendor_path(self):
        scout = ScoutAgent()
        vendor_art = RawArtifact(
            source_url="https://github.com/test",
            file_path="node_modules/lodash/index.js",
            content="module.exports = {};",
            format="code",
        )
        res = scout.triage(vendor_art)
        assert res.is_candidate is False

    def test_heuristic_candidate_sql(self, sample_raw_sql: RawArtifact):
        scout = ScoutAgent()
        res = scout.triage(sample_raw_sql)
        assert res.is_candidate is True
        assert res.confidence >= 0.90
        assert res.primary_format == "sql"

    def test_heuristic_candidate_markdown(self, sample_raw_md: RawArtifact):
        scout = ScoutAgent()
        res = scout.triage(sample_raw_md)
        assert res.is_candidate is True
        assert res.confidence >= 0.90
        assert res.primary_format == "markdown"

    def test_llm_triage_ambiguous_file(self, mock_llm):
        wrapper = LLMClientWrapper(mock_client=mock_llm)
        scout = ScoutAgent(llm_client=wrapper)

        ambiguous_art = RawArtifact(
            source_url="https://github.com/test",
            file_path="notes/interview_prep.txt",
            content="Some interview notes discussing window functions and salary ranking algorithms.",
            format="code",
        )
        res = scout.triage(ambiguous_art)
        assert res.is_candidate is True
        assert len(res.reasoning) > 0


class TestExtractorAgent:
    def test_preprocess_jupyter_notebook(self, sample_raw_nb: RawArtifact):
        extractor = ExtractorAgent()
        preprocessed = extractor._preprocess_content(sample_raw_nb)
        assert "<!-- Markdown -->" in preprocessed
        assert "```sql" in preprocessed
        assert "CREATE TABLE Employee" in preprocessed

    def test_extract_sql_artifact_with_mock_llm(self, sample_raw_sql: RawArtifact, mock_llm):
        wrapper = LLMClientWrapper(mock_client=mock_llm)
        extractor = ExtractorAgent(llm_client=wrapper)

        extracted = extractor.extract(sample_raw_sql)
        assert isinstance(extracted, ExtractedRecord)
        assert extracted.source_url == sample_raw_sql.source_url
        assert "title" in extracted.data
        assert "setup_ddl" in extracted.data
        assert "solution_sql" in extracted.data
        assert extracted.raw_content_hash is not None


class TestCuratorAgent:
    def test_sandbox_execution_success(self):
        curator = CuratorAgent()
        ddl = "CREATE TABLE Users (id INT, name VARCHAR); INSERT INTO Users VALUES (1, 'Alice'), (2, 'Bob');"
        sql = "SELECT * FROM Users WHERE id = 1;"

        success, preview, error = curator.verify_sql_sandbox(ddl, sql)
        assert success is True
        assert error is None
        assert preview is not None
        assert "Alice" in preview

    def test_sandbox_execution_syntax_error(self):
        curator = CuratorAgent()
        ddl = "CREATE TABLE Users (id INT);"
        sql = "SELECT invalid_column_xyz FROM NonExistentTable;"

        success, preview, error = curator.verify_sql_sandbox(ddl, sql)
        assert success is False
        assert preview is None
        assert (
            "Table with name NonExistentTable does not exist" in error
            or "Binder Error" in error
            or "does not exist" in error
        )

    def test_classify_difficulty_levels(self):
        curator = CuratorAgent()

        easy_sql = "SELECT id, name FROM employees WHERE status = 'active';"
        assert curator.classify_difficulty(easy_sql) == DifficultyLevel.EASY

        med_sql = "SELECT dept, AVG(salary) FROM employees GROUP BY dept HAVING COUNT(*) > 5;"
        assert curator.classify_difficulty(med_sql) == DifficultyLevel.MEDIUM

        hard_sql = "SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk FROM employees;"
        assert curator.classify_difficulty(hard_sql) == DifficultyLevel.HARD

    def test_curate_valid_record(self):
        curator = CuratorAgent()
        extracted = ExtractedRecord(
            data={
                "title": "Calculate Employee Salary",
                "problem_statement": "Find highest salary.",
                "setup_ddl": "CREATE TABLE Emp (id INT, sal INT); INSERT INTO Emp VALUES (1, 5000);",
                "solution_sql": "SELECT MAX(sal) AS max_sal FROM Emp;",
                "category": "Aggregations",
                "tags": ["max", "sql"],
            },
            source_url="https://github.com/test/repo",
        )

        curated = curator.curate(extracted)
        assert curated is not None
        assert curated.title == "Calculate Employee Salary"
        assert curated.difficulty == DifficultyLevel.EASY
        assert curated.dialect == SQLDialect.DUCKDB
        assert curated.quality_score == 1.0
        assert "5000" in curated.sandbox_output

    def test_curate_invalid_record_returns_none(self):
        curator = CuratorAgent()
        extracted = ExtractedRecord(
            data={
                "title": "Broken Challenge",
                "problem_statement": "Broken SQL query test",
                "setup_ddl": "CREATE TABLE T (x INT);",
                "solution_sql": "SELECT y FROM T WHERE z = 100;",  # columns y, z don't exist
            },
            source_url="https://github.com/test/repo",
        )

        curated = curator.curate(extracted)
        assert curated is None
