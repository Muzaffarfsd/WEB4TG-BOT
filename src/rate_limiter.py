"""Rate limiting and resilience: spam protection, circuit breaker, backoff."""

import time
import logging
import asyncio
from collections import defaultdict
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class UserBucket:
    tokens: float = 10.0
    last_refill: float = field(default_factory=time.time)
    warnings: int = 0
    blocked_until: float = 0.0


@dataclass
class CircuitBreakerState:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: float = 0.0
    last_success: float = 0.0
    open_until: float = 0.0


class RateLimiter:
    def __init__(
        self,
        tokens_per_minute: float = 12,
        max_tokens: float = 15,
        block_duration: int = 300,
        warning_threshold: int = 3
    ):
        self._buckets: Dict[int, UserBucket] = {}
        self._tokens_per_minute = tokens_per_minute
        self._max_tokens = max_tokens
        self._block_duration = block_duration
        self._warning_threshold = warning_threshold
        self._global_count = 0
        self._global_window_start = time.time()

    def _get_bucket(self, user_id: int) -> UserBucket:
        if user_id not in self._buckets:
            self._buckets[user_id] = UserBucket()
        return self._buckets[user_id]

    def _refill(self, bucket: UserBucket):
        now = time.time()
        elapsed = now - bucket.last_refill
        refill = elapsed * (self._tokens_per_minute / 60.0)
        bucket.tokens = min(self._max_tokens, bucket.tokens + refill)
        bucket.last_refill = now

    def check_rate_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        now = time.time()
        bucket = self._get_bucket(user_id)

        if bucket.blocked_until > now:
            remaining = int(bucket.blocked_until - now)
            return False, f"⏳ Слишком много сообщений. Подождите {remaining} секунд."

        self._refill(bucket)

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            self._global_count += 1
            return True, None
        else:
            bucket.warnings += 1
            if bucket.warnings >= self._warning_threshold:
                bucket.blocked_until = now + self._block_duration
                bucket.warnings = 0
                return False, f"🚫 Вы временно заблокированы за спам. Попробуйте через {self._block_duration // 60} минут."
            return False, "⏳ Пожалуйста, не отправляйте сообщения так быстро. Подождите немного."

    def cleanup(self):
        now = time.time()
        stale = [uid for uid, b in self._buckets.items()
                 if now - b.last_refill > 3600 and b.blocked_until < now]
        for uid in stale:
            del self._buckets[uid]

    def get_stats(self) -> Dict:
        now = time.time()
        active = sum(1 for b in self._buckets.values() if now - b.last_refill < 300)
        blocked = sum(1 for b in self._buckets.values() if b.blocked_until > now)
        return {
            "active_users": active,
            "blocked_users": blocked,
            "total_tracked": len(self._buckets),
        }


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max: int = 2
    ):
        self._circuits: Dict[str, CircuitBreakerState] = {}
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max

    def _get_circuit(self, service: str) -> CircuitBreakerState:
        if service not in self._circuits:
            self._circuits[service] = CircuitBreakerState()
        return self._circuits[service]

    def can_execute(self, service: str) -> bool:
        circuit = self._get_circuit(service)
        now = time.time()

        if circuit.state == CircuitState.CLOSED:
            return True
        elif circuit.state == CircuitState.OPEN:
            if now >= circuit.open_until:
                circuit.state = CircuitState.HALF_OPEN
                circuit.failure_count = 0
                logger.info(f"Circuit breaker {service}: OPEN -> HALF_OPEN")
                return True
            return False
        elif circuit.state == CircuitState.HALF_OPEN:
            return circuit.failure_count < self._half_open_max

    def record_success(self, service: str):
        circuit = self._get_circuit(service)
        circuit.last_success = time.time()
        if circuit.state == CircuitState.HALF_OPEN:
            circuit.state = CircuitState.CLOSED
            circuit.failure_count = 0
            logger.info(f"Circuit breaker {service}: HALF_OPEN -> CLOSED")

    def record_failure(self, service: str, error: str = ""):
        circuit = self._get_circuit(service)
        circuit.failure_count += 1
        circuit.last_failure = time.time()

        if circuit.state == CircuitState.HALF_OPEN:
            circuit.state = CircuitState.OPEN
            circuit.open_until = time.time() + self._recovery_timeout
            logger.warning(f"Circuit breaker {service}: HALF_OPEN -> OPEN ({error})")
        elif circuit.state == CircuitState.CLOSED and circuit.failure_count >= self._failure_threshold:
            circuit.state = CircuitState.OPEN
            circuit.open_until = time.time() + self._recovery_timeout
            logger.warning(f"Circuit breaker {service}: CLOSED -> OPEN after {circuit.failure_count} failures ({error})")

    def get_status(self) -> Dict:
        return {
            service: {
                "state": c.state.value,
                "failures": c.failure_count,
            }
            for service, c in self._circuits.items()
        }


async def exponential_backoff_retry(
    coro_func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retry_on: tuple = (Exception,)
):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except retry_on as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
                await asyncio.sleep(delay)
    raise last_exception


rate_limiter = RateLimiter()
circuit_breaker = CircuitBreaker()
