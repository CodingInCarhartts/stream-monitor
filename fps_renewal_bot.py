"""
FPS Server Renewal Bot - Standalone Discord Bot
Monitors server expiration and sends renewal reminders.
Run separately from the main stream monitor.
"""

import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
USER_ID = int(os.getenv("DISCORD_USER_ID", 0))
CONFIG_FILE = "fps_config.json"

DEFAULT_CONFIG = {
    "expiration": "2025-12-09T13:25:48",
    "acknowledged": False,
    "message_id": None,
    "renewal_url": "https://panel.fps.ms/server/acc5d845",
    "dm_sent": False,
}

# Minimal intents - only what we need
intents = discord.Intents.default()
intents.message_content = True
intents.members = False
intents.presences = False
intents.typing = False
intents.voice_states = False
intents.reactions = False

# Disable all caching to prevent memory growth
bot = discord.Client(
    intents=intents,
    max_messages=0,  # No message cache
    member_cache_flags=discord.MemberCacheFlags.none(),  # No member cache
)
tree = app_commands.CommandTree(bot)


class RenewalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Acknowledge Renewal", style=discord.ButtonStyle.primary, disabled=True
    )
    async def acknowledge(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != USER_ID:
            await interaction.response.send_message(
                "Only the server owner can acknowledge.", ephemeral=True
            )
            return
        config = load_config()
        config["acknowledged"] = True
        config["dm_sent"] = False
        save_config(config)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Renewal acknowledged!", ephemeral=True)


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_remaining() -> timedelta:
    config = load_config()
    expiration = datetime.fromisoformat(config["expiration"])
    return expiration - datetime.now()


def format_countdown() -> str:
    remaining = get_remaining()
    if remaining <= timedelta(0):
        return "Expired!"
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def create_embed(config: dict) -> discord.Embed:
    """Create renewal status embed."""
    remaining = get_remaining()

    # Color based on urgency
    if remaining <= timedelta(0):
        color = 0xFF0000  # Red
    elif remaining < timedelta(hours=12):
        color = 0xFF6B00  # Orange
    elif remaining < timedelta(hours=24):
        color = 0xFFD700  # Gold
    else:
        color = 0x00FF00  # Green

    embed = discord.Embed(
        title="🖥️ FPS Server Renewal Status",
        description="Monitor your server expiration",
        color=color,
        timestamp=datetime.now(),
    )

    expiration = datetime.fromisoformat(config["expiration"])
    embed.add_field(
        name="📅 Expiration",
        value=f"`{expiration.strftime('%B %d, %Y at %I:%M %p')}`",
        inline=False,
    )
    embed.add_field(
        name="⏳ Time Remaining",
        value=f"**{format_countdown()}**",
        inline=True,
    )

    # Status indicator
    if remaining <= timedelta(0):
        status = "🔴 **EXPIRED**"
    elif remaining < timedelta(hours=12):
        status = "🟠 **CRITICAL**"
    elif remaining < timedelta(hours=24):
        status = "🟡 **WARNING**"
    else:
        status = "🟢 **ACTIVE**"

    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(
        name="🔗 Renewal Portal",
        value=f"[Click here to renew]({config['renewal_url']})",
        inline=False,
    )

    ack = "✅ Acknowledged" if config.get("acknowledged") else "⏸️ Pending"
    embed.set_footer(text=f"{ack} • Last Updated")

    return embed


async def update_embed() -> None:
    """Update the status embed."""
    config = load_config()
    if not config.get("message_id"):
        return
    
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(config["message_id"])
        embed = create_embed(config)
        view = RenewalView()
        
        remaining = get_remaining()
        # Enable button if DM was sent or < 1 hour remaining
        if config.get("dm_sent") or (timedelta(0) < remaining < timedelta(hours=1)):
            view.children[0].disabled = False
        
        await message.edit(embed=embed, view=view)
    except discord.NotFound:
        config["message_id"] = None
        save_config(config)
    except Exception as e:
        print(f"Update error: {e}")


@tasks.loop(seconds=60)
async def countdown_task():
    """Update embed every minute."""
    await update_embed()


@tasks.loop(hours=1)
async def notification_task():
    """Send DM reminder when expiration is near."""
    try:
        remaining = get_remaining()
        config = load_config()
        
        if (
            timedelta(0) < remaining < timedelta(hours=12)
            and not config.get("acknowledged")
            and not config.get("dm_sent")
        ):
            try:
                user = await bot.fetch_user(USER_ID)
                await user.send(
                    f"⚠️ Your FPS server expires soon! Time remaining: {format_countdown()}.\n"
                    f"Please renew at {config['renewal_url']} and acknowledge in the channel."
                )
                config["dm_sent"] = True
                save_config(config)
                print("Sent renewal DM")
            except Exception as e:
                print(f"DM error: {e}")
    except Exception as e:
        print(f"Notification task error: {e}")


@bot.event
async def on_ready():
    await tree.sync()
    config = load_config()
    
    # Create initial message if needed
    if not config.get("message_id"):
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            try:
                embed = create_embed(config)
                view = RenewalView()
                message = await channel.send(embed=embed, view=view)
                config["message_id"] = message.id
                save_config(config)
                print("Created initial message")
            except Exception as e:
                print(f"Failed to create message: {e}")
    
    countdown_task.start()
    notification_task.start()
    print(f"FPS Renewal Bot ready as {bot.user}")


@tree.command(name="set_expire", description="Set expiration time (YYYY-MM-DDTHH:MM:SS)")
async def set_expire(interaction: discord.Interaction, time: str):
    if interaction.user.id != USER_ID:
        await interaction.response.send_message("Unauthorized", ephemeral=True)
        return
    
    try:
        time = time.replace(" ", "T")
        datetime.fromisoformat(time)  # Validate
        config = load_config()
        config["expiration"] = time
        config["acknowledged"] = False
        config["dm_sent"] = False
        save_config(config)
        await update_embed()
        await interaction.response.send_message(f"Expiration set to {time}", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid format. Use YYYY-MM-DDTHH:MM:SS", ephemeral=True)


@bot.event
async def on_message(message):
    if message.author.bot or message.author.id != USER_ID:
        return
    
    if message.content.lower().startswith("set-expire"):
        parts = message.content.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Usage: set-expire YYYY-MM-DDTHH:MM:SS")
            return
        
        time_str = parts[1].strip().replace(" ", "T")
        try:
            datetime.fromisoformat(time_str)
            config = load_config()
            config["expiration"] = time_str
            config["acknowledged"] = False
            config["dm_sent"] = False
            save_config(config)
            await update_embed()
            await message.reply(f"✅ Expiration set to {time_str}")
        except ValueError:
            await message.reply("❌ Invalid format. Use YYYY-MM-DDTHH:MM:SS")
        
        try:
            await message.delete()
        except Exception:
            pass


async def main():
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return
    await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
