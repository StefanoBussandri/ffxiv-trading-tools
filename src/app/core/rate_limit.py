import asyncio
import logging
import time
from contextlib import asynccontextmanager

import httpx

log = logging.getLogger("rate_limit")


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait)


class RateLimiter:
    def __init__(
        self,
        rate: float,
        capacity: float,
        max_concurrent: int,
        name: str = "limiter",
    ) -> None:
        self.bucket = TokenBucket(rate, capacity)
        self.sem = asyncio.Semaphore(max_concurrent)
        self.name = name
        self.in_flight = 0
        self.max_seen = 0

    @asynccontextmanager
    async def slot(self):
        await self.bucket.acquire()
        async with self.sem:
            self.in_flight += 1
            if self.in_flight > self.max_seen:
                self.max_seen = self.in_flight
            log.debug("%s in_flight=%d max_seen=%d", self.name, self.in_flight, self.max_seen)
            try:
                yield
            finally:
                self.in_flight -= 1


class RateLimitedClient:
    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter) -> None:
        self._c = client
        self._lim = limiter

    @property
    def limiter(self) -> RateLimiter:
        return self._lim

    async def get(self, url: str, **kwargs) -> httpx.Response:
        async with self._lim.slot():
            return await self._c.get(url, **kwargs)
