import asyncio

from core_models import Notification
from settings import load_settings
from kick_service import KickChannelRepository, KickWebSocketClient
from discord_service import DiscordNotificationService
from db_service import DatabaseNotificationService
from fps_renewal_bot import run_renewal_bot


async def handle_notification(notification: Notification) -> None:
    settings = load_settings()
    discord_service = DiscordNotificationService(settings.discord)
    db_service = DatabaseNotificationService(settings.database)

    await discord_service.send(notification)
    await db_service.save(notification)

    message = notification.message
    print(
        f"[{message.channel.platform}] {message.message_type} "
        f"from {message.sender} in {message.channel.name}"
    )


async def run_kick_monitor() -> None:
    settings = load_settings()
    kick_repo = KickChannelRepository(settings.kick)
    kick_ws = KickWebSocketClient(settings.kick)

    channels = await kick_repo.get_monitored_channels()
    if not channels:
        print("No Kick channels configured to monitor")
        return

    print(f"Monitoring {len(channels)} Kick channels...")

    tasks = [
        kick_ws.listen_channel(channel, handle_notification)
        for channel in channels
    ]

    await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    print("Starting Kick monitor and FPS renewal bot...")
    await asyncio.gather(
        run_kick_monitor(),
        run_renewal_bot(),
        return_exceptions=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down monitor...")
