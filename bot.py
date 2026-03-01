import discord
from discord.ext import commands
from discord import app_commands
import os
import aiosqlite
import io
import re
import html
from discord.utils import utcnow

# =========================================================
# CONFIG
# =========================================================

BOT_ROLE_ID = 1477661066992287958
TRANSCRIPT_CHANNEL_ID = 1477673838996357201
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


async def get_ticket_owner(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM open_tickets WHERE channel_id=?",
            (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


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
# HTML TRANSCRIPT (PREMIUM)
# =========================================================

async def generate_transcript(channel: discord.TextChannel):
    rows = []

    async for msg in channel.history(limit=None, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        author = html.escape(f"{msg.author} ({msg.author.id})")
        content = html.escape(msg.content or "").replace("\n", "<br>")

        # attachments
        attach_html = ""
        if msg.attachments:
            links = [
                f'<a href="{html.escape(a.url)}" target="_blank">{html.escape(a.filename)}</a>'
                for a in msg.attachments
            ]
            attach_html = "<div class='meta'><b>Attachments:</b> " + " • ".join(links) + "</div>"

        # embeds
        embed_html = ""
        if msg.embeds:
            parts = []
            for e in msg.embeds:
                title = html.escape(e.title) if e.title else "Embed"

                desc = ""
                if e.description:
                    desc = html.escape(e.description).replace("\n", "<br>")

                fields_html = ""
                if e.fields:
                    field_parts = []
                    for field in e.fields:
                        fname = html.escape(field.name)
                        fvalue = html.escape(field.value).replace("\n", "<br>")
                        field_parts.append(
                            f"<div class='field'><b>{fname}</b><br>{fvalue}</div>"
                        )
                    fields_html = "".join(field_parts)

                parts.append(
                    f"""
                    <div class='embed'>
                        <b>{title}</b>
                        <div class='embed-desc'>{desc}</div>
                        {fields_html}
                    </div>
                    """
                )

            embed_html = "<div class='meta'><b>Embeds:</b></div>" + "".join(parts)

        jump_html = f"<a class='jump' href='{html.escape(msg.jump_url)}' target='_blank'>Jump</a>"

        if not content and (msg.attachments or msg.embeds):
            content = "<i>(no text)</i>"

        rows.append(f"""
        <div class="msg">
          <div class="head">
            <span class="author">{author}</span>
            <span class="time">{ts}</span>
            {jump_html}
          </div>
          <div class="body">{content}</div>
          {attach_html}
          {embed_html}
        </div>
        """)

    guild_name = html.escape(channel.guild.name)
    channel_name = html.escape(channel.name)

    html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Transcript - #{channel_name}</title>
<style>
body {{
  font-family: system-ui;
  background:#0b0f19;
  color:#e6e6e6;
  padding:24px;
}}
.msg {{
  background:#0f1627;
  border:1px solid #1b2a4a;
  border-radius:14px;
  padding:14px;
  margin:12px 0;
}}
.author {{color:#a9c7ff;font-weight:700}}
.time {{opacity:.7;font-size:12px}}
.jump {{font-size:12px;color:#7aa2ff;text-decoration:none}}
.embed {{margin-top:8px;padding:8px;border-left:4px solid #5865F2;background:rgba(88,101,242,.12)}}
</style>
</head>
<body>
<h2>Transcript • {guild_name} • #{channel_name}</h2>
<p>Exported: {utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
{''.join(rows) if rows else "<i>No messages.</i>"}
</body>
</html>
"""

    return io.BytesIO(html_doc.encode()), f"transcript-{channel.name}.html"

# =========================================================
# TRANSCRIPT BUTTON VIEW
# =========================================================

class TranscriptDownloadView(discord.ui.View):
    def __init__(self, data: bytes, fname: str):
        super().__init__(timeout=None)
        self.data = data
        self.fname = fname

@discord.ui.button(
    label="Download Transcript",
    style=discord.ButtonStyle.secondary,
    emoji="📄",
    custom_id="download_transcript_btn"
)
    async def download(self, interaction: discord.Interaction, button: discord.ui.Button):
        file_obj = io.BytesIO(self.data)
        await interaction.response.send_message(
            file=discord.File(file_obj, self.fname),
            ephemeral=True
        )

# =========================================================
# CLOSE VIEW
# =========================================================

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        guild = interaction.guild
        archive_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)

        owner_id = await get_ticket_owner(channel.id)
        owner_mention = f"<@{owner_id}>" if owner_id else "Unknown"

        file_buffer, filename = await generate_transcript(channel)
        file_buffer.seek(0)
        file_bytes = file_buffer.getvalue()

        if archive_channel:
            embed = discord.Embed(
                title="📁 Ticket Closed",
                description=(
                    f"**Channel:** {channel.name}\n"
                    f"**Opened by:** {owner_mention}\n"
                    f"**Closed by:** {interaction.user.mention}"
                ),
                color=discord.Color.blurple()
            )
            embed.timestamp = utcnow()

            await archive_channel.send(
                embed=embed,
                view=TranscriptDownloadView(file_bytes, filename)
            )

            file_buffer.seek(0)
            await archive_channel.send(file=discord.File(file_buffer, filename))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM open_tickets WHERE channel_id=?",
                (channel.id,)
            )
            await db.commit()

        await channel.delete()

# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(interaction: discord.Interaction, reason: str, extra_info: str | None = None):
    guild = interaction.guild
    user = interaction.user

    existing = await get_existing_ticket(guild.id, user.id)
    if existing:
        ch = guild.get_channel(existing)
        if ch:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {ch.mention}",
                ephemeral=True
            )
            return

    category_id = await get_ticket_category(guild.id)
    if not category_id:
        await interaction.response.send_message(
            "❌ Ticket category not set. Use /setticketcategory",
            ephemeral=True
        )
        return

    category = guild.get_channel(category_id)

    top_role = user.top_role if user.top_role != guild.default_role else None
    role_name = top_role.name if top_role else "client"

    safe_role = re.sub(r"[^a-z0-9-]", "", role_name.lower().replace(" ", "-"))
    safe_user = re.sub(r"[^a-z0-9-]", "", user.name.lower().replace(" ", "-"))

    base_name = f"{safe_role}-{safe_user}"
    channel_name = base_name[:90]

    existing_names = [c.name for c in category.channels]
    counter = 1
    while channel_name in existing_names:
        channel_name = f"{base_name[:85]}-{counter}"
        counter += 1

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

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO open_tickets VALUES (?, ?, ?)",
            (guild.id, user.id, ticket_channel.id)
        )
        await db.commit()

    embed = discord.Embed(
        title="🎫 Ticket Opened",
        description=f"{user.mention} thanks for opening a ticket.\n\n**Reason:** {reason}",
        color=discord.Color.blurple()
    )

    if extra_info:
        embed.add_field(name="Submitted Info", value=extra_info[:1024], inline=False)

    embed.timestamp = utcnow()

    await ticket_channel.send(
        content=user.mention,
        embed=embed,
        view=CloseTicketView()
    )

    await interaction.response.send_message(
        f"✅ Ticket created: {ticket_channel.mention}",
        ephemeral=True
    )

# =========================================================
# MODAL + PANEL
# =========================================================

class CustomQuoteModal(discord.ui.Modal, title="Custom Quote Request"):
    member_count = discord.ui.TextInput(label="How many members does your Discord have?")
    description = discord.ui.TextInput(
        label="Tell me about your community",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            reason="custom-quote",
            extra_info=(
                f"**Server Members:** {self.member_count.value}\n\n"
                f"**Server Info:**\n{self.description.value}"
            )
        )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Custom Quote",
        style=discord.ButtonStyle.primary,
        emoji="💼",
        custom_id="ticket_custom_quote_btn"
    )
    async def custom_quote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomQuoteModal())

    @discord.ui.button(
        label="Questions",
        style=discord.ButtonStyle.secondary,
        emoji="❓",
        custom_id="ticket_questions_btn"
    )
    async def questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket(interaction, reason="questions")

# =========================================================
# SLASH COMMANDS
# =========================================================

@bot.tree.command(name="setticketcategory")
async def setticketcategory(interaction: discord.Interaction, category: discord.CategoryChannel):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO ticket_settings VALUES (?, ?)",
            (interaction.guild.id, category.id)
        )
        await db.commit()

    await interaction.response.send_message(
        f"✅ Tickets will now be created in **{category.name}**",
        ephemeral=True
    )


@bot.tree.command(name="ticketpanel")
async def ticketpanel(interaction: discord.Interaction, channel: discord.TextChannel):

    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Use the buttons below to open a ticket.",
        color=discord.Color.blurple()
    )
    embed.timestamp = utcnow()

    await channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Ticket panel sent!", ephemeral=True)

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

    formatted_name = f"〔 {new_name} 〕"

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

    new_category = await guild.create_category(
        name=formatted_name,
        overwrites=overwrites
    )

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
@app_commands.describe(channel="Channel to send the explanation embed to")
async def channelexplanation(interaction: discord.Interaction, channel: discord.TextChannel):

    embed = discord.Embed(
        title="Channel Explanation",
        description="Below is a brief explanation of what each channel in your category is used for:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="💬 discussion",
        value="This channel is for all general communication between us.",
        inline=False
    )

    embed.add_field(
        name="🚧 progress",
        value="Updates regarding the status of your setup will be posted here.",
        inline=False
    )

    embed.add_field(
        name="📢 notices",
        value="Important notices such as availability updates.",
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
@app_commands.describe(channel="Channel to send the pricing embed to")
async def pricing(interaction: discord.Interaction, channel: discord.TextChannel):

    embed = discord.Embed(
        title="💼 Quaticy Services & Pricing",
        description="Upgrade your Discord experience with professional development and setup services.",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📈 Long-Term Server Management",
        value="💬 Open a ticket for a custom quote.",
        inline=False
    )

    embed.set_footer(text="Quaticy Helper")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Pricing embed sent!", ephemeral=True)
    
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
