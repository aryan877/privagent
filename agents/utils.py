from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_time: float = 60.0,
        half_open_success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.half_open_success_threshold = half_open_success_threshold

        self._state: str = "closed"
        self._failures: int = 0
        self._successes: int = 0
        self._last_failure: float = 0.0

    def allow_call(self) -> bool:
        if self._state == "closed":
            return True

        if self._state == "open":
            # Only reopen the breaker after the cool-off period has elapsed.
            if time.time() - self._last_failure >= self.recovery_time:
                self._state = "half_open"
                self._successes = 0
                return True
            return False

        # half_open
        return True

    def record_success(self) -> None:
        self._failures = 0
        if self._state == "half_open":
            self._successes += 1
            if self._successes >= self.half_open_success_threshold:
                self._state = "closed"
                self._successes = 0

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.time()
        self._successes = 0
        if self._failures >= self.failure_threshold:
            self._state = "open"

    @property
    def state(self) -> str:
        return self._state


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self._last_refill = time.time()

    async def acquire(self, amount: float = 1.0, max_wait: float = 5.0) -> bool:
        await self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True

        deficit = amount - self.tokens
        wait_time = deficit / self.rate if self.rate else max_wait
        if wait_time > max_wait:
            return False

        await asyncio.sleep(wait_time)
        await self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    async def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self._last_refill = now


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    backoff: float = 2.0,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    attempt = 0
    while True:
        try:
            return await func()
        except Exception as exc:  # noqa: PERF203 - explicit retry loop
            attempt += 1
            if attempt > retries:
                raise
            if on_retry:
                on_retry(attempt, exc)
            await asyncio.sleep(base_delay * (backoff ** (attempt - 1)))


@dataclass
class TransactionContext:
    signature: Optional[str] = None
    slot: Optional[int] = None
    block_time: Optional[int] = None
    fee_paid: int = 0
    compute_units: int = 0
    priority_fee: int = 0
    retries: int = 0
    deadline_seconds: int = 30

    metadata: dict = field(default_factory=dict)
