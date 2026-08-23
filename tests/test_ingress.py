import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ingress.base import RepoMetadata, detect_file_format
from core.ingress.github import GithubFetcher
from core.ingress.rate_limiter import AsyncRateLimiter
from core.ingress.web import WebFetcher


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_token_bucket_initial_and_acquire(self):
        limiter = AsyncRateLimiter(capacity=2.0, refill_rate=1.0)
        assert limiter.tokens == 2.0

        await limiter.acquire(1.0)
        assert limiter.tokens <= 1.0

        await limiter.acquire(1.0)
        assert limiter.tokens <= 0.05

    @pytest.mark.asyncio
    async def test_token_refill(self):
        limiter = AsyncRateLimiter(capacity=5.0, refill_rate=10.0)
        limiter.tokens = 0.0
        limiter.last_refill -= 0.5  # simulate 0.5s passed

        await limiter._refill()
        assert limiter.tokens >= 4.9

    @pytest.mark.asyncio
    async def test_rate_limit_reset_sleep(self):
        limiter = AsyncRateLimiter()
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("time.time", return_value=100.0):
                await limiter.handle_rate_limit_reset(reset_timestamp=110.0)
                # wait_seconds is (110 - 100) + 1.0 = 11.0
                mock_sleep.assert_awaited_once_with(11.0)

    @pytest.mark.asyncio
    async def test_execute_with_backoff_success(self):
        limiter = AsyncRateLimiter()
        mock_fn = AsyncMock(return_value="success")

        result = await limiter.execute_with_backoff(mock_fn, max_retries=3)
        assert result == "success"
        assert mock_fn.await_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_backoff_retry_and_fail(self):
        limiter = AsyncRateLimiter()
        mock_fn = AsyncMock(side_effect=ValueError("Connection error"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="Connection error"):
                await limiter.execute_with_backoff(mock_fn, max_retries=3)
        assert mock_fn.await_count == 3


class TestFormatDetection:
    def test_detect_file_format(self):
        assert detect_file_format("query.sql") == "sql"
        assert detect_file_format("UPPER_CASE.SQL") == "sql"
        assert detect_file_format("README.md") == "markdown"
        assert detect_file_format("doc.markdown") == "markdown"
        assert detect_file_format("page.mdx") == "markdown"
        assert detect_file_format("notebook.ipynb") == "jupyter"
        assert detect_file_format("script.py") == "code"
        assert detect_file_format("config.json") == "code"


class TestGithubFetcher:
    @pytest.mark.asyncio
    async def test_search_repositories(self):
        fetcher = GithubFetcher(token="mock_token")

        mock_payload = {
            "items": [
                {
                    "id": 12345,
                    "name": "sql-interview-questions",
                    "full_name": "faizanxmulla/sql-interview-questions",
                    "html_url": "https://github.com/faizanxmulla/sql-interview-questions",
                    "clone_url": "https://github.com/faizanxmulla/sql-interview-questions.git",
                    "description": "SQL interview prep",
                    "stargazers_count": 150,
                    "language": "SQL",
                    "default_branch": "main",
                }
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock(return_value=mock_payload)
        mock_response.raise_for_status = MagicMock()

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response

        mock_session_inst = MagicMock()
        mock_session_inst.get.return_value = mock_get_ctx
        mock_session_inst.__aenter__.return_value = mock_session_inst
        mock_session_inst.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session_inst):
            repos = await fetcher.search_repositories("topic:sql-interview-questions", min_stars=10)

        assert len(repos) == 1
        repo = repos[0]
        assert isinstance(repo, RepoMetadata)
        assert repo.name == "sql-interview-questions"
        assert repo.stargazers_count == 150
        assert repo.full_name == "faizanxmulla/sql-interview-questions"

    @pytest.mark.asyncio
    async def test_clone_and_extract(self):
        fetcher = GithubFetcher()

        with tempfile.TemporaryDirectory() as fixture_dir:
            fpath = Path(fixture_dir)
            (fpath / "problems").mkdir()
            (fpath / "problems" / "test.sql").write_text("SELECT 1;", encoding="utf-8")
            (fpath / "node_modules").mkdir()
            (fpath / "node_modules" / "junk.js").write_text("console.log()", encoding="utf-8")

            # Mock create_subprocess_exec to copy fixture_dir contents to target tmp_dir
            async def fake_subprocess(*args, **kwargs):
                target_dir = args[args.index("--filter=blob:none") + 2]
                import shutil

                shutil.copytree(fixture_dir, target_dir, dirs_exist_ok=True)
                mock_proc = AsyncMock()
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"", b"")
                return mock_proc

            filters = {
                "exclude_paths": ["node_modules/**", ".git/**"],
                "file_patterns": ["*.sql"],
            }

            with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
                artifacts = []
                async for art in fetcher.clone_and_extract("https://github.com/mock/repo.git", filters):
                    artifacts.append(art)

                assert len(artifacts) == 1
                assert artifacts[0].file_path == "problems/test.sql"
                assert artifacts[0].content == "SELECT 1;"
                assert artifacts[0].format == "sql"


class TestWebFetcher:
    @pytest.mark.asyncio
    async def test_fetch(self):
        fetcher = WebFetcher()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="# SQL Problem Guide\nHere is a question...")
        mock_response.raise_for_status = MagicMock()

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response

        mock_session_inst = MagicMock()
        mock_session_inst.get.return_value = mock_get_ctx
        mock_session_inst.__aenter__.return_value = mock_session_inst
        mock_session_inst.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session_inst):
            artifacts = []
            async for art in fetcher.fetch(["https://example.com/sql-guide.md"]):
                artifacts.append(art)

        assert len(artifacts) == 1
        assert artifacts[0].source_url == "https://example.com/sql-guide.md"
        assert artifacts[0].format == "markdown"
        assert "# SQL Problem Guide" in artifacts[0].content
