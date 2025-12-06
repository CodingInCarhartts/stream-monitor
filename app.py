import asyncio
import gc
import signal
import sys
from contextlib import asynccontextmanager

from core_models import Notification
from settings import load_settings
from kick_service import KickChannelRepository, KickWebSocketClient
from discord_service import DiscordNotificationService
from db_service import DatabaseNotificationService
from fps_renewal_bot import run_renewal_bot
from resource_manager import TaskManager


# Global service instances with proper lifecycle management
discord_service: DiscordNotificationService | None = None
db_service: DatabaseNotificationService | None = None
task_manager = TaskManager()


async def handle_notification(notification: Notification) -> None:
    """Handle notification with proper error handling and resource cleanup"""
    if not discord_service or not db_service:
        return

    try:
        # Send to Discord with error handling
        try:
            await asyncio.wait_for(discord_service.send(notification), timeout=12.0)
        except asyncio.TimeoutError:
            print("Discord notification send timeout, continuing...")
        except Exception as e:
            print(f"Discord notification error: {e}")

        # Save to database with error handling
        try:
            await asyncio.wait_for(db_service.save(notification), timeout=20.0)
        except asyncio.TimeoutError:
            print("Database save timeout, continuing...")
        except Exception as e:
            print(f"Database save error: {e}")

        message = notification.message
        print(
            f"[{message.channel.platform}] {message.message_type} "
            f"from {message.sender} in {message.channel.name}"
        )
    except Exception as e:
        print(f"Error handling notification: {e}")


async def run_kick_monitor() -> None:
    """Run Kick monitor with proper task and resource management"""
    settings = load_settings()
    kick_repo = KickChannelRepository(settings.kick)
    kick_ws = KickWebSocketClient(settings.kick)

    channels = await kick_repo.get_monitored_channels()
    if not channels:
        print("No Kick channels configured to monitor")
        return

    print(f"Monitoring {len(channels)} Kick channels...")

    tasks = []
    try:
        for channel in channels:
            task = await task_manager.create_task(
                kick_ws.listen_channel(channel, handle_notification),
                name=f"kick_monitor_{channel.name}",
            )
            tasks.append(task)

        # Wait for tasks with proper error handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error in channel {i}: {result}")
    except Exception as e:
        print(f"Error in kick monitor: {e}")


async def gc_task():
    """Periodically run garbage collection - run infrequently to avoid interference"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        gc.collect()


async def main() -> None:
    """Main entry point with graceful shutdown and resource cleanup"""
    global discord_service, db_service
    
    # Initialize services
    settings = load_settings()
    discord_service = DiscordNotificationService(settings.discord)
    db_service = DatabaseNotificationService(settings.database)

    # Setup signal handlers for graceful shutdown
    def shutdown_handler() -> None:
        """Handle shutdown signals"""
        print("\nReceived shutdown signal, cleaning up resources...")
        sys.exit(0)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    print("Starting Kick monitor and FPS renewal bot...")
    tasks = []
    try:
        # Create monitored tasks
        tasks.append(
            await task_manager.create_task(run_kick_monitor(), name="kick_monitor")
        )
        tasks.append(
            await task_manager.create_task(run_renewal_bot(), name="fps_renewal_bot")
        )
        # Add periodic garbage collection
        tasks.append(
            await task_manager.create_task(gc_task(), name="gc_task")
        )

        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Task {i} error: {result}")
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        # Cleanup all resources
        print("Cleaning up resources...")
        if discord_service:
            await discord_service.cleanup()
        if db_service:
            await db_service.cleanup()
        await task_manager.cancel_all()
        gc.collect()
        print("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down monitor...")
    except Exception as e:
        print(f"Fatal error: {e}")
