import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 1436505351930384434))
USER_ID = int(os.getenv('DISCORD_USER_ID', 499288461472432148))
CONFIG_FILE = 'fps_config.json'

# Default config
DEFAULT_CONFIG = {
    "expiration": "2025-11-09T13:25:48",
    "acknowledged": False,
    "message_id": None,
    "renewal_url": "https:panel.fps.ms/server/acc5d845"
}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

class RenewalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Acknowledge Renewal", style=discord.ButtonStyle.primary, disabled=True)
    async def acknowledge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != USER_ID:
            await interaction.response.send_message("Only the server owner can acknowledge.", ephemeral=True)
            return
        config = load_config()
        config['acknowledged'] = True
        save_config(config)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Renewal acknowledged!", ephemeral=True)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_remaining():
    config = load_config()
    expiration = datetime.fromisoformat(config['expiration'])
    return expiration - datetime.now()

def format_countdown():
    remaining = get_remaining()
    if remaining <= timedelta(0):
        return "Expired!"
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

async def update_embed():
    config = load_config()
    if config['message_id'] is None:
        return
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        try:
            message = await channel.fetch_message(config['message_id'])
            embed = discord.Embed(title="FPS Server Renewal Status", color=0x00ff00)
            embed.add_field(name="Expiration Time", value=config['expiration'], inline=False)
            embed.add_field(name="Time Remaining", value=format_countdown(), inline=False)
            embed.add_field(name="Renewal Link", value=f"[Renew Server]({config['renewal_url']})", inline=False)
            remaining = get_remaining()
            view = RenewalView()
            if remaining < timedelta(hours=1) and remaining > timedelta(0):
                view.children[0].disabled = False
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            pass

@tasks.loop(seconds=60)
async def countdown_task():
    await update_embed()

@tasks.loop(hours=1)
async def notification_task():
    remaining = get_remaining()
    config = load_config()
    if remaining < timedelta(hours=1) and remaining > timedelta(0) and not config['acknowledged']:
        user = bot.get_user(USER_ID)
        if user:
            await user.send(f"⚠️ Your FPS server expires soon! Time remaining: {format_countdown()}. Please renew at\n{config['renewal_url']} and acknowledge in the channel.")

@bot.event
async def on_ready():
    await tree.sync()
    config = load_config()
    if config['message_id'] is None:
        channel = bot.get_channel(CHANNEL_ID)
        print(f"Channel: {channel}")
        if channel:
            try:
                embed = discord.Embed(title="FPS Server Renewal Status", color=0x00ff00)
                embed.add_field(name="Expiration Time", value=config['expiration'], inline=False)
                embed.add_field(name="Time Remaining", value=format_countdown(), inline=False)
                embed.add_field(name="Renewal Link", value=f"[Renew Server]({config['renewal_url']})", inline=False)
                view = RenewalView()
                message = await channel.send(embed=embed, view=view)
                config['message_id'] = message.id
                save_config(config)
                print("Message sent successfully")
            except Exception as e:
                print(f"Failed to send message: {e}")
    countdown_task.start()
    notification_task.start()
    print(f'FPS Renewal Bot is ready. Logged in as {bot.user}')

@tree.command(name="set_expire", description="Set new expiration time (ISO format: YYYY-MM-DDTHH:MM:SS)")
async def set_expire(interaction: discord.Interaction, time: str):
    if interaction.user.id != USER_ID:
        await interaction.response.send_message("Only the server owner can set expiration.", ephemeral=True)
        return
    try:
        datetime.fromisoformat(time)
        config = load_config()
        config['expiration'] = time
        config['acknowledged'] = False  # Reset acknowledgment
        save_config(config)
        await update_embed()
        await interaction.response.send_message(f"Expiration set to {time}", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid time format. Use ISO format: YYYY-MM-DDTHH:MM:SS",
ephemeral=True)

async def run_renewal_bot():
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set in .env")
        return
    await bot.start(TOKEN)