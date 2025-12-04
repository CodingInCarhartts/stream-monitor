import aiohttp
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from core_models import Notification
from settings import DiscordSettings
from resource_manager import SessionPool, CircuitBreaker


class DiscordNotificationService:
    def __init__(self, settings: DiscordSettings):
        self.settings = settings
        self.color_map = {
            "Twitch": 0x9146FF,
            "Kick": 0x53FC18,
        }
        # Resource management utilities
        self.session_pool = SessionPool(connector_limit=50, timeout_seconds=10.0)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0
        )

    async def send(self, notification: Notification) -> None:
        """Send notification with circuit breaker protection and proper session cleanup"""
        if not self.settings.webhook_url:
            return

        embed = self._create_embed(notification)
        payload = {"embeds": [embed]}

        try:
            # Use circuit breaker to prevent cascading failures
            await self.circuit_breaker.call(self._send_with_timeout(payload))
        except RuntimeError as e:
            print(f"Circuit breaker open: {e}")
        except Exception as e:
            print(f"Error sending Discord notification: {e}")

    async def _send_with_timeout(self, payload: Dict[str, Any]) -> None:
        """Send with explicit timeout and proper session management"""
        try:
            async with self.session_pool.get_session() as session:
                async with asyncio.timeout(10.0):  # Explicit timeout
                    async with session.post(
                        self.settings.webhook_url, json=payload
                    ) as response:
                        if response.status != 204:
                            error_msg = await response.text()
                            raise aiohttp.ClientError(
                                f"Discord API error: {response.status} - {error_msg}"
                            )
                        self.circuit_breaker.record_success()
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            raise TimeoutError("Discord notification send timeout") from None

    def _create_embed(self, notification: Notification) -> Dict[str, Any]:
        message = notification.message
        timestamp = self._format_timestamp(message.timestamp)

        fields = []

        if notification.original_message:
            fields.append(
                {
                    "name": "Original Message",
                    "value": notification.original_message[:1024],
                    "inline": False,
                }
            )

        fields.extend(
            [
                {
                    "name": "Message",
                    "value": str(message.content)[:1024],
                    "inline": False,
                },
                {
                    "name": "Channel",
                    "value": f"[{message.channel.name}]({notification.url})",
                    "inline": True,
                },
                {
                    "name": "User",
                    "value": message.sender,
                    "inline": True,
                },
            ]
        )

        return {
            "title": f"Notification on {message.channel.platform}",
            "description": f"{message.sender} {message.message_type} in {message.channel.name}",
            "color": self.color_map.get(message.channel.platform, 0x808080),
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": f"{message.channel.platform} Notification"},
        }

    async def cleanup(self) -> None:
        """Clean up all session resources"""
        await self.session_pool.cleanup_all()

    def _format_timestamp(self, value: datetime | int | str) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000).isoformat()
        return str(value)
