import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 1436505351930384434))
USER_ID = int(os.getenv("DISCORD_USER_ID", 499288461472432148))
CONFIG_FILE = "fps_config.json"

# Default config
DEFAULT_CONFIG = {
    "expiration": "2025-11-09T13:25:48",
    "acknowledged": False,
    "message_id": None,
    "renewal_url": "https://panel.fps.ms/server/acc5d845",
}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
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
        config["dm_sent"] = False  # Reset DM sent flag
        save_config(config)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Renewal acknowledged!", ephemeral=True)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def get_remaining():
    config = load_config()
    expiration = datetime.fromisoformat(config["expiration"])
    return expiration - datetime.now()


def format_countdown():
    remaining = get_remaining()
    if remaining <= timedelta(0):
        return "Expired!"
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


async def create_embed(config):
    """Create a visually appealing embed for the renewal status"""
    remaining = get_remaining()

    # Dynamic color based on time remaining
    if remaining <= timedelta(0):
        color = 0xFF0000  # Red for expired
    elif remaining < timedelta(hours=12):
        color = 0xFF6B00  # Orange for critical
    elif remaining < timedelta(hours=24):
        color = 0xFFD700  # Gold for warning
    else:
        color = 0x00FF00  # Green for good

    embed = discord.Embed(
        title="🖥️ FPS Server Renewal Status",
        description="Monitor your server expiration and renewal status",
        color=color,
        timestamp=datetime.now(),
    )

    # Format expiration time nicely
    expiration = datetime.fromisoformat(config["expiration"])
    formatted_expiration = expiration.strftime("%B %d, %Y at %I:%M %p")

    # Add fields with emojis
    embed.add_field(
        name="📅 Expiration Date", value=f"`{formatted_expiration}`", inline=False
    )

    countdown = format_countdown()
    embed.add_field(name="⏳ Time Remaining", value=f"**{countdown}**", inline=True)

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
        value=f"[Click here to renew your server]({config['renewal_url']})",
        inline=False,
    )

    # Add footer with acknowledgment status
    ack_status = (
        "✅ Acknowledged" if config["acknowledged"] else "⏸️ Pending Acknowledgment"
    )
    embed.set_footer(
        text=f"{ack_status} • Last Updated",
        icon_url="https://cdn.discordapp.com/emojis/1234567890.png",  # Optional: Add your server icon
    )

    # Optional: Add thumbnail (you can use your server logo)
    # embed.set_thumbnail(url="YOUR_IMAGE_URL_HERE")

    return embed


async def update_embed():
    config = load_config()
    if config["message_id"] is None:
        return
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        try:
            message = await channel.fetch_message(config["message_id"])
            embed = await create_embed(config)
            remaining = get_remaining()
            view = RenewalView()
            if config.get("dm_sent", False) or (
                remaining < timedelta(hours=1) and remaining > timedelta(0)
            ):
                view.children[0].disabled = False
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            pass


@tasks.loop(seconds=60)
async def countdown_task():
    await update_embed()


@tasks.loop(hours=1)
async def notification_task():
    try:
        remaining = get_remaining()
        config = load_config()
        if (
            remaining < timedelta(hours=12)
            and remaining > timedelta(0)
            and not config["acknowledged"]
        ):
            try:
                user = await bot.fetch_user(USER_ID)
            except Exception as e:
                print(f"Failed to fetch user for DM: {e}")
                return
            if not user:
                print("User not found in cache or via fetch_user")
                return
            try:
                await user.send(
                    f"⚠️ Your FPS server expires soon! Time remaining: {format_countdown()}. Please renew at\n{config['renewal_url']} and acknowledge in the channel."
                )
                config["dm_sent"] = True
                save_config(config)
                print("Sent FPS renewal DM notification")
            except Exception as e:
                print(f"Failed to send DM notification: {e}")
    except Exception as e:
        print(f"notification_task error: {e}")


@bot.event
async def on_ready():
    await tree.sync()
    config = load_config()
    if config["message_id"] is None:
        channel = bot.get_channel(CHANNEL_ID)
        print(f"Channel: {channel}")
        if channel:
            try:
                embed = await create_embed(config)
                view = RenewalView()
                message = await channel.send(embed=embed, view=view)
                config["message_id"] = message.id
                save_config(config)
                print("Message sent successfully")
            except Exception as e:
                print(f"Failed to send message: {e}")
    countdown_task.start()
    notification_task.start()
    print(f"FPS Renewal Bot is ready. Logged in as {bot.user}")


@tree.command(
    name="set_expire",
    description="Set new expiration time (ISO format: YYYY-MM-DDTHH:MM:SS)",
)
async def set_expire(interaction: discord.Interaction, time: str):
    if interaction.user.id != USER_ID:
        await interaction.response.send_message(
            "Only the server owner can set expiration.", ephemeral=True
        )
        return
    try:
        time = time.replace(" ", "T")
        datetime.fromisoformat(time)
        config = load_config()
        config["expiration"] = time
        config["acknowledged"] = False  # Reset acknowledgment
        config["dm_sent"] = False  # Reset DM sent flag
        save_config(config)
        await update_embed()
        await interaction.response.send_message(
            f"Expiration set to {time}", ephemeral=True
        )
    except ValueError:
        await interaction.response.send_message(
            "Invalid time format. Use ISO format: YYYY-MM-DDTHH:MM:SS", ephemeral=True
        )


async def run_renewal_bot():
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set in .env")
        return
    await bot.start(TOKEN)
