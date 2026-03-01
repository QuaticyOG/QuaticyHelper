import discord
from discord.ext import commands
from discord import app_commands
import os
import aiosqlite
import io
import re

BOT_ROLE_ID = 1477661066992287958
DB_PATH = "quaticy.db"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# DATABASE
# =========================================================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id INTEGER PRIMARY KEY,
                category_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS open_tickets (
                guild_id INTEGER,
                user_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()

async def get_ticket_category(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT category_id FROM ticket_settings WHERE guild_id=?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_existing_ticket(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT channel_id FROM open_tickets WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# =========================================================
# TRANSCRIPT
# =========================================================
async def generate_transcript(channel: discord.TextChannel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
    data = "\n".join(messages) or "No messages."
    return io.BytesIO(data.encode()), f"transcript-{channel.name}.txt"

# =========================================================
# CLOSE VIEW
# =========================================================
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel

        file_buffer, filename = await generate_transcript(channel)
        await channel.send(file=discord.File(file_buffer, filename))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM open_tickets WHERE channel_id=?", (channel.id,))
            await db.commit()

        await interaction.response.send_message("🔒 Closing ticket...", ephemeral=True)
        await channel.delete()

# =========================================================
# CREATE TICKET
# =========================================================
async def create_ticket(interaction: discord.Interaction, reason: str, extra_info: str | None = None):
    guild = interaction.guild
    user = interaction.user

    # 🔒 duplicate prevention
    existing = await get_existing_ticket(guild.id, user.id)
    if existing:
        ch = guild.get_channel(existing)
        if ch:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {ch.mention}",
                ephemeral=True
            )
            return

    # 📂 get category
    category_id = await get_ticket_category(guild.id)
    if not category_id:
        await interaction.response.send_message(
            "❌ Ticket category not set. Use /setticketcategory",
            ephemeral=True
        )
        return

    category = guild.get_channel(category_id)
    if not category:
        await interaction.response.send_message(
            "❌ Ticket category no longer exists. Please set it again.",
            ephemeral=True
        )
        return

    # 🧠 role-based auto naming (highest role)
    roles = [r for r in user.roles if r != guild.default_role]
    top_role = roles[-1] if roles else None

    role_name = top_role.name if top_role else "client"

    # clean for Discord channel safety
    safe_role = re.sub(r"[^a-z0-9-]", "", role_name.lower().replace(" ", "-"))
    safe_user = re.sub(r"[^a-z0-9-]", "", user.name.lower().replace(" ", "-"))

    channel_name = f"{safe_role}-{safe_user}"[:95]

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    # 💾 save ticket
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO open_tickets (guild_id, user_id, channel_id) VALUES (?, ?, ?)",
            (guild.id, user.id, ticket_channel.id)
        )
        await db.commit()

    # 🎨 embed
    embed = discord.Embed(
        title="🎫 Ticket Opened",
        description=f"{user.mention} thanks for opening a ticket.\n\n**Reason:** {reason}",
        color=discord.Color.blurple()
    )

    if extra_info:
        embed.add_field(name="Submitted Info", value=extra_info[:1024], inline=False)

    embed.set_footer(text="Quaticy Support")
    embed.timestamp = discord.utils.utcnow()

    await ticket_channel.send(content=user.mention, embed=embed, view=CloseTicketView())

    await interaction.response.send_message(
        f"✅ Ticket created: {ticket_channel.mention}",
        ephemeral=True
    )
# =========================================================
# MODAL
# =========================================================
class CustomQuoteModal(discord.ui.Modal, title="Custom Quote Request"):
    member_count = discord.ui.TextInput(label="How many members does your Discord have?", required=True)
    description = discord.ui.TextInput(label="Tell me about your community", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            reason="custom-quote",
            extra_info=f"**Members:** {self.member_count}\n{self.description}"
        )

# =========================================================
# PANEL VIEW
# =========================================================
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Custom Quote", style=discord.ButtonStyle.primary, emoji="💼", custom_id="quote_btn")
    async def custom_quote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomQuoteModal())

    @discord.ui.button(label="Questions", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="question_btn")
    async def questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket(interaction, reason="questions")

# =========================================================
# YOUR ORIGINAL COMMANDS
# =========================================================

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

# =========================================================
# TICKET COMMANDS
# =========================================================
@bot.tree.command(name="setticketcategory", description="Set the category where tickets are created")
@app_commands.describe(category="Category for new tickets")
async def setticketcategory(interaction: discord.Interaction, category: discord.CategoryChannel):

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO ticket_settings (guild_id, category_id) VALUES (?, ?)",
            (interaction.guild.id, category.id)
        )
        await db.commit()

    await interaction.response.send_message(
        f"✅ Tickets will now be created in **{category.name}**",
        ephemeral=True
    )

@bot.tree.command(name="ticketpanel", description="Send the ticket panel")
@app_commands.describe(channel="Channel to send the ticket panel to")
async def ticketpanel(interaction: discord.Interaction, channel: discord.TextChannel):

    embed = discord.Embed(
        title="🎫 Ticket System",
        description="To create a ticket, use one of the buttons below depending on your needs.",
        color=discord.Color.blurple()
    )

    embed.set_footer(text="Quaticy Helper")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Ticket panel sent!", ephemeral=True)

# =========================================================
# EVENTS
# =========================================================
@bot.event
async def setup_hook():
    await init_db()
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())
    await bot.tree.sync()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# =========================================================
# RUN
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
