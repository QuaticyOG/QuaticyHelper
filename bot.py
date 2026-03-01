import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# ==============================
# CATEGORY CLONER
# ==============================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def clonecategory(ctx, category_id: int, *, new_name: str):
    guild = ctx.guild
    old_category = guild.get_channel(category_id)

    if not old_category or not isinstance(old_category, discord.CategoryChannel):
        await ctx.send("❌ Invalid category ID.")
        return

    # Create new category with custom name
    new_category = await guild.create_category(
        name=new_name,
        overwrites=old_category.overwrites
    )

    await ctx.send(f"✅ Created category **{new_name}**. Cloning channels...")

    # Clone channels
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
            await ctx.send(f"⚠️ Failed to clone {channel.name}: {e}")

    await ctx.send("🎉 Category cloned successfully!")


# ==============================
# SEND EMBED COMMAND
# ==============================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def sendembed(ctx, channel_id: int, title: str, *, description: str):
    channel = bot.get_channel(channel_id)

    if not channel:
        await ctx.send("❌ Invalid channel ID.")
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )

    await channel.send(embed=embed)
    await ctx.send("✅ Embed sent!")


# ==============================
# RUN BOT (Railway safe)
# ==============================
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
