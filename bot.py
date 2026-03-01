import discord
from discord.ext import commands
from discord import app_commands
import os

GUILD_ID = 1477477283705917503
BOT_ROLE_ID = 1477661066992287958

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ==============================
# SLASH COMMANDS
# ==============================

@bot.tree.command(name="test", description="Test command")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Slash commands working!", ephemeral=True)


# ==============================
# SYNC (RUNS AFTER LOGIN)
# ==============================

@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild.")
    except Exception as e:
        print("Sync error:", e)

    print(f"Logged in as {bot.user}")


TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
