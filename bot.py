import discord
from discord.ext import commands
from discord import app_commands
import os

GUILD_ID = 1477477283705917503
BOT_ROLE_ID = 1477661066992287958

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ==============================
# SLASH: CLONE CATEGORY (PRIVATE)
# ==============================
@bot.tree.command(name="clonecategory", description="Clone a category privately")
@app_commands.describe(
    category_id="The ID of the category to clone",
    new_name="Name for the new category"
)
async def clonecategory(interaction: discord.Interaction, category_id: str, new_name: str):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    old_category = guild.get_channel(int(category_id))

    if not old_category or not isinstance(old_category, discord.CategoryChannel):
        await interaction.followup.send("❌ Invalid category ID.")
        return

    bot_role = guild.get_role(BOT_ROLE_ID)
    if not bot_role:
        await interaction.followup.send("❌ Bot role not found.")
        return

    # 🔒 PRIVATE OVERWRITES
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True),
        bot_role: discord.PermissionOverwrite(view_channel=True),
    }

    # Create private category
    new_category = await guild.create_category(
        name=new_name,
        overwrites=overwrites
    )

    # Clone channels
    for channel in old_category.channels:
        try:
            if isinstance(channel, discord.TextChannel):
                await guild.create_text_channel(
                    name=channel.name,
                    category=new_category,
                    topic=channel.topic,
                    slowmode_delay=channel.slowmode_delay,
                    nsfw=channel.nsfw
                )

            elif isinstance(channel, discord.VoiceChannel):
                await guild.create_voice_channel(
                    name=channel.name,
                    category=new_category,
                    bitrate=channel.bitrate,
                    user_limit=channel.user_limit
                )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to clone {channel.name}: {e}")

    await interaction.followup.send("🔒 Private category cloned successfully!")


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
# SYNC
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
