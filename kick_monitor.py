"""
Kick Chat Monitor - Minimal memory footprint
Monitors Kick chat channels for mentions and replies via Pusher WebSocket.
"""

import asyncio
import json
from typing import Optional

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed


async def get_chatroom_id(
    session: aiohttp.ClientSession,
    channel: str,
    user_agent: str,
    fallbacks: dict[str, str],
) -> Optional[str]:
    """Get chatroom ID from Kick API with fallback."""
    try:
        async with session.get(
            f"https://kick.com/api/v2/channels/{channel}",
            headers={"User-Agent": user_agent},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return str(data.get("chatroom", {}).get("id"))
    except Exception as e:
        print(f"API error for {channel}: {e}")
    
    # Use fallback if available
    fallback = fallbacks.get(channel)
    if fallback:
        print(f"Using fallback ID for {channel}: {fallback}")
    return fallback


async def send_discord_webhook(
    session: aiohttp.ClientSession,
    webhook_url: str,
    embed: dict,
) -> None:
    """Send embed to Discord webhook - fire and forget."""
    if not webhook_url:
        return
    try:
        async with session.post(
            webhook_url,
            json={"embeds": [embed]},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status not in (200, 204):
                print(f"Discord webhook error: {resp.status}")
    except Exception as e:
        print(f"Discord error: {e}")


async def save_to_supabase(
    session: aiohttp.ClientSession,
    url: str,
    key: str,
    data: dict,
) -> None:
    """Save notification to Supabase - fire and forget."""
    if not url or not key:
        return
    try:
        async with session.post(
            f"{url}/rest/v1/kick_notifications",
            json=data,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 201:
                print(f"Supabase error: {resp.status}")
    except Exception as e:
        print(f"Supabase error: {e}")


async def monitor_channel(
    session: aiohttp.ClientSession,
    channel_name: str,
    chatroom_id: str,
    target_username: str,
    webhook_url: str,
    pusher_url: str,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> None:
    """
    Monitor a single Kick channel for mentions and replies.
    Reconnects automatically on disconnect.
    """
    pusher_channel = f"chatrooms.{chatroom_id}.v2"
    target_lower = target_username.lower()
    
    while True:
        try:
            async with websockets.connect(
                pusher_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                print(f"Connected: {channel_name}")
                subscribed = False
                
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    
                    event = data.get("event")
                    
                    # Handle Pusher protocol
                    if event == "pusher:connection_established":
                        await ws.send(json.dumps({
                            "event": "pusher:subscribe",
                            "data": {"channel": pusher_channel},
                        }))
                        continue
                    
                    if event == "pusher_internal:subscription_succeeded":
                        subscribed = True
                        print(f"Subscribed to {channel_name} ({chatroom_id})")
                        continue
                    
                    if event == "pusher:ping":
                        await ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                        continue
                    
                    if event == "pusher:error":
                        print(f"Pusher error for {channel_name}: {data.get('data')}")
                        continue
                    
                    # Only process chat messages after subscribed
                    if not subscribed:
                        continue
                    
                    if event == "App\\Events\\ChatMessageEvent":
                        # Process message inline - minimal overhead
                        try:
                            msg = json.loads(data.get("data", "{}"))
                        except json.JSONDecodeError:
                            continue
                        
                        username = msg.get("sender", {}).get("username", "")
                        content = str(msg.get("content", ""))
                        
                        # Skip own messages
                        if username.lower() == target_lower:
                            continue
                        
                        # Check for mention
                        is_mention = f"@{target_lower}" in content.lower()
                        
                        # Check for reply to us
                        is_reply = False
                        if msg.get("type") == "reply":
                            original_sender = msg.get("metadata", {}).get("original_sender", {})
                            if original_sender.get("username", "").lower() == target_lower:
                                is_reply = True
                        
                        if not (is_mention or is_reply):
                            continue
                        
                        notification_type = "Reply" if is_reply else "Mention"
                        timestamp = msg.get("created_at", "")
                        
                        # Create Discord embed
                        embed = {
                            "title": f"{notification_type} on Kick",
                            "description": f"**{username}** in **{channel_name}**",
                            "color": 0x53FC18,  # Kick green
                            "fields": [
                                {"name": "Message", "value": content[:1024], "inline": False}
                            ],
                            "url": f"https://kick.com/{channel_name}",
                        }
                        
                        # Add original message for replies
                        if is_reply:
                            original = msg.get("metadata", {}).get("original_message", "")
                            if isinstance(original, dict):
                                original = original.get("content", str(original))
                            if original:
                                embed["fields"].insert(0, {
                                    "name": "Original Message",
                                    "value": str(original)[:1024],
                                    "inline": False,
                                })
                        
                        # Fire and forget - don't wait
                        asyncio.create_task(send_discord_webhook(session, webhook_url, embed))
                        
                        # Optionally save to Supabase
                        if supabase_url and supabase_key:
                            db_data = {
                                "platform": "Kick",
                                "type": notification_type,
                                "channel": channel_name,
                                "username": username,
                                "message": content,
                                "timestamp": timestamp,
                                "url": f"https://kick.com/{channel_name}",
                            }
                            asyncio.create_task(save_to_supabase(session, supabase_url, supabase_key, db_data))
                        
                        print(f"[Kick] {notification_type} from {username} in {channel_name}")
                        
        except ConnectionClosed:
            print(f"WebSocket closed for {channel_name}, reconnecting...")
        except Exception as e:
            print(f"Error for {channel_name}: {e}")
        
        # Wait before reconnecting
        await asyncio.sleep(5)


async def start_monitoring(
    session: aiohttp.ClientSession,
    channels: list[str],
    fallback_ids: dict[str, str],
    target_username: str,
    webhook_url: str,
    pusher_app_key: str,
    pusher_cluster: str,
    user_agent: str,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> None:
    """Start monitoring all channels."""
    pusher_url = (
        f"wss://ws-{pusher_cluster}.pusher.com/app/{pusher_app_key}"
        "?protocol=7&client=js&version=8.4.0-rc2"
    )
    
    # Get chatroom IDs for all channels
    tasks = []
    for channel in channels:
        chatroom_id = await get_chatroom_id(session, channel, user_agent, fallback_ids)
        if chatroom_id:
            task = asyncio.create_task(
                monitor_channel(
                    session=session,
                    channel_name=channel,
                    chatroom_id=chatroom_id,
                    target_username=target_username,
                    webhook_url=webhook_url,
                    pusher_url=pusher_url,
                    supabase_url=supabase_url,
                    supabase_key=supabase_key,
                )
            )
            tasks.append(task)
        else:
            print(f"Skipping {channel} - no chatroom ID")
    
    if not tasks:
        print("No channels to monitor!")
        return
    
    print(f"Monitoring {len(tasks)} channels...")
    await asyncio.gather(*tasks, return_exceptions=True)
