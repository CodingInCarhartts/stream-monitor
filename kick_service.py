import asyncio
import json
from datetime import datetime
from typing import Awaitable, Callable

import aiohttp
import websockets

from core_models import Channel, Message, Notification
from settings import KickSettings


class KickChannelRepository:
    def __init__(self, settings: KickSettings):
        self.settings = settings

    async def get_channel_id(self, channel_name: str) -> str | None:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"https://kick.com/api/v2/channels/{channel_name}",
                    headers={"User-Agent": self.settings.user_agent},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return str(data.get("chatroom", {}).get("id"))
            except Exception as e:
                print(f"Error getting chatroom ID for {channel_name}: {e}")

        fallback = self.settings.fallback_chatroom_ids.get(channel_name)
        if fallback:
            print(f"Using fallback chatroom ID for {channel_name}: {fallback}")
        return fallback

    async def get_monitored_channels(self) -> list[Channel]:
        channels: list[Channel] = []
        for name in self.settings.channels:
            chatroom_id = await self.get_channel_id(name)
            if chatroom_id:
                channels.append(Channel(name=name, id=chatroom_id, platform="Kick"))
        return channels


class KickWebSocketClient:
    def __init__(self, settings: KickSettings):
        self.settings = settings
        self.ws_url = (
            f"wss://ws-{settings.pusher_cluster}.pusher.com/app/{settings.pusher_app_key}"
            "?protocol=7&client=js&version=8.4.0-rc2"
        )

    async def listen_channel(
        self,
        channel: Channel,
        handler: Callable[[Notification], Awaitable[None]],
    ) -> None:
        pusher_channel = f"chatrooms.{channel.id}.v2"

        while True:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as websocket:
                    print(f"Connected to WebSocket for {channel.name}")
                    await self._run_loop(websocket, channel, pusher_channel, handler)
            except websockets.exceptions.ConnectionClosed:
                print(
                    f"WebSocket connection closed for {channel.name}, "
                    "reconnecting in 5 seconds...",
                )
                await asyncio.sleep(5)
            except Exception as e:
                print(
                    f"Error in WebSocket connection for {channel.name}: {e}. "
                    "Reconnecting in 5 seconds...",
                )
                await asyncio.sleep(5)

    async def _run_loop(
        self,
        websocket: websockets.WebSocketClientProtocol,
        channel: Channel,
        pusher_channel: str,
        handler: Callable[[Notification], Awaitable[None]],
    ) -> None:
        connection_established = False

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event")

            if event == "pusher:connection_established" and not connection_established:
                connection_established = True
                await websocket.send(
                    json.dumps(
                        {
                            "event": "pusher:subscribe",
                            "data": {"channel": pusher_channel},
                        }
                    )
                )
                continue

            if event == "pusher:ping":
                await websocket.send(
                    json.dumps({"event": "pusher:pong", "data": {}})
                )
                continue

            if event == "pusher_internal:subscription_succeeded":
                print(f"Subscribed to {channel.name} ({channel.id})")
                continue

            if event == "pusher:error":
                print(f"Pusher error for {channel.name}: {data.get('data')}")
                continue

            if not connection_established:
                continue

            if event == "App\\Events\\ChatMessageEvent":
                await self._handle_chat_message(data, channel, handler)

    async def _handle_chat_message(
        self,
        envelope: dict,
        channel: Channel,
        handler: Callable[[Notification], Awaitable[None]],
    ) -> None:
        try:
            msg_data = json.loads(envelope.get("data", "{}"))
        except json.JSONDecodeError:
            return

        sender_info = msg_data.get("sender", {})
        username = str(sender_info.get("username", ""))
        raw_content = msg_data.get("content", "")
        content = str(raw_content)

        if (
            self.settings.username
            and username
            and username.lower() == self.settings.username.lower()
        ):
            return

        message_type = self._get_message_type(msg_data, content)
        if not message_type:
            return

        timestamp = msg_data.get("created_at") or datetime.utcnow().isoformat()

        message = Message(
            content=content,
            sender=username,
            timestamp=timestamp,
            channel=channel,
            message_type=message_type,
        )

        original_message = None
        if message_type == "Reply":
            raw_original = msg_data.get("metadata", {}).get(
                "original_message", ""
            )
            if isinstance(raw_original, dict):
                raw_original = raw_original.get("content", str(raw_original))
            original_message = str(raw_original) if raw_original else None

        notification = Notification(
            message=message,
            original_message=original_message,
            url=f"https://kick.com/{channel.name}",
        )

        await handler(notification)

    def _get_message_type(self, msg_data: dict, content: str) -> str | None:
        if (
            self.settings.username
            and f"@{self.settings.username.lower()}" in content.lower()
        ):
            return "Mention"

        if msg_data.get("type") == "reply":
            original_sender = msg_data.get("metadata", {}).get(
                "original_sender", {}
            )
            if (
                self.settings.username
                and str(original_sender.get("username", "")).lower()
                == self.settings.username.lower()
            ):
                return "Reply"

        return None
