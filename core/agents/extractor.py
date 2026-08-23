import hashlib
import json
from typing import Dict, Optional

from pydantic import BaseModel, Field

from core.agents.base import LLMClientWrapper
from core.schemas import ExtractedRecord, RawArtifact


class RawExtractionPayload(BaseModel):
    """Temporary structured output container from LLM extraction before wrapping in ExtractedRecord."""

    title: str = Field(..., description="Clean, concise title of the problem")
    problem_statement: str = Field(..., description="Complete, self-contained markdown description of the problem")
    setup_ddl: Optional[str] = Field(None, description="CREATE TABLE and INSERT INTO mock data statements")
    solution_sql: Optional[str] = Field(None, description="Canonical solution SQL query only (SELECT...)")
    dialect: Optional[str] = Field("DuckDB", description="SQL dialect (PostgreSQL, MySQL, DuckDB, Spark SQL)")
    difficulty: Optional[str] = Field("Medium", description="Estimated difficulty (Easy, Medium, Hard)")
    category: Optional[str] = Field(None, description="Topic (e.g. CTEs, Window Functions, Aggregations)")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")


class ExtractorAgent:
    """
    Extractor Agent for Kaizen Harvester.
    Converts unstructured code, markdown, and Jupyter notebooks into normalized structured challenge records.
    """

    def __init__(self, llm_client: Optional[LLMClientWrapper] = None):
        self.llm = llm_client or LLMClientWrapper()

    def _preprocess_content(self, artifact: RawArtifact) -> str:
        """
        Preprocesses raw file content to maximize token efficiency.
        Strips heavy base64 outputs, execution counts, and metadata from Jupyter notebooks.
        """
        if artifact.format == "jupyter":
            try:
                nb_data = json.loads(artifact.content)
                cleaned_cells = []
                for cell in nb_data.get("cells", []):
                    cell_type = cell.get("cell_type", "code")
                    source_lines = cell.get("source", [])
                    source_text = "".join(source_lines) if isinstance(source_lines, list) else str(source_lines)
                    if source_text.strip():
                        if cell_type == "markdown":
                            cleaned_cells.append(f"<!-- Markdown -->\n{source_text}")
                        else:
                            cleaned_cells.append(f"```sql\n{source_text}\n```")
                return "\n\n".join(cleaned_cells)
            except Exception:
                return artifact.content

        return artifact.content

    def extract(
        self,
        artifact: RawArtifact,
        target_schema: Optional[Dict[str, str]] = None,
        domain: str = "sql",
    ) -> ExtractedRecord:
        """
        Extracts structured domain challenge fields from raw artifact content.
        """
        processed_content = self._preprocess_content(artifact)
        raw_hash = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()

        schema_desc = json.dumps(
            target_schema
            or {
                "title": "string",
                "problem_statement": "string",
                "setup_ddl": "string",
                "solution_sql": "string",
                "dialect": "enum[PostgreSQL, MySQL, DuckDB, Spark SQL]",
                "difficulty": "enum[Easy, Medium, Hard]",
            },
            indent=2,
        )

        system_prompt = (
            f"You are the Extractor Agent for Kaizen Harvester.\n"
            f"Your job is to parse raw content from a {artifact.format} file and extract structured technical challenge fields "
            f"for the '{domain}' domain matching this target schema:\n{schema_desc}\n\n"
            f"Extraction Rules:\n"
            f"1. Isolate the setup DDL (CREATE TABLE, INSERT INTO) into 'setup_ddl'. Do not include SELECT solution queries in setup_ddl.\n"
            f"2. Extract ONLY the solution query into 'solution_sql' (no setup or DDL inside solution_sql).\n"
            f"3. Make 'problem_statement' a clean, self-contained markdown description.\n"
            f"4. If setup DDL is missing, synthesize minimal mock DDL tables and 3-5 rows based on the problem description."
        )

        user_prompt = (
            f"Source URL: {artifact.source_url}\n"
            f"File Path: {artifact.file_path}\n"
            f"Raw Content:\n"
            f"```\n{processed_content}\n```\n\n"
            f"Extract the structured challenge fields."
        )

        extracted_payload = self.llm.structured_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=RawExtractionPayload,
        )

        return ExtractedRecord(
            data=extracted_payload.model_dump(),
            source_url=artifact.source_url,
            raw_content_hash=raw_hash,
        )
