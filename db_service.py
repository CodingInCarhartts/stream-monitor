import aiohttp
import asyncio
from core_models import Notification
from settings import DatabaseSettings
from resource_manager import SessionPool, CircuitBreaker


class DatabaseNotificationService:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        # Resource management utilities
        self.session_pool = SessionPool(connector_limit=50, timeout_seconds=15.0)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=10, recovery_timeout=120.0
        )

    async def save(self, notification: Notification) -> None:
        """Save notification with circuit breaker protection and proper session cleanup"""
        if not self.settings.url or not self.settings.anon_key:
            return

        message = notification.message
        payload = {
            "platform": message.channel.platform,
            "type": message.message_type,
            "channel": message.channel.name,
            "username": message.sender,
            "message": str(message.content),
            "timestamp": message.timestamp,
            "url": notification.url,
            "original_message": notification.original_message,
        }

        try:
            # Use circuit breaker to prevent cascading failures
            await self.circuit_breaker.call(self._save_with_timeout(payload))
        except RuntimeError as e:
            print(f"Circuit breaker open for database: {e}")
        except Exception as e:
            print(f"Error saving notification: {e}")

    async def _save_with_timeout(self, payload: dict) -> None:
        """Save with explicit timeout and proper session management"""
        try:
            async with self.session_pool.get_session() as session:
                async with asyncio.timeout(15.0):  # Explicit timeout
                    async with session.post(
                        f"{self.settings.url}/rest/v1/kick_notifications",
                        json=payload,
                        headers={
                            "apikey": str(self.settings.anon_key),
                            "Authorization": f"Bearer {self.settings.anon_key}",
                            "Content-Type": "application/json",
                        },
                    ) as response:
                        if response.status != 201:
                            error_msg = await response.text()
                            raise aiohttp.ClientError(
                                f"Database API error: {response.status} - {error_msg}"
                            )
                        self.circuit_breaker.record_success()
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            raise TimeoutError("Database save timeout") from None

    async def cleanup(self) -> None:
        """Clean up all session resources"""
        await self.session_pool.cleanup_all()
