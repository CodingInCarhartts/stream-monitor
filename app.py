"""
Main Bot - Runs Kick monitor and FPS renewal bot simultaneously
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import aiohttp
from kick_monitor import run_kick_monitor, get_chatroom_id
from fps_renewal_bot import run_renewal_bot
from config import KICK_CHANNELS_TO_MONITOR

async def main():
    """Run the Kick monitor and renewal bot"""
    # Dynamically generate chatroom IDs
    chatroom_ids = {}
    async with aiohttp.ClientSession() as session:
        for channel in KICK_CHANNELS_TO_MONITOR:
            chatroom_id = await get_chatroom_id(channel, session)
            if chatroom_id:
                chatroom_ids[channel] = str(chatroom_id)

    # Print copyable Go map
    print('var chatroomIDs = map[string]string{')
    for channel, id in chatroom_ids.items():
        print(f'\t"{channel}": "{id}",')
    print('}')

    print('Starting Kick chat monitor and FPS renewal bot...')
    print('Press Ctrl+C to stop\n')

    # Run both concurrently with error isolation
    async def run_kick_with_error_handling():
        try:
            await run_kick_monitor()
        except Exception as e:
            print(f"Kick monitor crashed: {e}")
            # Don't re-raise to prevent killing the other task

    async def run_renewal_with_error_handling():
        try:
            await run_renewal_bot()
        except Exception as e:
            print(f"FPS renewal bot crashed: {e}")
            # Don't re-raise to prevent killing the other task

    # Run both concurrently with error isolation
    await asyncio.gather(
        run_kick_with_error_handling(),
        run_renewal_with_error_handling(),
        return_exceptions=True  # Don't crash if one task fails
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nShutting down monitor...')