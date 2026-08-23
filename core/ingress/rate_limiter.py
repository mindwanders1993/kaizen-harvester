import asyncio
import time
from typing import Any, Callable, Coroutine, Optional


class AsyncRateLimiter:
    """
    Token Bucket rate limiter for managing API throughput and complying with GitHub API rate limits.
    Default config: 10 token burst capacity, refills ~1.38 tokens/sec (approx 5,000 req/hr).
    """

    def __init__(self, capacity: float = 10.0, refill_rate: float = 1.38):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquires tokens, sleeping asynchronously if the bucket is empty."""
        while True:
            async with self._lock:
                await self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                needed = tokens - self.tokens
                sleep_time = needed / self.refill_rate

            await asyncio.sleep(min(sleep_time, 2.0))

    async def handle_rate_limit_reset(self, reset_timestamp: Optional[float] = None) -> None:
        """Handles HTTP 403 rate limit by sleeping until reset timestamp."""
        if reset_timestamp:
            now_epoch = time.time()
            wait_seconds = max(0.0, reset_timestamp - now_epoch) + 1.0
            await asyncio.sleep(min(wait_seconds, 60.0))
        else:
            await asyncio.sleep(5.0)

    async def execute_with_backoff(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> Any:
        """Executes an async callable with token acquisition and exponential backoff on failure."""
        for attempt in range(max_retries):
            await self.acquire()
            try:
                return await coro_fn()
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise exc
                wait_time = backoff_factor**attempt
                await asyncio.sleep(wait_time)
