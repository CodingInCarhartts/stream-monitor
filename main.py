"""
Stream Monitor - Main Entry Point
Monitors Kick chat channels for mentions/replies and sends Discord notifications.
"""

import asyncio
import resource
import signal
import sys
from contextlib import asynccontextmanager

import aiohttp

from settings import load_settings
from kick_monitor import start_monitoring


async def log_memory() -> None:
    """Periodically log memory usage for debugging."""
    while True:
        await asyncio.sleep(60)
        # ru_maxrss is in KB on Linux
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_mb = mem_kb / 1024
        print(f"[Memory] {mem_mb:.1f} MB")


@asynccontextmanager
async def managed_session():
    """Create a properly managed aiohttp session."""
    # Use conservative connection limits
    connector = aiohttp.TCPConnector(
        limit=20,  # Total connection limit
        limit_per_host=5,  # Per-host limit
        ttl_dns_cache=300,  # DNS cache TTL
        enable_cleanup_closed=True,  # Clean up closed connections
    )
    timeout = aiohttp.ClientTimeout(total=30)
    session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    try:
        yield session
    finally:
        await session.close()
        # Give time for connections to close gracefully
        await asyncio.sleep(0.25)


async def run_kick_monitor(session: aiohttp.ClientSession) -> None:
    """Run the Kick chat monitor."""
    settings = load_settings()
    
    await start_monitoring(
        session=session,
        channels=settings.kick.channels,
        fallback_ids=settings.kick.fallback_chatroom_ids,
        target_username=settings.kick.username,
        webhook_url=settings.discord.webhook_url,
        pusher_app_key=settings.kick.pusher_app_key,
        pusher_cluster=settings.kick.pusher_cluster,
        user_agent=settings.kick.user_agent,
        supabase_url=settings.database.url,
        supabase_key=settings.database.anon_key,
    )


async def main() -> None:
    """Main entry point."""
    print("Starting Stream Monitor...")
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    
    def shutdown():
        print("\nShutdown signal received...")
        for task in asyncio.all_tasks(loop):
            task.cancel()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown)
    
    async with managed_session() as session:
        # Start memory logging and kick monitor
        memory_task = asyncio.create_task(log_memory())
        monitor_task = asyncio.create_task(run_kick_monitor(session))
        
        try:
            await asyncio.gather(memory_task, monitor_task)
        except asyncio.CancelledError:
            print("Tasks cancelled, shutting down...")
        except Exception as e:
            print(f"Fatal error: {e}")
        finally:
            memory_task.cancel()
            monitor_task.cancel()
            print("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
