"""
Kick Chat Monitor - Detects mentions and replies using Pusher WebSocket
"""
import asyncio
import websockets
import json
import aiohttp
import re
from config import (
    YOUR_KICK_USERNAME,
    KICK_CHANNELS_TO_MONITOR,
    PUSHER_APP_KEY,
    PUSHER_CLUSTER,
    KICK_USER_AGENT,
    FALLBACK_CHATROOM_IDS,
)
from discord_notifier import send_to_discord

async def get_emote_url(emote_name, emote_id, session):
    """Get emote image URL, preferring 7TV by name, fallback to Kick by ID"""
    # Try 7TV first via GraphQL
    gql_query = f'{{ emotes(query: "{emote_name}", limit: 1, sort: {{ value: "popularity", order: DESCENDING }}) {{ items {{ id name host {{ url files {{ name }} }} }} }} }}'
    try:
        async with session.post('https://7tv.io/v3/gql', json={'query': gql_query}, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                items = data.get('data', {}).get('emotes', {}).get('items', [])
                if items:
                    emote = items[0]
                    host = emote.get('host', {})
                    if host:
                        base_url = host.get('url', '')
                        files = host.get('files', [])
                        # Find 1x.webp
                        for file in files:
                            if file.get('name') == '1x.webp':
                                url = base_url + '/' + file['name']
                                if url.startswith('//'):
                                    url = 'https:' + url
                                return url
                        # If not found, take first file
                        if files:
                            url = base_url + '/' + files[0]['name']
                            if url.startswith('//'):
                                url = 'https:' + url
                            return url
    except Exception:
        pass
    # Fallback to Kick
    return f"https://files.kick.com/emotes/{emote_id}/fullsize.webp"

async def process_emotes(message, session):
    """Parse emote tags and return processed message with emote URLs"""
    emote_urls = []
    # Since re.sub doesn't support async, we need to process sequentially
    emote_matches = re.findall(r'\[emote:(\d+):(\w+)\]', message)
    processed_message = re.sub(r'\[emote:(\d+):(\w+)\]', r':\2:', message)
    for emote_id, emote_name in emote_matches:
        url = await get_emote_url(emote_name, emote_id, session)
        emote_urls.append(url)
    return processed_message, emote_urls

# Configuration
CHANNELS_TO_MONITOR = KICK_CHANNELS_TO_MONITOR

# Kick uses Pusher for WebSocket connections
PUSHER_WS_URL = f'wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}?protocol=7&client=js&version=8.4.0-rc2'

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
            async with websockets.connect(PUSHER_WS_URL) as websocket:
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
                            message_text, emote_urls = await process_emotes(raw_message, session)
                            
                            # Skip your own messages
                            if username.lower() == YOUR_KICK_USERNAME.lower():
                                continue
                            
                            mentioned = False
                            is_reply = False
                            
                            # Check for mention
                            if f'@{YOUR_KICK_USERNAME.lower()}' in message_text.lower():
                                mentioned = True
                            
                            # Check if it's a reply to you
                            if msg_data.get('type') == 'reply':
                                original_sender = msg_data.get('metadata', {}).get('original_sender', {})
                                if original_sender.get('username', '').lower() == YOUR_KICK_USERNAME.lower():
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
                                    'url': f'https://kick.com/{channel_name}',
                                    'emote_urls': emote_urls
                                }

                                # Add original message for replies
                                if is_reply:
                                    raw_original = msg_data.get('metadata', {}).get('original_message', '')
                                    if isinstance(raw_original, dict):
                                        raw_original = raw_original.get('content', str(raw_original))
                                    else:
                                        raw_original = str(raw_original)
                                    original_message, original_emotes = await process_emotes(raw_original, session)
                                    if original_message:
                                        notification_data['original_message'] = original_message
                                        notification_data['original_emote_urls'] = original_emotes

                                # Check if send_to_discord is actually async
                                result = send_to_discord(notification_data)
                                if asyncio.iscoroutine(result):
                                    await result

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
    tasks = [monitor_kick_channel(channel) for channel in CHANNELS_TO_MONITOR]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(run_kick_monitor())
