import discord
from discord.ext import commands
from discord import app_commands
import os

BOT_ROLE_ID = 1477661066992287958  # your bot role ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ==============================
# SLASH: CLONE CATEGORY (PRIVATE)
# ==============================
@bot.tree.command(name="clonecategory", description="Clone a category privately")
@app_commands.describe(
    category_id="The ID of the category to clone",
    new_name="Name for the new category (without brackets)",
    allowed_role="Extra role that can access the category"
)
async def clonecategory(
    interaction: discord.Interaction,
    category_id: str,
    new_name: str,
    allowed_role: discord.Role
):
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

    # 🔥 AUTO FORMAT NAME → 〔 NAME 〕
    formatted_name = f"〔 {new_name} 〕"

    # 🔒 PRIVATE OVERWRITES
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        bot_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        allowed_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
    }

    # Create private category
    new_category = await guild.create_category(
        name=formatted_name,
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
async def sendembed(
    interaction: discord.Interaction,
    channel_id: str,
    title: str,
    description: str
):
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
# SLASH: CHANNEL EXPLANATION EMBED
# ==============================
@bot.tree.command(name="channelexplanation", description="Send the channel explanation embed")
@app_commands.describe(
    channel="Channel to send the explanation embed to"
)
async def channelexplanation(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="Channel Explanation",
        description="Below is a brief explanation of what each channel in your category is used for:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="💬 discussion",
        value="This channel is for all general communication between us. Feel free to ask questions, share ideas, or request changes here.",
        inline=False
    )

    embed.add_field(
        name="🚧 progress",
        value="I will post updates here regarding the status of your setup, including what has been completed and what is in progress.",
        inline=False
    )

    embed.add_field(
        name="📢 notices",
        value="This channel is used for important notices from my side, such as availability updates or schedule changes.",
        inline=False
    )

    embed.set_footer(text="Quaticy Helper")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Explanation embed sent!", ephemeral=True)


# ==============================
# SLASH: PRICING EMBED
# ==============================
@bot.tree.command(name="pricing", description="Send the services & pricing embed")
@app_commands.describe(
    channel="Channel to send the pricing embed to"
)
async def pricing(interaction: discord.Interaction, channel: discord.TextChannel):

    embed = discord.Embed(
        title="💼 Quaticy Services & Pricing",
        description="Upgrade your Discord experience with professional development and setup services.",
        color=discord.Color.blurple()
    )

    # 🤖 BOT DEVELOPMENT
    embed.add_field(
        name="🤖 Custom Bot Development",
        value=(
            "**⚡ Bot Spark — $19**\n"
            "• Up to 3 custom commands\n"
            "• Basic bot setup\n"
            "• 1 moderation command\n"
            "• JSON database\n"
            "• 2-day delivery • 1 revision\n\n"

            "**🔥 Bot Forge — $49**\n"
            "• Up to 8 custom commands\n"
            "• Full moderation system\n"
            "• JSON or SQLite database\n"
            "• Custom embeds • Help command\n"
            "• 3–4 day delivery • 2 revisions\n\n"

            "**👑 Bot Overlord — $99**\n"
            "• Up to 15 custom commands\n"
            "• Advanced systems (tickets, levels, etc.)\n"
            "• SQLite database\n"
            "• Fully customized bot\n"
            "• Priority support\n"
            "• 5–7 day delivery • 3 revisions\n\n"
            "➡️ Order: https://www.quaticy.com/GetYourBot"
        ),
        inline=False
    )

    # 🛠️ SERVER SETUP
    embed.add_field(
        name="🛠️ Professional Server Setup",
        value=(
            "**⚡ Server Spark — $15**\n"
            "• Server creation\n"
            "• Basic channel setup\n"
            "• Basic roles\n"
            "• Rules channel • Welcome message\n"
            "• Clean layout\n"
            "• 2-day delivery • 1 revision\n\n"

            "**🔥 Server Forge — $39**\n"
            "• Everything in Basic\n"
            "• Advanced channel organization\n"
            "• Moderation bot setup\n"
            "• Reaction roles • Auto-mod setup\n"
            "• Permission tuning\n"
            "• 3-day delivery • 2 revisions\n\n"

            "**👑 Server Overlord — $79**\n"
            "• Everything in Standard\n"
            "• Fully customized server design\n"
            "• Ticket system • Level system\n"
            "• Advanced permissions\n"
            "• Full bot integrations\n"
            "• Server optimization • Priority support\n\n"
            "➡️ Order: https://www.quaticy.com/OrderServer"
        ),
        inline=False
    )

    # 📈 LONG TERM
    embed.add_field(
        name="📈 Long-Term Server Management",
        value=(
            "Hire me for ongoing development and maintenance:\n"
            "• Bot development whenever needed\n"
            "• Continuous server improvements\n"
            "• Ongoing technical support\n\n"
            "💬 Open a ticket for a custom quote."
        ),
        inline=False
    )

    embed.set_footer(text="Quaticy Helper")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Pricing embed sent!", ephemeral=True)


# ==============================
# GLOBAL SYNC (clean)
# ==============================
@bot.event
async def setup_hook():
    try:
        synced = await bot.tree.sync()
        print(f"Globally synced {len(synced)} commands.")
    except Exception as e:
        print("Sync error:", e)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# ==============================
# RUN BOT
# ==============================
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
