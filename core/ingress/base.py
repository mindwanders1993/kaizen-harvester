from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field

from core.schemas import RawArtifact


class RepoMetadata(BaseModel):
    """Metadata container for discovered source repositories."""

    id: Optional[int] = None
    name: str = Field(..., description="Repository short name")
    full_name: str = Field(..., description="Owner/repo full name")
    html_url: str = Field(..., description="Web URL")
    clone_url: str = Field(..., description="Git clone URL")
    description: Optional[str] = Field(None, description="Repository description")
    stargazers_count: int = Field(0, description="Star count")
    language: Optional[str] = Field(None, description="Primary language")
    default_branch: str = Field("main", description="Default branch name")


def detect_file_format(file_path: str) -> str:
    """Classifies file format category based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".sql":
        return "sql"
    elif ext in [".md", ".markdown", ".mdx"]:
        return "markdown"
    elif ext == ".ipynb":
        return "jupyter"
    return "code"


class BaseFetcher(ABC):
    """Abstract protocol for all Ingress collectors."""

    @abstractmethod
    async def fetch(
        self,
        targets: List[str],
        filters: Optional[Dict] = None,
    ) -> AsyncGenerator[RawArtifact, None]:
        """Discovers and yields RawArtifacts based on target queries or URLs."""
        pass
