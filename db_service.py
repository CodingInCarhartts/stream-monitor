import aiohttp
from core_models import Notification
from settings import DatabaseSettings


class DatabaseNotificationService:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings

    async def save(self, notification: Notification) -> None:
        if not self.settings.url or not self.settings.anon_key:
            return

        message = notification.message

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.settings.url}/rest/v1/kick_notifications",
                json={
                    "platform": message.channel.platform,
                    "type": message.message_type,
                    "channel": message.channel.name,
                    "username": message.sender,
                    "message": str(message.content),
                    "timestamp": message.timestamp,
                    "url": notification.url,
                    "original_message": notification.original_message,
                },
                headers={
                    "apikey": str(self.settings.anon_key),
                    "Authorization": f"Bearer {self.settings.anon_key}",
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status != 201:
                    print(
                        f"Failed to save notification: {response.status} - {await response.text()}"
                    )
