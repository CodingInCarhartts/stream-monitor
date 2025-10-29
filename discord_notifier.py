"""
Discord Notifier - Sends formatted notifications to Discord via webhook
"""
import aiohttp
from datetime import datetime
from config import DISCORD_WEBHOOK_URL

async def send_to_discord(data):
    """
    Send notification to Discord via webhook
    
    Args:
        data: Dictionary with keys:
            - platform: 'Twitch' or 'Kick'
            - type: 'Mention' or 'Reply'
            - channel: Channel name
            - username: User who mentioned/replied
            - message: The message content
            - timestamp: Message timestamp
            - url: Link to the channel
    """
    # Color coding
    color_map = {
        'Twitch': 0x9146FF,  # Twitch purple
        'Kick': 0x53FC18     # Kick green
    }
    
    # Format timestamp
    if isinstance(data['timestamp'], int):
        timestamp = datetime.fromtimestamp(data['timestamp'] / 1000).isoformat()
    else:
        timestamp = data['timestamp']
    
    # Create embed
    embed = {
        'title': f"🔔 {data['type']} on {data['platform']}",
        'description': f"**{data['username']}** {data['type'].lower()}ed you in **{data['channel']}**",
        'color': color_map.get(data['platform'], 0x808080),
        'fields': [
            {
                'name': 'Message',
                'value': data['message'][:1024],  # Discord field limit
                'inline': False
            }
        ],
        'timestamp': timestamp,
        'footer': {
            'text': f"{data['platform']} Notification"
        }
    }

    # Add original message for replies
    if 'original_message' in data and data['original_message']:
        embed['fields'].insert(0, {
            'name': 'Original Message',
            'value': data['original_message'][:1024],
            'inline': False
        })

    # Add emote image if present
    emote_urls = data.get('emote_urls', [])
    if not emote_urls and 'original_emote_urls' in data:
        emote_urls = data['original_emote_urls']
    if emote_urls:
        embed['image'] = {'url': emote_urls[0]}  # Use first emote as image

    # Add other fields
    embed['fields'].extend([
        {
            'name': 'Channel',
            'value': f"[{data['channel']}]({data['url']})",
            'inline': True
        },
        {
            'name': 'User',
            'value': data['username'],
            'inline': True
        }
    ])
    
    payload = {
        'embeds': [embed]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(DISCORD_WEBHOOK_URL, json=payload) as response:
            if response.status != 204:
                print(f'Failed to send Discord notification: {response.status}')
            else:
                print(f'Successfully sent {data["platform"]} notification to Discord')
