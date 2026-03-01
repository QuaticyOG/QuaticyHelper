import discord
from discord.ext import commands
from discord import app_commands
import os

intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(e)

    print(f"Logged in as {bot.user}")


# ==============================
# SLASH: CLONE CATEGORY
# ==============================
@bot.tree.command(name="clonecategory", description="Clone a category and its channels")
@app_commands.describe(
    category_id="The ID of the category to clone",
    new_name="Name for the new category"
)
async def clonecategory(interaction: discord.Interaction, category_id: str, new_name: str):
    await interaction.response.defer()

    guild = interaction.guild
    old_category = guild.get_channel(int(category_id))

    if not old_category or not isinstance(old_category, discord.CategoryChannel):
        await interaction.followup.send("❌ Invalid category ID.")
        return

    new_category = await guild.create_category(
        name=new_name,
        overwrites=old_category.overwrites
    )

    for channel in old_category.channels:
        try:
            if isinstance(channel, discord.TextChannel):
                await guild.create_text_channel(
                    name=channel.name,
                    category=new_category,
                    topic=channel.topic,
                    slowmode_delay=channel.slowmode_delay,
                    overwrites=channel.overwrites,
                    nsfw=channel.nsfw
                )

            elif isinstance(channel, discord.VoiceChannel):
                await guild.create_voice_channel(
                    name=channel.name,
                    category=new_category,
                    bitrate=channel.bitrate,
                    user_limit=channel.user_limit,
                    overwrites=channel.overwrites
                )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to clone {channel.name}: {e}")

    await interaction.followup.send("🎉 Category cloned successfully!")


# ==============================
# SLASH: SEND EMBED
# ==============================
@bot.tree.command(name="sendembed", description="Send an embed to a channel")
@app_commands.describe(
    channel_id="Channel ID to send the embed to",
    title="Embed title",
    description="Embed description"
)
async def sendembed(interaction: discord.Interaction, channel_id: str, title: str, description: str):
    channel = bot.get_channel(int(channel_id))

    if not channel:
        await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )

    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Embed sent!", ephemeral=True)


# ==============================
# RUN BOT
# ==============================
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
