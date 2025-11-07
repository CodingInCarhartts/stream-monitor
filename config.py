"""
Centralized configuration for the stream monitor
"""
import os

from secrets import DISCORD_WEBHOOK_URL, YOUR_KICK_USERNAME, PUSHER_APP_KEY, PUSHER_CLUSTER

# Kick configuration
KICK_CHANNELS_TO_MONITOR = ['zombiebarricades', 'lordkebun', 'skillspecs', 'taydoubleyou', 'hutchmf', 'ramee', 'sarah_loopz', 'karyn', 'gioso', 'binks', 'siglow', 'luiks', 'ayegavmf', 'officialtaco', 'camoetoes', 'angelknivez', 'bigskenger']
KICK_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"

# Fallback chatroom IDs if API fails
FALLBACK_CHATROOM_IDS = {
    "zombiebarricades": "56479",
    "lordkebun": "56466",
    "skillspecs": "3355654",
    "taydoubleyou": "49436398",
    "hutchmf": "13772821",
    "ramee": "129914",
    "sarah_loopz": "1144544",
    "karyn": "57099",
    "gioso": "1275063",
    "binks": "1439468",
    "siglow": "10560368",
    "luiks": "3074667",
    "ayegavmf": "6391",
    "officialtaco": "2210588",
    "camoetoes": "1545875",
    "angelknivez": "1989830",
    "bigskenger": "126607",
}