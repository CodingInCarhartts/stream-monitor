"""
Main Bot - Runs both Twitch and Kick monitors simultaneously
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import aiohttp
from kick_monitor import run_kick_monitor, get_chatroom_id
from config import KICK_CHANNELS_TO_MONITOR

async def main():
    """Run the Kick monitor"""
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

    print('Starting Kick chat monitor...')
    print('Press Ctrl+C to stop\n')
    
    # Run the monitor
    await run_kick_monitor()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nShutting down monitor...')
