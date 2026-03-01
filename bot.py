import discord
from discord.ext import commands
from discord import app_commands
import os

GUILD_ID = 1477477283705917503

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ==============================
# SLASH COMMANDS (MUST BE ABOVE setup_hook)
# ==============================

@bot.tree.command(name="test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Slash commands working!", ephemeral=True)


# ==============================
# SYNC (modern method)
# ==============================

@bot.event
async def setup_hook():
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild.")
    except Exception as e:
        print("Sync error:", e)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
