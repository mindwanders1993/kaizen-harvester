import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import duckdb

from core.schemas import CuratedRecord, DifficultyLevel, HarvestRunStats, SQLDialect


class DuckDBStore:
    """Relational knowledge vault backed by DuckDB for storing, querying, and exporting validated challenges."""

    def __init__(self, db_path: str = "storage/vault.duckdb"):
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.con = duckdb.connect(database=self.db_path)
        self.init_schema()

    def init_schema(self) -> None:
        """Initializes the relational schema for challenges and harvest run telemetry."""
        self.con.execute("""
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
                quality_score DOUBLE,
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

    def insert_challenge(self, record: CuratedRecord) -> str:
        """Inserts or updates a validated challenge in the vault."""
        # Convert created_at to ISO or string format if needed
        created_at_val = record.created_at or datetime.now(timezone.utc)

        self.con.execute(
            """
            INSERT INTO challenges (
                id, domain, title, problem_statement, setup_ddl, solution_sql,
                difficulty, dialect, category, tags, source_urls,
                sandbox_output, quality_score, retry_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                title = excluded.title,
                problem_statement = excluded.problem_statement,
                setup_ddl = excluded.setup_ddl,
                solution_sql = excluded.solution_sql,
                difficulty = excluded.difficulty,
                dialect = excluded.dialect,
                category = excluded.category,
                tags = excluded.tags,
                source_urls = excluded.source_urls,
                sandbox_output = excluded.sandbox_output,
                quality_score = excluded.quality_score,
                retry_count = excluded.retry_count;
            """,
            [
                record.record_id,
                record.domain,
                record.title,
                record.problem_statement,
                record.setup_ddl,
                record.solution_sql,
                record.difficulty.value if isinstance(record.difficulty, DifficultyLevel) else str(record.difficulty),
                record.dialect.value if isinstance(record.dialect, SQLDialect) else str(record.dialect),
                record.category,
                record.tags,
                record.source_urls,
                record.sandbox_output,
                record.quality_score,
                record.retry_count,
                created_at_val,
            ],
        )
        return record.record_id

    def merge_source(self, record_id: str, source_url: str) -> None:
        """Appends a new source URL to an existing challenge if not already tracked."""
        row = self.con.execute("SELECT source_urls FROM challenges WHERE id = ?", [record_id]).fetchone()
        if not row:
            return

        current_sources = row[0] if row[0] is not None else []
        if source_url not in current_sources:
            new_sources = list(current_sources) + [source_url]
            self.con.execute(
                "UPDATE challenges SET source_urls = ? WHERE id = ?",
                [new_sources, record_id],
            )

    def get_challenge(self, record_id: str) -> Optional[CuratedRecord]:
        """Retrieves a single challenge by its unique ID."""
        row = self.con.execute(
            """
            SELECT id, domain, title, problem_statement, setup_ddl, solution_sql,
                   difficulty, dialect, category, tags, source_urls,
                   sandbox_output, quality_score, retry_count, created_at
            FROM challenges WHERE id = ?
            """,
            [record_id],
        ).fetchone()

        if not row:
            return None

        return CuratedRecord(
            record_id=row[0],
            domain=row[1],
            title=row[2],
            problem_statement=row[3],
            setup_ddl=row[4],
            solution_sql=row[5],
            difficulty=DifficultyLevel(row[6])
            if row[6] in [d.value for d in DifficultyLevel]
            else DifficultyLevel.UNKNOWN,
            dialect=SQLDialect(row[7]) if row[7] in [d.value for d in SQLDialect] else SQLDialect.DUCKDB,
            category=row[8],
            tags=row[9] if row[9] is not None else [],
            source_urls=row[10] if row[10] is not None else [],
            sandbox_output=row[11],
            quality_score=row[12] if row[12] is not None else 1.0,
            retry_count=row[13] if row[13] is not None else 0,
            created_at=row[14],
        )

    def get_stats(self) -> Dict[str, Any]:
        """Computes aggregate vault statistics (total count, difficulty & dialect breakdowns)."""
        total_row = self.con.execute("SELECT COUNT(*) FROM challenges").fetchone()
        total_count = total_row[0] if total_row else 0

        diff_rows = self.con.execute(
            "SELECT difficulty, COUNT(*) FROM challenges GROUP BY difficulty ORDER BY COUNT(*) DESC"
        ).fetchall()
        by_difficulty = {row[0] or "Unknown": row[1] for row in diff_rows}

        dialect_rows = self.con.execute(
            "SELECT dialect, COUNT(*) FROM challenges GROUP BY dialect ORDER BY COUNT(*) DESC"
        ).fetchall()
        by_dialect = {row[0] or "Unknown": row[1] for row in dialect_rows}

        cat_rows = self.con.execute(
            "SELECT category, COUNT(*) FROM challenges GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall()
        by_category = {row[0] or "Uncategorized": row[1] for row in cat_rows}

        return {
            "total_challenges": total_count,
            "by_difficulty": by_difficulty,
            "by_dialect": by_dialect,
            "by_category": by_category,
        }

    def record_harvest_run(self, stats: HarvestRunStats) -> None:
        """Records or updates harvest run telemetry."""
        self.con.execute(
            """
            INSERT INTO harvest_runs (
                run_id, recipe_name, started_at, completed_at,
                total_scanned, total_extracted, total_deduped, total_saved, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id) DO UPDATE SET
                completed_at = excluded.completed_at,
                total_scanned = excluded.total_scanned,
                total_extracted = excluded.total_extracted,
                total_deduped = excluded.total_deduped,
                total_saved = excluded.total_saved,
                status = excluded.status;
            """,
            [
                stats.run_id,
                stats.recipe_name,
                stats.started_at,
                stats.completed_at,
                stats.total_scanned,
                stats.total_extracted,
                stats.total_deduped,
                stats.total_saved,
                stats.status,
            ],
        )

    def export_jsonl(self, output_path: str) -> None:
        """Exports all challenges to JSONL format."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        # Using DuckDB copy to json format
        self.con.execute(f"COPY challenges TO '{output_path}' (FORMAT JSON);")

    def export_parquet(self, output_path: str) -> None:
        """Exports all challenges to compressed Apache Parquet format."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self.con.execute(f"COPY challenges TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD);")

    def close(self) -> None:
        """Closes DuckDB connection."""
        self.con.close()
