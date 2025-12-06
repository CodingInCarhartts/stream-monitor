import os
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv


load_dotenv()


@dataclass
class KickSettings:
    username: str
    pusher_app_key: str
    pusher_cluster: str
    user_agent: str
    channels: List[str]
    fallback_chatroom_ids: Dict[str, str]


@dataclass
class DiscordSettings:
    bot_token: str
    channel_id: int
    user_id: int
    webhook_url: str


@dataclass
class AppSettings:
    kick: KickSettings
    discord: DiscordSettings


def load_settings() -> AppSettings:
    kick_channels_env = os.getenv("KICK_CHANNELS")
    kick_channels = (
        [c.strip() for c in kick_channels_env.split(",") if c.strip()]
        if kick_channels_env
        else [
            "angelknivez",
            "ayegavmf",
            "bigskenger",
            "binks",
            "camoetoes",
            "gioso",
            "hoss",
            "hutchmf",
            "karyn",
            "latenightlane",
            "lordkebun",
            "luiks",
            "officialtaco",
            "ramee",
            "ratedepicz",
            "sarah_loopz",
            "siglow",
            "skillspecs",
            "taydoubleyou",
            "urlittlemia",
            "zombiebarricades",
        ]
    )

    fallback_chatroom_ids = {
        "angelknivez": "1989830",
        "ayegavmf": "6391",
        "bigskenger": "126607",
        "binks": "1439468",
        "camoetoes": "1545875",
        "gioso": "1275063",
        "hoss": "120323",
        "hutchmf": "13772821",
        "karyn": "57099",
        "latenightlane": "1179480",
        "lordkebun": "56466",
        "luiks": "3074667",
        "officialtaco": "2210588",
        "ramee": "129914",
        "ratedepicz": "2365013",
        "sarah_loopz": "1144544",
        "siglow": "10560368",
        "skillspecs": "3355654",
        "taydoubleyou": "49436398",
        "urlittlemia": "16555624",
        "zombiebarricades": "56479",
    }

    kick = KickSettings(
        username=os.getenv("KICK_USERNAME", ""),
        pusher_app_key=os.getenv("PUSHER_APP_KEY", ""),
        pusher_cluster=os.getenv("PUSHER_CLUSTER", "us2"),
        user_agent=(
            os.getenv(
                "KICK_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/105.0.0.0 Safari/537.36",
            )
        ),
        channels=kick_channels,
        fallback_chatroom_ids=fallback_chatroom_ids,
    )

    discord = DiscordSettings(
        bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
        channel_id=int(os.getenv("DISCORD_CHANNEL_ID", 0)),
        user_id=int(os.getenv("DISCORD_USER_ID", 0)),
        webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
    )

    return AppSettings(kick=kick, discord=discord)
