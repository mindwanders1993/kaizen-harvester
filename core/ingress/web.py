from typing import AsyncGenerator, Dict, List, Optional

import aiohttp

from core.ingress.base import BaseFetcher
from core.schemas import RawArtifact


class WebFetcher(BaseFetcher):
    async def fetch(self, targets: List[str], filters: Optional[Dict] = None) -> AsyncGenerator[RawArtifact, None]:
        async with aiohttp.ClientSession() as session:
            for url in targets:
                if not url.startswith("http"):
                    continue
                try:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        content = await response.text()
                        yield RawArtifact(
                            source_url=url,
                            file_path=url.split("/")[-1] or "index.html",
                            content=content,
                            format="markdown",
                            metadata={},
                        )
                except Exception:
                    pass
