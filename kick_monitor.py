"""
Kick Chat Monitor - Detects mentions and replies using Pusher WebSocket
"""
import asyncio
import websockets
import json
import aiohttp
from config import (
    KICK_USERNAME,
    KICK_CHANNELS_TO_MONITOR,
    PUSHER_APP_KEY,
    PUSHER_CLUSTER,
    KICK_USER_AGENT,
    FALLBACK_CHATROOM_IDS,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
)
from discord_notifier import send_to_discord

# Kick uses Pusher for WebSocket connections
PUSHER_WS_URL = f'wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}?protocol=7&client=js&version=8.4.0-rc2'

# Global session for database operations (reused across all notifications)
_db_session = None

async def get_db_session():
    """Get or create the shared database session"""
    global _db_session
    if _db_session is None or _db_session.closed:
        _db_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
        )
    return _db_session

async def close_db_session():
    """Close the shared database session"""
    global _db_session
    if _db_session and not _db_session.closed:
        await _db_session.close()
        _db_session = None

async def get_chatroom_id(channel_name, session):
    """Get the chatroom ID for a Kick channel"""
    url = f'https://kick.com/api/v2/channels/{channel_name}'
    headers = {
        "User-Agent": KICK_USER_AGENT
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('chatroom', {}).get('id')
    except Exception as e:
        print(f'Error getting chatroom ID for {channel_name}: {e}')
    # Fallback to hardcoded IDs if API fails
    fallback_id = FALLBACK_CHATROOM_IDS.get(channel_name)
    if fallback_id:
        print(f'Using fallback chatroom ID for {channel_name}: {fallback_id}')
        return fallback_id
    return None

async def monitor_kick_channel(channel_name):
    """Monitor a single Kick channel for mentions and replies"""
    async with aiohttp.ClientSession() as session:
        chatroom_id = await get_chatroom_id(channel_name, session)
        if not chatroom_id:
            print(f'Could not get chatroom ID for {channel_name}')
            return
    
    channel = f'chatrooms.{chatroom_id}.v2'
    
    while True:  # Reconnection loop
        try:
            # Add connection timeout and ping/pong handling
            async with websockets.connect(
                PUSHER_WS_URL,
                ping_interval=30,  # Send ping every 30 seconds
                ping_timeout=10,   # Wait 10 seconds for pong
                close_timeout=5    # Close connection within 5 seconds
            ) as websocket:
                print(f'Connected to WebSocket for {channel_name}')
                
                # Wait for connection_established event
                connection_established = False
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        # Handle connection established
                        if data.get('event') == 'pusher:connection_established':
                            print(f'Connection established for {channel_name}')
                            connection_established = True
                            
                            # Now subscribe to the channel
                            subscribe_message = {
                                'event': 'pusher:subscribe',
                                'data': {
                                    'channel': channel
                                }
                            }
                            await websocket.send(json.dumps(subscribe_message))
                            print(f'Subscribed to Kick channel: {channel_name} (chatroom {chatroom_id})')
                            continue
                        
                        # Handle ping/pong
                        if data.get('event') == 'pusher:ping':
                            await websocket.send(json.dumps({'event': 'pusher:pong', 'data': {}}))
                            continue
                        
                        # Check for subscription success
                        if data.get('event') == 'pusher_internal:subscription_succeeded':
                            print(f'Successfully subscribed to {channel_name}')
                            continue
                        
                        # Check for errors
                        if data.get('event') == 'pusher:error':
                            error_data = data.get('data', {})
                            print(f'Pusher error for {channel_name}: {error_data}')
                            continue
                        
                        # Only process messages after connection is established
                        if not connection_established:
                            continue
                        
                         # Check for chat messages
                        if data.get('event') == 'App\\Events\\ChatMessageEvent':
                            msg_data = json.loads(data.get('data', '{}'))

                            # Handle the new structure
                            sender = msg_data.get('sender', {})
                            username = sender.get('username', '')
                            raw_message = str(msg_data.get('content', ''))
                            message_text = raw_message
                            
                            # Skip your own messages
                            if KICK_USERNAME and username and username.lower() == KICK_USERNAME.lower():
                                continue

                            mentioned = False
                            is_reply = False

                            # Check for mention
                            if KICK_USERNAME and f'@{KICK_USERNAME.lower()}' in message_text.lower():
                                mentioned = True

                            # Check if it's a reply to you
                            if msg_data.get('type') == 'reply':
                                original_sender = msg_data.get('metadata', {}).get('original_sender', {})
                                if KICK_USERNAME and original_sender.get('username', '').lower() == KICK_USERNAME.lower():
                                    is_reply = True
                            
                            if mentioned or is_reply:
                                notification_type = "Reply" if is_reply else "Mention"

                                notification_data = {
                                    'platform': 'Kick',
                                    'type': notification_type,
                                    'channel': channel_name,
                                    'username': username,
                                    'message': message_text,
                                    'timestamp': msg_data.get('created_at'),
                                    'url': f'https://kick.com/{channel_name}'
                                }

                                # Add original message for replies
                                if is_reply:
                                    raw_original = msg_data.get('metadata', {}).get('original_message', '')
                                    if isinstance(raw_original, dict):
                                        raw_original = raw_original.get('content', str(raw_original))
                                    else:
                                        raw_original = str(raw_original)
                                    if raw_original:
                                        notification_data['original_message'] = raw_original

                                # Check if send_to_discord is actually async
                                result = send_to_discord(notification_data)
                                if asyncio.iscoroutine(result):
                                    await result

                                # Save to database
                                if SUPABASE_URL and SUPABASE_ANON_KEY:
                                    try:
                                        db_session = await get_db_session()
                                        async with db_session.post(
                                            f"{SUPABASE_URL}/rest/v1/kick_notifications",
                                            json={
                                                "platform": notification_data["platform"],
                                                "type": notification_data["type"],
                                                "channel": notification_data["channel"],
                                                "username": notification_data["username"],
                                                "message": notification_data["message"],
                                                "timestamp": notification_data.get("timestamp"),
                                                "url": notification_data["url"],
                                                "original_message": notification_data.get("original_message")
                                            },
                                            headers={
                                                "apikey": str(SUPABASE_ANON_KEY),
                                                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                                                "Content-Type": "application/json"
                                            }
                                        ) as response:
                                            if response.status == 201:
                                                print("Notification saved to database")
                                            else:
                                                print(f"Failed to save: {response.status} - {await response.text()}")
                                    except Exception as e:
                                        print(f'Error saving to database: {e}')

                                print(f'[Kick] {notification_type} from {username} in {channel_name}')
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f'Error processing Kick message: {e}')
                        
        except websockets.exceptions.ConnectionClosed:
            print(f'WebSocket connection closed for {channel_name}, reconnecting in 5 seconds...')
            await asyncio.sleep(5)
        except Exception as e:
            print(f'Error in WebSocket connection for {channel_name}: {e}')
            await asyncio.sleep(5)

async def run_kick_monitor():
    """Run monitors for all Kick channels"""
    # Start heartbeat task to monitor system health
    async def heartbeat():
        while True:
            print(f"[HEARTBEAT] Kick monitor active - monitoring {len(KICK_CHANNELS_TO_MONITOR)} channels")
            await asyncio.sleep(3600)  # Log every hour

    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        tasks = [monitor_kick_channel(channel) for channel in KICK_CHANNELS_TO_MONITOR]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # Ensure database session is closed on shutdown
        heartbeat_task.cancel()
        await close_db_session()

if __name__ == '__main__':
    asyncio.run(run_kick_monitor())
