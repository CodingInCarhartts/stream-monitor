"""
Centralized configuration for the stream monitor
"""
import os
from dotenv import load_dotenv

load_dotenv()

KICK_USERNAME = os.getenv('KICK_USERNAME')
PUSHER_APP_KEY = os.getenv('PUSHER_APP_KEY')
PUSHER_CLUSTER = os.getenv('PUSHER_CLUSTER')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
DISCORD_USER_ID = os.getenv('DISCORD_USER_ID')
FPS_RENEWAL_URL = os.getenv('FPS_RENEWAL_URL')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

# Kick configuration
KICK_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"

KICK_CHANNELS_TO_MONITOR = ['angelknivez', 'ayegavmf', 'bigskenger', 'binks', 'camoetoes', 'gioso', 'hoss', 'hutchmf', 'karyn', 'latenightlane', 'lordkebun', 'luiks', 'officialtaco', 'ramee', 'ratedepicz', 'sarah_loopz', 'siglow', 'skillspecs', 'taydoubleyou', 'urlittlemia', 'zombiebarricades']
# Fallback chatroom IDs if API fails
FALLBACK_CHATROOM_IDS = {
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