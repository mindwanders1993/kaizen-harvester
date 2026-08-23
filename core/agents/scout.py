from pathlib import Path
from typing import Optional

from core.agents.base import LLMClientWrapper
from core.schemas import RawArtifact, ScoutResult

EXCLUDED_PATH_SUBSTRINGS = {
    "node_modules",
    "vendor",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "env",
    "venv",
    ".venv",
}

EXCLUDED_FILENAMES = {
    "license",
    "license.md",
    "license.txt",
    "copying",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "cargo.lock",
    "poetry.lock",
    "requirements.txt",
    "setup.py",
    "pyproject.toml",
    "tsconfig.json",
    ".gitignore",
    ".prettierrc",
    ".eslintrc",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


class ScoutAgent:
    """
    Scout Agent for Kaizen Harvester.
    Performs fast heuristic triage followed by LLM-backed REACT reasoning on ambiguous files.
    """

    def __init__(self, llm_client: Optional[LLMClientWrapper] = None):
        self.llm = llm_client or LLMClientWrapper()

    def _heuristic_triage(self, artifact: RawArtifact, domain: str = "sql") -> Optional[ScoutResult]:
        """
        Fast deterministic heuristic triage.
        Returns a ScoutResult if a definitive decision can be made without LLM, or None if ambiguous.
        """
        path_lower = artifact.file_path.lower()
        filename = Path(path_lower).name

        # 1. Reject excluded directory paths
        if any(ex in path_lower for ex in EXCLUDED_PATH_SUBSTRINGS):
            return ScoutResult(
                reasoning=f"Heuristic Reject: Path '{artifact.file_path}' is inside excluded directory.",
                is_candidate=False,
                confidence=1.0,
                primary_format=artifact.format,
                reason="Path in excluded directory (vendor/deps/build)",
            )

        # 2. Reject excluded boilerplate files
        if filename in EXCLUDED_FILENAMES:
            return ScoutResult(
                reasoning=f"Heuristic Reject: Filename '{filename}' is standard project config/license boilerplate.",
                is_candidate=False,
                confidence=1.0,
                primary_format=artifact.format,
                reason="Standard config or license boilerplate",
            )

        # 3. Reject empty or oversized files
        content_stripped = artifact.content.strip()
        if not content_stripped:
            return ScoutResult(
                reasoning="Heuristic Reject: File content is empty.",
                is_candidate=False,
                confidence=1.0,
                primary_format=artifact.format,
                reason="Empty file",
            )

        if len(artifact.content) > 200_000:
            return ScoutResult(
                reasoning="Heuristic Reject: File exceeds 200KB limit, likely a large dump or binary asset.",
                is_candidate=False,
                confidence=0.9,
                primary_format=artifact.format,
                reason="File size exceeds candidate limits",
            )

        # 4. Domain-specific fast candidates (SQL)
        if domain.lower() == "sql":
            content_upper = content_stripped.upper()

            # Clear SQL problem script
            if artifact.format == "sql":
                if ("SELECT" in content_upper and "FROM" in content_upper) or "CREATE TABLE" in content_upper:
                    return ScoutResult(
                        reasoning="Heuristic Candidate: Valid SQL file containing query and/or DDL statements.",
                        is_candidate=True,
                        confidence=0.95,
                        primary_format="sql",
                        reason="Standard SQL query/DDL file",
                    )

            # Clear Markdown SQL problem note
            if artifact.format == "markdown":
                has_problem_header = any(
                    kw in content_lower_snippet
                    for kw in [
                        "## problem",
                        "### problem",
                        "## question",
                        "## description",
                        "### schema",
                        "### solution",
                    ]
                    for content_lower_snippet in [content_stripped[:1000].lower()]
                )
                has_sql_fences = "```sql" in content_stripped.lower() or "```" in content_stripped.lower()
                if has_problem_header and has_sql_fences:
                    return ScoutResult(
                        reasoning="Heuristic Candidate: Markdown file containing problem description header and SQL code block.",
                        is_candidate=True,
                        confidence=0.95,
                        primary_format="markdown",
                        reason="Markdown problem statement with SQL blocks",
                    )

            # Jupyter notebooks with SQL or challenge headers
            if artifact.format == "jupyter":
                if "SELECT" in content_upper or "CREATE TABLE" in content_upper:
                    return ScoutResult(
                        reasoning="Heuristic Candidate: Jupyter Notebook containing SQL execution cells.",
                        is_candidate=True,
                        confidence=0.90,
                        primary_format="jupyter",
                        reason="Jupyter notebook with SQL cells",
                    )

        # If heuristics cannot definitively classify, return None for LLM triage
        return None

    def triage(self, artifact: RawArtifact, domain: str = "sql") -> ScoutResult:
        """
        Triages a raw artifact into a Candidate or Rejected classification.
        Applies fast heuristics first, falling back to LLM REACT triage for ambiguous cases.
        """
        # Step 1: Deterministic Heuristic Filter (0 LLM Cost)
        heuristic_res = self._heuristic_triage(artifact, domain=domain)
        if heuristic_res is not None:
            return heuristic_res

        # Step 2: LLM REACT Triage (Ambiguous Files Only)
        content_head = artifact.content[:1500]

        system_prompt = (
            f"You are the Scout Agent for Kaizen Harvester.\n"
            f"Your role is to evaluate whether a file contains genuine practice challenges, interview questions, "
            f"or educational problem statements for the domain: '{domain}'.\n\n"
            f"Follow the REACT principle: Provide explicit chain-of-thought reasoning analyzing the file path, "
            f"headers, and content snippet before concluding with your decision."
        )

        user_prompt = (
            f"File Path: {artifact.file_path}\n"
            f"Detected Format: {artifact.format}\n"
            f"Content Snippet (first 1500 chars):\n"
            f"```\n{content_head}\n```\n\n"
            f"Evaluate if this file is a viable candidate for extraction."
        )

        return self.llm.structured_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ScoutResult,
        )
