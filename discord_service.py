import aiohttp
from datetime import datetime
from typing import Any, Dict

from core_models import Notification
from settings import DiscordSettings


class DiscordNotificationService:
    def __init__(self, settings: DiscordSettings):
        self.settings = settings
        self.color_map = {
            "Twitch": 0x9146FF,
            "Kick": 0x53FC18,
        }

    async def send(self, notification: Notification) -> None:
        embed = self._create_embed(notification)
        payload = {"embeds": [embed]}

        if not self.settings.webhook_url:
            return

        async with aiohttp.ClientSession() as session:
            async with session.post(self.settings.webhook_url, json=payload) as response:
                if response.status != 204:
                    print(f"Failed to send Discord notification: {response.status}")

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

    def _format_timestamp(self, value: datetime | int | str) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000).isoformat()
        return str(value)
