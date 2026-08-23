import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp

from core.ingress.base import BaseFetcher, RepoMetadata, detect_file_format
from core.ingress.rate_limiter import AsyncRateLimiter
from core.schemas import RawArtifact


class GithubFetcher(BaseFetcher):
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.rate_limiter = AsyncRateLimiter(capacity=10, refill_rate=1.38)
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    async def search_repositories(self, query: str, min_stars: int = 0) -> List[RepoMetadata]:
        repos = []
        if "stars:>" not in query and min_stars > 0:
            url = f"https://api.github.com/search/repositories?q={query}+stars:>{min_stars}&per_page=100"
        else:
            url = f"https://api.github.com/search/repositories?q={query}&per_page=100"

        async with aiohttp.ClientSession(headers=self.headers) as session:
            while url:
                await self.rate_limiter.acquire()
                async with session.get(url) as response:
                    if response.status == 403 and "x-ratelimit-reset" in response.headers:
                        reset_time = float(response.headers["x-ratelimit-reset"])
                        await self.rate_limiter.handle_rate_limit_reset(reset_time)
                        continue

                    response.raise_for_status()
                    data = await response.json()

                    for item in data.get("items", []):
                        repos.append(
                            RepoMetadata(
                                id=item.get("id"),
                                name=item["name"],
                                full_name=item["full_name"],
                                html_url=item["html_url"],
                                clone_url=item["clone_url"],
                                description=item.get("description"),
                                stargazers_count=item.get("stargazers_count", 0),
                                language=item.get("language"),
                                default_branch=item.get("default_branch", "main"),
                            )
                        )

                    # Check pagination header
                    url = None
                    link_header = response.headers.get("Link")
                    if link_header:
                        links = link_header.split(",")
                        for link in links:
                            if 'rel="next"' in link:
                                url = link[link.find("<") + 1 : link.find(">")]
                                break
        return repos

    def _should_exclude(self, rel_path: Path, exclude_paths: List[str]) -> bool:
        path_str = str(rel_path)
        for pattern in exclude_paths:
            if pattern.endswith("/**"):
                base = pattern[:-3]
                if path_str.startswith(base + "/") or path_str == base or rel_path.name == base:
                    return True
            elif rel_path.match(pattern) or path_str == pattern or rel_path.name == pattern:
                return True
        return False

    def _matches_file_patterns(self, rel_path: Path, file_patterns: List[str]) -> bool:
        if not file_patterns:
            return True
        for pattern in file_patterns:
            if rel_path.match(pattern) or rel_path.name == pattern:
                return True
        return False

    async def clone_and_extract(
        self, repo_url: str, filters: Optional[Dict] = None
    ) -> AsyncGenerator[RawArtifact, None]:
        filters = filters or {}
        tmp_dir = Path(tempfile.gettempdir()) / f"kaizen_harvest_{uuid.uuid4().hex}"

        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                repo_url,
                str(tmp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            if process.returncode != 0:
                return

            exclude_paths = filters.get("exclude_paths", [])
            file_patterns = filters.get("file_patterns", [])

            for root, dirs, files in os.walk(tmp_dir):
                root_path = Path(root)
                # Filter out excluded directories in-place
                dirs[:] = [
                    d for d in dirs if not self._should_exclude((root_path / d).relative_to(tmp_dir), exclude_paths)
                ]

                for file in files:
                    file_path = root_path / file
                    rel_path = file_path.relative_to(tmp_dir)

                    if self._should_exclude(rel_path, exclude_paths):
                        continue

                    if not self._matches_file_patterns(rel_path, file_patterns):
                        continue

                    format_type = detect_file_format(str(file_path))

                    try:
                        content = file_path.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue

                    yield RawArtifact(
                        source_url=f"{repo_url.rstrip('.git')}/blob/HEAD/{rel_path}",
                        file_path=str(rel_path),
                        content=content,
                        format=format_type,
                        metadata={"repo_url": repo_url},
                    )
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    async def fetch(self, targets: List[str], filters: Optional[Dict] = None) -> AsyncGenerator[RawArtifact, None]:
        filters = filters or {}
        for target in targets:
            if target.startswith("http://") or target.startswith("https://"):
                async for artifact in self.clone_and_extract(target, filters):
                    yield artifact
            else:
                repos = await self.search_repositories(target, filters.get("min_stars", 0))
                for repo in repos:
                    async for artifact in self.clone_and_extract(repo.clone_url, filters):
                        yield artifact
