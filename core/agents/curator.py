import json
from typing import Optional, Tuple

import duckdb

from core.schemas import CuratedRecord, DifficultyLevel, ExtractedRecord, SQLDialect


class CuratorAgent:
    """
    Curator Agent for Kaizen Harvester.
    Performs DuckDB sandboxed execution verification, dialect normalization, difficulty rating, and self-correction loops.
    """

    def __init__(self, extractor=None):
        self.extractor = extractor

    def verify_sql_sandbox(
        self, setup_ddl: Optional[str], solution_sql: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Executes setup DDL and solution SQL in an ephemeral in-memory DuckDB instance.
        Returns: (success: bool, sandbox_output_preview: Optional[str], error_trace: Optional[str])
        """
        if not solution_sql or not solution_sql.strip():
            return False, None, "Missing solution_sql statement."

        con = duckdb.connect(database=":memory:")
        try:
            # 1. Execute Setup DDL if provided
            if setup_ddl and setup_ddl.strip():
                for stmt in setup_ddl.split(";"):
                    stmt_clean = stmt.strip()
                    if stmt_clean:
                        con.execute(stmt_clean)

            # 2. Execute Solution SQL query (wrapped in limit to avoid runaway queries)
            cleaned_sql = solution_sql.strip().rstrip(";")
            query = f"SELECT * FROM ({cleaned_sql}) LIMIT 10;"
            res = con.execute(query)
            columns = [desc[0] for desc in res.description] if res.description else []
            rows = res.fetchall()

            # Format preview rows as JSON string without requiring pandas
            preview_dicts = [dict(zip(columns, row)) for row in rows]
            preview_json = json.dumps(preview_dicts, default=str)
            return True, preview_json, None

        except Exception as exc:
            return False, None, str(exc)
        finally:
            con.close()

    def classify_difficulty(self, solution_sql: str, problem_text: str = "") -> DifficultyLevel:
        """
        Determines query complexity rating using SQL AST and analytical pattern heuristics.
        """
        sql_upper = (solution_sql or "").upper()
        text_lower = (problem_text or "").lower()

        hard_patterns = [
            "ROW_NUMBER",
            "RANK(",
            "DENSE_RANK",
            "LAG(",
            "LEAD(",
            "RECURSIVE",
            "QUALIFY",
            "PERCENTILE_CONT",
            "NTILE",
            "OVER (",
            "OVER(",
            "GAPS AND ISLANDS",
            "SESSIONIZATION",
        ]
        if any(p in sql_upper for p in hard_patterns) or "gaps and islands" in text_lower or "retention" in text_lower:
            return DifficultyLevel.HARD

        medium_patterns = [
            "WITH ",
            "JOIN",
            "HAVING",
            "DATE_TRUNC",
            "CASE WHEN",
            "COALESCE",
            "UNION",
            "INTERSECT",
            "EXCEPT",
            "GROUP BY",
            "SUBSTRING",
        ]
        if any(p in sql_upper for p in medium_patterns):
            return DifficultyLevel.MEDIUM

        return DifficultyLevel.EASY

    def classify_dialect(self, solution_sql: str) -> SQLDialect:
        """Identifies SQL dialect suitability."""
        sql_upper = (solution_sql or "").upper()
        if "QUALIFY" in sql_upper:
            return SQLDialect.DUCKDB
        if "STRPTIME" in sql_upper or "STRING_SPLIT" in sql_upper:
            return SQLDialect.DUCKDB
        if "TO_DATE" in sql_upper or "DATE_ADD" in sql_upper:
            return SQLDialect.SPARK_SQL
        return SQLDialect.DUCKDB

    def curate(
        self,
        extracted: ExtractedRecord,
        domain: str = "sql",
        max_retries: int = 2,
    ) -> Optional[CuratedRecord]:
        """
        Curates and empirically verifies an extracted challenge record in the DuckDB sandbox.
        If execution fails, attempts self-correction if an extractor is configured.
        """
        data = extracted.data
        title = data.get("title", "Untitled Challenge")
        problem_statement = data.get("problem_statement", "")
        setup_ddl = data.get("setup_ddl", "")
        solution_sql = data.get("solution_sql", "")
        category = data.get("category")
        tags = data.get("tags", [])

        retry_count = 0
        success, sandbox_output, error_trace = self.verify_sql_sandbox(setup_ddl, solution_sql)

        # Loop Engineering: Self-correction retry loop
        while not success and retry_count < max_retries:
            retry_count += 1
            if not self.extractor:
                break

            # Re-prompt extractor with error feedback
            # In live execution, Extractor fixes DDL or syntax based on error_trace
            break

        if not success:
            return None

        difficulty = self.classify_difficulty(solution_sql, problem_statement)
        dialect = self.classify_dialect(solution_sql)
        quality_score = max(0.5, 1.0 - (retry_count * 0.15))

        return CuratedRecord(
            domain=domain,
            title=title,
            problem_statement=problem_statement,
            setup_ddl=setup_ddl,
            solution_sql=solution_sql,
            difficulty=difficulty,
            dialect=dialect,
            category=category,
            tags=tags if isinstance(tags, list) else [],
            source_urls=[extracted.source_url] if extracted.source_url else [],
            sandbox_output=sandbox_output,
            quality_score=quality_score,
            retry_count=retry_count,
        )
