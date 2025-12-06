"""
Resource cleanup utilities for managing WebSocket connections, sessions, and async tasks.
Implements bounded memory structures, timeouts, circuit breakers, and graceful cleanup.
"""

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from enum import Enum
from typing import AsyncIterator, Callable, Any, Optional


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Fail fast
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    Stops attempting operations that are likely to fail.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED

    def record_success(self) -> None:
        """Record a successful operation"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def can_attempt(self) -> bool:
        """Check if operation can be attempted"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False

        # HALF_OPEN: allow one attempt to test recovery
        return True

    async def call(self, coro: Any) -> Any:
        """Execute operation with circuit breaker protection"""
        if not self.can_attempt():
            raise RuntimeError(
                f"Circuit breaker is OPEN. Retry after {self.recovery_timeout}s"
            )

        try:
            result = await coro
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure()
            raise


class BoundedMessageQueue:
    """
    Thread-safe bounded queue for messages using deque.
    Prevents unbounded memory growth by discarding old messages when full.
    """

    def __init__(self, maxlen: int = 1000):
        self.queue: deque[dict] = deque(maxlen=maxlen)
        self.lock = asyncio.Lock()

    async def put(self, item: dict) -> bool:
        """
        Add message to queue. Returns False if queue was full and item was dropped.
        """
        async with self.lock:
            was_full = len(self.queue) == self.queue.maxlen
            self.queue.append(item)
            return not was_full

    async def get(self) -> Optional[dict]:
        """Get next message from queue"""
        async with self.lock:
            if self.queue:
                return self.queue.popleft()
            return None

    async def size(self) -> int:
        """Get current queue size"""
        async with self.lock:
            return len(self.queue)

    async def clear(self) -> None:
        """Clear all messages from queue"""
        async with self.lock:
            self.queue.clear()


class ExplicitTimeoutManager:
    """
    Manages explicit timeouts for operations to prevent accumulation.
    Tracks timeout violations for monitoring.
    """

    def __init__(self):
        self.timeout_violations = 0
        self.total_operations = 0

    @asynccontextmanager
    async def timeout_context(
        self, operation_name: str, timeout_seconds: float
    ) -> AsyncIterator[None]:
        """
        Context manager for explicit timeouts.
        Usage:
            async with timeout_manager.timeout_context("operation", 10.0):
                await some_operation()
        """
        self.total_operations += 1
        try:
            async with asyncio.timeout(timeout_seconds):
                yield
        except asyncio.TimeoutError:
            self.timeout_violations += 1
            raise TimeoutError(
                f"Operation '{operation_name}' exceeded {timeout_seconds}s timeout"
            ) from None

    def get_violation_rate(self) -> float:
        """Get percentage of operations that timed out"""
        if self.total_operations == 0:
            return 0.0
        return (self.timeout_violations / self.total_operations) * 100


class SessionPool:
    """
    Manages a single reusable aiohttp session with bounded lifecycle.
    Uses lazy initialization and ensures proper cleanup.
    """

    def __init__(self, connector_limit: int = 100, timeout_seconds: float = 30.0):
        self.connector_limit = connector_limit
        self.timeout_seconds = timeout_seconds
        self._session: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def _get_or_create_session(self) -> Any:
        """Get existing session or create one if needed"""
        if self._session is None or self._session.closed:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            connector = aiohttp.TCPConnector(limit=self.connector_limit, limit_per_host=10)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        """Get the shared aiohttp session"""
        async with self._lock:
            session = await self._get_or_create_session()
        yield session

    async def cleanup_all(self) -> None:
        """Close the session"""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
            self._session = None


class WebSocketConnectionManager:
    """
    Manages WebSocket connections with circuit breaker, timeouts, and graceful cleanup.
    """

    def __init__(self, max_reconnect_attempts: int = 10):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0
        )
        self.timeout_manager = ExplicitTimeoutManager()
        self.max_reconnect_attempts = max_reconnect_attempts
        self.active_connections: list[Any] = []
        self.lock = asyncio.Lock()

    async def connect_with_retry(
        self,
        ws_url: str,
        connection_handler: Callable[[Any], Any],
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
    ) -> None:
        """
        Connect to WebSocket with exponential backoff and circuit breaker protection.
        Ensures graceful cleanup on errors.
        """
        backoff_delay = initial_backoff
        reconnect_attempts = 0

        while reconnect_attempts < self.max_reconnect_attempts:
            try:
                if not self.circuit_breaker.can_attempt():
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, max_backoff)
                    continue

                async with asyncio.timeout(30.0):  # Connection timeout
                    import websockets

                    async with websockets.connect(
                        ws_url,
                        ping_interval=30,
                        ping_timeout=10,
                        close_timeout=5,
                    ) as websocket:
                        async with self.lock:
                            self.active_connections.append(websocket)

                        try:
                            self.circuit_breaker.record_success()
                            backoff_delay = initial_backoff
                            reconnect_attempts = 0

                            await connection_handler(websocket)
                        finally:
                            async with self.lock:
                                if websocket in self.active_connections:
                                    self.active_connections.remove(websocket)

            except asyncio.TimeoutError:
                self.circuit_breaker.record_failure()
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2, max_backoff)
                reconnect_attempts += 1
            except Exception as e:
                self.circuit_breaker.record_failure()
                print(
                    f"WebSocket error (attempt {reconnect_attempts + 1}/"
                    f"{self.max_reconnect_attempts}): {e}"
                )
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2, max_backoff)
                reconnect_attempts += 1

        print(f"Max reconnection attempts ({self.max_reconnect_attempts}) exceeded")

    async def cleanup_all(self) -> None:
        """Close all active connections"""
        async with self.lock:
            for conn in self.active_connections:
                try:
                    await conn.close()
                except Exception as e:
                    print(f"Error closing connection: {e}")
            self.active_connections.clear()


class TaskManager:
    """
    Manages async tasks with proper cleanup and cancellation.
    Prevents orphaned tasks from accumulating.
    """

    def __init__(self):
        self.tasks: set[asyncio.Task[Any]] = set()
        self.lock = asyncio.Lock()

    async def create_task(self, coro: Any, name: Optional[str] = None) -> asyncio.Task[Any]:
        """Create and track a task"""
        task = asyncio.create_task(coro)
        if name:
            task.set_name(name)

        async with self.lock:
            self.tasks.add(task)

        # Remove task from set when done
        task.add_done_callback(lambda t: asyncio.create_task(self._remove_task(t)))
        return task

    async def _remove_task(self, task: asyncio.Task[Any]) -> None:
        """Remove completed task from set"""
        async with self.lock:
            self.tasks.discard(task)

    async def cancel_all(self) -> None:
        """Cancel all tracked tasks"""
        async with self.lock:
            for task in self.tasks:
                task.cancel()

        # Wait for cancellation
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        async with self.lock:
            self.tasks.clear()

    async def get_active_count(self) -> int:
        """Get number of active tasks"""
        async with self.lock:
            return len(self.tasks)
