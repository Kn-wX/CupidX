# cogs/ticket.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ticket System — Full Featured
#  Commands:
#    /ticket setup   — Interactive setup (multi-buttons)
#    /ticket edit    — Edit existing config
#    /ticket config  — View current configuration
#    /ticket setlog  — Set log channel
#    /ticket open    — Open a ticket
#    /ticket close   — Close current ticket
#    /ticket transcript — Save transcript
#    /ticket reset   — Reset all ticket data
#  Features:
#    → Multi-button panel (e.g. Staff Apply, General Support)
#    → Banner shown when ticket is opened
#    → Per-button ticket type tracking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import io
import os
import json
from utils.detectfile import *
from datetime import datetime

try:
    from utils.config import BANNER_URL
except ImportError:
    BANNER_URL = None

# ══════════════════════════════════════
# EMOJIS
# ══════════════════════════════════════
EMOJI_TICKET     = EMOJI_CURRENCY
EMOJI_LOCK       = EMOJI_KEY
EMOJI_UNLOCK     = EMOJI_SHUFFLE
EMOJI_CLAIM      = EMOJI_FREEZE
EMOJI_TRANSCRIPT = EMOJI_APP2
EMOJI_DELETE     = EMOJI_TRASH
EMOJI_SUCCESS    = EMOJI_TICK
EMOJI_ERROR      = EMOJI_CROSS
EMOJI_WARN       = EMOJI_WARN
EMOJI_RECYCLE    = EMOJI_LOADING
EMOJI_ATTACH     = EMOJI_BOND2
EMOJI_SETTINGS   = "<:cog:1487152125069889677>"
EMOJI_INFO       = EMOJI_SIGN

# ══════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════
EMBED_COLOR  = 0x2b2d31
DB_PATH      = "db/ticket.db"
TICKET_LIMIT = 5
MAX_BUTTONS  = 5   # max buttons per panel (Discord limit is 5 per row)

# Banner shown INSIDE the ticket when user opens it
TICKET_OPEN_BANNER = (
    "https://cdn.discordapp.com/attachments/1472594595664891926/"
    "1490031700976079053/file_000000003eb471fa85def201fef56adb.png"
    "?ex=69d293a8&is=69d14228&hm=4df29b7840551f244211478cde3d120208d5d8e0a3755a9f01df105f75ecad00&"
)

os.makedirs("db", exist_ok=True)


# ══════════════════════════════════════
# DATABASE
# ══════════════════════════════════════

async def db_exec(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()

async def db_one(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

async def db_all(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return await cur.fetchall()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS configs (
                guild_id            INTEGER PRIMARY KEY,
                log_channel_id      INTEGER,
                support_roles       TEXT,
                support_role_id     INTEGER,
                closed_cat_id       INTEGER,
                open_cat_id         INTEGER,
                panel_image         TEXT,
                panel_description   TEXT,
                panel_title         TEXT,
                button_label        TEXT,
                embed_color         TEXT,
                buttons             TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id   INTEGER PRIMARY KEY,
                guild_id     INTEGER,
                creator_id   INTEGER,
                ticket_num   INTEGER,
                is_closed    INTEGER DEFAULT 0,
                opened_at    TEXT,
                closed_at    TEXT,
                ticket_type  TEXT
            );
            CREATE TABLE IF NOT EXISTS open_counts (
                guild_id  INTEGER,
                user_id   INTEGER,
                count     INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()

        migrations = [
            ("tickets", "is_closed",        "INTEGER DEFAULT 0"),
            ("tickets", "opened_at",         "TEXT"),
            ("tickets", "closed_at",         "TEXT"),
            ("tickets", "creator_id",        "INTEGER"),
            ("tickets", "ticket_num",        "INTEGER"),
            ("tickets", "ticket_type",       "TEXT"),
            ("configs", "closed_cat_id",     "INTEGER"),
            ("configs", "open_cat_id",       "INTEGER"),
            ("configs", "log_channel_id",    "INTEGER"),
            ("configs", "support_roles",     "TEXT"),
            ("configs", "support_role_id",   "INTEGER"),
            ("configs", "panel_image",       "TEXT"),
            ("configs", "panel_description", "TEXT"),
            ("configs", "panel_title",       "TEXT"),
            ("configs", "button_label",      "TEXT"),
            ("configs", "embed_color",       "TEXT"),
            ("configs", "buttons",           "TEXT"),
        ]
        for table, col, col_type in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass


# ══════════════════════════════════════
# SAFE INTERACTION HELPERS
# ══════════════════════════════════════

async def safe_defer(interaction: discord.Interaction, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass

async def safe_send(interaction: discord.Interaction, **kwargs):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except Exception:
        pass


# ══════════════════════════════════════
# HELPERS
# ══════════════════════════════════════

def parse_color(hex_str: str) -> int:
    try:
        return int(str(hex_str).strip().lstrip("#"), 16)
    except Exception:
        return EMBED_COLOR

def get_support_roles(cfg, guild: discord.Guild):
    roles = []
    if not cfg:
        return roles
    if cfg["support_roles"]:
        try:
            ids = json.loads(cfg["support_roles"])
            for rid in ids:
                r = guild.get_role(int(rid))
                if r:
                    roles.append(r)
        except Exception:
            pass
    if not roles and cfg["support_role_id"]:
        r = guild.get_role(cfg["support_role_id"])
        if r:
            roles.append(r)
    return roles

def is_staff(member: discord.Member, cfg) -> bool:
    if member.guild_permissions.manage_channels:
        return True
    roles = get_support_roles(cfg, member.guild)
    member_ids = {r.id for r in member.roles}
    return any(r.id in member_ids for r in roles)

def make_embed(title: str, description: str, color: int = EMBED_COLOR, image_url: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    if image_url:
        embed.set_image(url=image_url)
    elif BANNER_URL:
        embed.set_image(url=BANNER_URL)
    return embed

def get_buttons_list(cfg) -> list:
    """
    Returns list of button dicts.
    Format: [{"label": "General Support", "emoji": "🎫"}, ...]
    Falls back to old single button_label if no multi-buttons set.
    """
    if cfg and cfg["buttons"]:
        try:
            btns = json.loads(cfg["buttons"])
            if isinstance(btns, list) and len(btns) > 0:
                return btns
        except Exception:
            pass
    # Legacy fallback
    label = (cfg["button_label"] if cfg else None) or "Open a Ticket"
    return [{"label": label, "emoji": EMOJI_TICKET}]

async def get_log_channel(guild: discord.Guild):
    row = await db_one("SELECT log_channel_id FROM configs WHERE guild_id=?", (guild.id,))
    if row and row["log_channel_id"]:
        return guild.get_channel(row["log_channel_id"])
    return None

async def log_action(guild: discord.Guild, user: discord.Member, action: str, detail: str):
    ch = await get_log_channel(guild)
    if not ch:
        return
    embed = discord.Embed(
        title=f"{EMOJI_TICKET} {action}",
        description=detail,
        color=EMBED_COLOR,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"By: {user.display_name}")
    try:
        await ch.send(embed=embed)
    except Exception:
        pass

async def get_or_create_open_category(guild: discord.Guild) -> discord.CategoryChannel:
    row = await db_one("SELECT open_cat_id FROM configs WHERE guild_id=?", (guild.id,))
    if row and row["open_cat_id"]:
        cat = guild.get_channel(row["open_cat_id"])
        if cat:
            return cat
    cat = await guild.create_category(
        f"{EMOJI_TICKET} Open Tickets",
        overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    )
    await db_exec(
        "INSERT INTO configs (guild_id, open_cat_id) VALUES (?,?) "
        "ON CONFLICT(guild_id) DO UPDATE SET open_cat_id=excluded.open_cat_id",
        (guild.id, cat.id)
    )
    return cat

async def get_or_create_closed_category(guild: discord.Guild) -> discord.CategoryChannel:
    row = await db_one("SELECT closed_cat_id FROM configs WHERE guild_id=?", (guild.id,))
    if row and row["closed_cat_id"]:
        cat = guild.get_channel(row["closed_cat_id"])
        if cat:
            return cat
    cat = await guild.create_category(
        f"{EMOJI_LOCK} Closed Tickets",
        overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    )
    await db_exec(
        "INSERT INTO configs (guild_id, closed_cat_id) VALUES (?,?) "
        "ON CONFLICT(guild_id) DO UPDATE SET closed_cat_id=excluded.closed_cat_id",
        (guild.id, cat.id)
    )
    return cat


# ══════════════════════════════════════
# TICKET OPEN FLOW
# ══════════════════════════════════════

async def open_ticket(interaction: discord.Interaction, cog, ticket_type: str = "General Support"):
    await safe_defer(interaction, ephemeral=True)

    guild = interaction.guild
    user  = interaction.user

    row = await db_one("SELECT count FROM open_counts WHERE guild_id=? AND user_id=?", (guild.id, user.id))
    if row and row["count"] >= TICKET_LIMIT:
        return await safe_send(interaction,
            content=f"{EMOJI_ERROR} You already have **{TICKET_LIMIT}** open tickets. Close one first.",
            ephemeral=True)

    cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (guild.id,))
    if not cfg:
        return await safe_send(interaction,
            content=f"{EMOJI_ERROR} Ticket system not set up yet. Ask an admin to run `/ticket setup`.",
            ephemeral=True)

    row2  = await db_one("SELECT MAX(ticket_num) as n FROM tickets WHERE guild_id=?", (guild.id,))
    t_num = (row2["n"] or 0) + 1

    support_roles = get_support_roles(cfg, guild)
    color         = parse_color(cfg["embed_color"]) if cfg["embed_color"] else EMBED_COLOR

    # Channel name: include ticket type as slug
    type_slug = ticket_type.lower().replace(" ", "-")[:12]
    ch_name   = f"ticket-{t_num:04d}-{type_slug}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user:               discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me:           discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_messages=True),
    }
    pings = [user.mention]
    for role in support_roles:
        overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        pings.append(role.mention)

    try:
        open_cat = await get_or_create_open_category(guild)
    except Exception:
        open_cat = None

    try:
        ch = await guild.create_text_channel(
            name=ch_name,
            overwrites=overwrites,
            category=open_cat
        )
    except discord.Forbidden:
        return await safe_send(interaction, content=f"{EMOJI_ERROR} Missing permission to create channels.", ephemeral=True)
    except Exception as e:
        return await safe_send(interaction, content=f"{EMOJI_ERROR} Failed: `{e}`", ephemeral=True)

    await db_exec(
        "INSERT INTO tickets VALUES (?,?,?,?,0,?,NULL,?)",
        (ch.id, guild.id, user.id, t_num, datetime.now().isoformat(), ticket_type)
    )
    await db_exec(
        "INSERT INTO open_counts VALUES (?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET count=count+1",
        (guild.id, user.id)
    )

    custom_desc  = cfg["panel_description"] or "**Please describe your issue in detail.**"
    panel_title  = cfg["panel_title"]       or f"{EMOJI_TICKET} Ticket"

    ticket_desc = (
        f"Welcome {user.mention}! Staff has been notified.\n\n"
        f"**Type:** {ticket_type}\n\n"
        f"{custom_desc}\n\n"
        f"Use the buttons below to manage this ticket."
    )

    # Always use TICKET_OPEN_BANNER inside the ticket channel
    embed = discord.Embed(
        title=f"{panel_title} — #{t_num:04d}",
        description=ticket_desc,
        color=color,
        timestamp=datetime.now()
    )
    embed.set_image(url=TICKET_OPEN_BANNER)
    embed.add_field(name="Opened By", value=user.mention,  inline=True)
    embed.add_field(name="Ticket #",  value=str(t_num),    inline=True)
    embed.add_field(name="Type",      value=ticket_type,   inline=True)

    await ch.send(content=" ".join(pings), embed=embed, view=OpenTicketView(cog, ch.id))
    await safe_send(interaction, content=f"{EMOJI_SUCCESS} Your ticket: {ch.mention}", ephemeral=True)
    await log_action(guild, user, "Ticket Opened", f"{ch.mention} — Type: **{ticket_type}**")


# ══════════════════════════════════════
# SETUP STATE — in-memory per guild
# ══════════════════════════════════════
_setup_state: dict[int, dict] = {}

# Default buttons list for new setups
DEFAULT_BUTTONS = [
    {"label": "General Support", "emoji": "🎫"},
    {"label": "Staff Apply",     "emoji": "📋"},
]

def build_setup_preview(state: dict) -> discord.Embed:
    desc    = state.get("description")  or "*(not set)*"
    img     = state.get("image")        or None
    ttl     = state.get("title")        or "*(not set)*"
    roles   = state.get("roles", [])
    buttons = state.get("buttons", DEFAULT_BUTTONS)

    role_str = ", ".join(r.mention for r in roles) if roles else "*(none)*"

    btn_lines = "\n".join(
        f"`{i+1}.` {b.get('emoji','🎫')} **{b['label']}**"
        for i, b in enumerate(buttons)
    ) or "*(none)*"

    embed = discord.Embed(
        title="🎫 Ticket Setup — Live Preview",
        color=EMBED_COLOR,
        description=(
            f"**Channel:** {state['channel'].mention}\n"
            f"**Support Roles:** {role_str}\n\n"
            f"**Panel Title:** {ttl}\n"
            f"**Description:** {desc[:100] + '...' if len(str(desc)) > 100 else desc}\n"
            f"**Image:** {'✅ Set' if img else '*(not set)*'}\n\n"
            f"**Buttons ({len(buttons)}):**\n{btn_lines}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Use the dropdown to configure each option.*\n"
            f"*Click ✅ **Confirm & Send** when done.*"
        )
    )
    if img:
        embed.set_image(url=img)
    return embed


# ══════════════════════════════════════
# SETUP DROPDOWN VIEW
# ══════════════════════════════════════

class SetupDropdownView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog      = cog
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="⚙️ Select what to configure...",
        custom_id="setup_select",
        options=[
            discord.SelectOption(label="📝 Set Description",  value="description", description="Custom text shown on the ticket panel"),
            discord.SelectOption(label="🖼️ Set Image URL",    value="image",       description="Banner image for the ticket panel"),
            discord.SelectOption(label="✏️ Set Panel Title",  value="title",       description="Title of the ticket panel embed"),
            discord.SelectOption(label="➕ Add Button",        value="add_button",  description="Add a ticket button (e.g. Staff Apply)"),
            discord.SelectOption(label="🗑️ Remove Button",    value="del_button",  description="Remove a button by number"),
            discord.SelectOption(label="✏️ Edit Button",      value="edit_button", description="Edit label/emoji of an existing button"),
        ]
    )
    async def select_option(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]
        state = _setup_state.setdefault(self.guild_id, {})

        if value == "add_button":
            btns = state.get("buttons", list(DEFAULT_BUTTONS))
            if len(btns) >= MAX_BUTTONS:
                return await interaction.response.send_message(
                    f"{EMOJI_ERROR} Maximum **{MAX_BUTTONS}** buttons allowed.", ephemeral=True)
            await interaction.response.send_modal(AddButtonModal(self.cog, self.guild_id))

        elif value == "del_button":
            btns = state.get("buttons", list(DEFAULT_BUTTONS))
            if not btns:
                return await interaction.response.send_message(
                    f"{EMOJI_ERROR} No buttons to remove.", ephemeral=True)
            await interaction.response.send_modal(RemoveButtonModal(self.cog, self.guild_id))

        elif value == "edit_button":
            btns = state.get("buttons", list(DEFAULT_BUTTONS))
            if not btns:
                return await interaction.response.send_message(
                    f"{EMOJI_ERROR} No buttons to edit.", ephemeral=True)
            await interaction.response.send_modal(EditButtonModal(self.cog, self.guild_id))

        else:
            await interaction.response.send_modal(SetupModal(self.cog, self.guild_id, value))

    @discord.ui.button(label="✅ Confirm & Send Panel", style=discord.ButtonStyle.success, custom_id="setup_confirm", row=1)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        state = _setup_state.get(self.guild_id)
        if not state:
            return await interaction.followup.send(
                f"{EMOJI_ERROR} Setup expired. Run `/ticket setup` again.", ephemeral=True)

        guild   = interaction.guild
        channel = state["channel"]
        roles   = state.get("roles", [])
        desc    = state.get("description") or "Click a button below to open a support ticket."
        image   = state.get("image")
        title   = state.get("title")       or f"{EMOJI_TICKET} Support Tickets"
        buttons = state.get("buttons",     list(DEFAULT_BUTTONS))

        role_ids    = json.dumps([r.id for r in roles])
        buttons_json = json.dumps(buttons)

        # Auto-create categories
        try:
            open_cat   = await get_or_create_open_category(guild)
            closed_cat = await get_or_create_closed_category(guild)
        except Exception as e:
            return await interaction.followup.send(
                f"{EMOJI_ERROR} Could not create categories: `{e}`", ephemeral=True)

        # Save to DB
        await db_exec(
            "INSERT INTO configs "
            "(guild_id, support_roles, open_cat_id, closed_cat_id, panel_description, panel_image, panel_title, button_label, buttons) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET "
            "support_roles=excluded.support_roles, "
            "open_cat_id=excluded.open_cat_id, "
            "closed_cat_id=excluded.closed_cat_id, "
            "panel_description=excluded.panel_description, "
            "panel_image=excluded.panel_image, "
            "panel_title=excluded.panel_title, "
            "button_label=excluded.button_label, "
            "buttons=excluded.buttons",
            (guild.id, role_ids, open_cat.id, closed_cat.id, desc, image, title, buttons[0]["label"] if buttons else "Open a Ticket", buttons_json)
        )

        # Send panel to channel
        panel_embed = make_embed(title=title, description=desc, image_url=image)
        panel_view  = PanelView(self.cog, buttons)
        await channel.send(embed=panel_embed, view=panel_view)

        # Register view for persistence
        self.cog.bot.add_view(panel_view)

        # Disable setup message
        try:
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
        except Exception:
            pass

        # Confirmation embed
        btn_list = "\n".join(f"• {b.get('emoji','🎫')} {b['label']}" for b in buttons)
        info = discord.Embed(title=f"{EMOJI_SUCCESS} Ticket System Ready!", color=0x57F287)
        info.add_field(name="📢 Panel Channel",   value=channel.mention,  inline=True)
        info.add_field(name="📁 Open Category",   value=open_cat.name,    inline=True)
        info.add_field(name="🔒 Closed Category", value=closed_cat.name,  inline=True)
        roles_val = ", ".join(r.mention for r in roles) if roles else "None"
        info.add_field(name="👥 Support Roles",   value=roles_val,        inline=False)
        info.add_field(name="✏️ Panel Title",     value=title,            inline=True)
        info.add_field(name="🖼️ Image",           value="Set ✅" if image else "Not set", inline=True)
        info.add_field(name=f"🎛️ Buttons ({len(buttons)})", value=btn_list or "None", inline=False)
        await interaction.followup.send(embed=info, ephemeral=True)
        _setup_state.pop(self.guild_id, None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, custom_id="setup_cancel", row=1)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        _setup_state.pop(self.guild_id, None)
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(
                content=f"{EMOJI_ERROR} Setup cancelled.", embed=None, view=self)
        except Exception:
            await safe_send(interaction, content=f"{EMOJI_ERROR} Setup cancelled.", ephemeral=True)

    async def on_timeout(self):
        _setup_state.pop(self.guild_id, None)


# ══════════════════════════════════════
# SETUP MODALS
# ══════════════════════════════════════

class SetupModal(discord.ui.Modal):
    field_input = discord.ui.TextInput(
        label="Value",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    FIELD_CONFIG = {
        "description": ("📝 Set Panel Description", "e.g. Open a ticket for support!", discord.TextStyle.paragraph, 1000),
        "image":       ("🖼️ Set Image URL",          "https://example.com/banner.png",  discord.TextStyle.short,     500),
        "title":       ("✏️ Set Panel Title",         "e.g. 🎫 Support Tickets",          discord.TextStyle.short,     100),
    }

    def __init__(self, cog, guild_id: int, field: str):
        lbl, ph, style, maxlen = self.FIELD_CONFIG[field]
        super().__init__(title=lbl)
        self.cog      = cog
        self.guild_id = guild_id
        self.field    = field
        self.field_input.label       = lbl
        self.field_input.placeholder = ph
        self.field_input.style       = style
        self.field_input.max_length  = maxlen

    async def on_submit(self, interaction: discord.Interaction):
        value = self.field_input.value.strip()

        if self.field == "image":
            if not (value.startswith("https://") or value.startswith("http://")):
                return await interaction.response.send_message(
                    f"{EMOJI_ERROR} Image URL must start with `https://`", ephemeral=True)

        state = _setup_state.setdefault(self.guild_id, {})
        state[self.field] = value

        embed = build_setup_preview(state)
        try:
            await interaction.response.edit_message(embed=embed)
        except Exception:
            try:
                await interaction.response.defer()
                await interaction.edit_original_response(embed=embed)
            except Exception:
                pass


class AddButtonModal(discord.ui.Modal, title="➕ Add Ticket Button"):
    btn_label = discord.ui.TextInput(
        label="Button Label",
        placeholder="e.g. Staff Apply",
        max_length=80,
        required=True
    )
    btn_emoji = discord.ui.TextInput(
        label="Button Emoji (optional)",
        placeholder="e.g. 📋  (leave blank for 🎫)",
        max_length=10,
        required=False
    )

    def __init__(self, cog, guild_id: int):
        super().__init__()
        self.cog      = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        state = _setup_state.setdefault(self.guild_id, {})
        if "buttons" not in state:
            state["buttons"] = list(DEFAULT_BUTTONS)

        label = self.btn_label.value.strip()
        emoji = self.btn_emoji.value.strip() or EMOJI_TICKET

        state["buttons"].append({"label": label, "emoji": emoji})

        embed = build_setup_preview(state)
        try:
            await interaction.response.edit_message(embed=embed)
        except Exception:
            await interaction.response.defer()
            await interaction.edit_original_response(embed=embed)


class RemoveButtonModal(discord.ui.Modal, title="🗑️ Remove Button"):
    btn_number = discord.ui.TextInput(
        label="Button Number to Remove",
        placeholder="e.g. 2  (see numbers in preview)",
        max_length=2,
        required=True
    )

    def __init__(self, cog, guild_id: int):
        super().__init__()
        self.cog      = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        state = _setup_state.setdefault(self.guild_id, {})
        if "buttons" not in state:
            state["buttons"] = list(DEFAULT_BUTTONS)

        try:
            idx = int(self.btn_number.value.strip()) - 1
            if 0 <= idx < len(state["buttons"]):
                removed = state["buttons"].pop(idx)
                embed = build_setup_preview(state)
                try:
                    await interaction.response.edit_message(embed=embed)
                except Exception:
                    await interaction.response.defer()
                    await interaction.edit_original_response(embed=embed)
            else:
                await interaction.response.send_message(
                    f"{EMOJI_ERROR} Invalid number. Must be between 1 and {len(state['buttons'])}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                f"{EMOJI_ERROR} Please enter a valid number.", ephemeral=True)


class EditButtonModal(discord.ui.Modal, title="✏️ Edit Button"):
    btn_number = discord.ui.TextInput(
        label="Button Number to Edit",
        placeholder="e.g. 1",
        max_length=2,
        required=True
    )
    btn_label = discord.ui.TextInput(
        label="New Label",
        placeholder="e.g. General Support",
        max_length=80,
        required=True
    )
    btn_emoji = discord.ui.TextInput(
        label="New Emoji (optional)",
        placeholder="e.g. 🎫",
        max_length=10,
        required=False
    )

    def __init__(self, cog, guild_id: int):
        super().__init__()
        self.cog      = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        state = _setup_state.setdefault(self.guild_id, {})
        if "buttons" not in state:
            state["buttons"] = list(DEFAULT_BUTTONS)

        try:
            idx = int(self.btn_number.value.strip()) - 1
            if 0 <= idx < len(state["buttons"]):
                state["buttons"][idx]["label"] = self.btn_label.value.strip()
                if self.btn_emoji.value.strip():
                    state["buttons"][idx]["emoji"] = self.btn_emoji.value.strip()
                embed = build_setup_preview(state)
                try:
                    await interaction.response.edit_message(embed=embed)
                except Exception:
                    await interaction.response.defer()
                    await interaction.edit_original_response(embed=embed)
            else:
                await interaction.response.send_message(
                    f"{EMOJI_ERROR} Invalid number.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                f"{EMOJI_ERROR} Please enter a valid number.", ephemeral=True)


# ══════════════════════════════════════
# EDIT MODALS (for /ticket edit)
# ══════════════════════════════════════

class EditFieldModal(discord.ui.Modal):
    field_input = discord.ui.TextInput(
        label="New Value",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    FIELD_CONFIG = {
        "description": ("📝 Edit Panel Description", "e.g. Open a ticket for support!", discord.TextStyle.paragraph, 1000),
        "image":       ("🖼️ Edit Image URL",          "https://example.com/banner.png",  discord.TextStyle.short,     500),
        "title":       ("✏️ Edit Panel Title",         "e.g. 🎫 Support Tickets",          discord.TextStyle.short,     100),
        "add_button":  ("➕ Add Button",               "Label | emoji  (emoji optional)",  discord.TextStyle.short,     100),
        "del_button":  ("🗑️ Remove Button",            "Enter button number (1, 2, ...)",  discord.TextStyle.short,     2),
    }

    def __init__(self, cog, guild_id: int, field: str):
        lbl, ph, style, maxlen = self.FIELD_CONFIG[field]
        super().__init__(title=lbl)
        self.cog      = cog
        self.guild_id = guild_id
        self.field    = field
        self.field_input.label       = "New Value"
        self.field_input.placeholder = ph
        self.field_input.style       = style
        self.field_input.max_length  = maxlen

    async def on_submit(self, interaction: discord.Interaction):
        value = self.field_input.value.strip()
        await interaction.response.defer(ephemeral=True)

        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (self.guild_id,))
        if not cfg:
            return await interaction.followup.send(
                f"{EMOJI_ERROR} No config found. Run `/ticket setup` first.", ephemeral=True)

        if self.field == "description":
            await db_exec("UPDATE configs SET panel_description=? WHERE guild_id=?", (value, self.guild_id))
            await interaction.followup.send(f"{EMOJI_SUCCESS} Description updated.", ephemeral=True)

        elif self.field == "image":
            if not (value.startswith("https://") or value.startswith("http://")):
                return await interaction.followup.send(
                    f"{EMOJI_ERROR} Image URL must start with `https://`", ephemeral=True)
            await db_exec("UPDATE configs SET panel_image=? WHERE guild_id=?", (value, self.guild_id))
            await interaction.followup.send(f"{EMOJI_SUCCESS} Image updated.", ephemeral=True)

        elif self.field == "title":
            await db_exec("UPDATE configs SET panel_title=? WHERE guild_id=?", (value, self.guild_id))
            await interaction.followup.send(f"{EMOJI_SUCCESS} Panel title updated.", ephemeral=True)

        elif self.field == "add_button":
            # Format: "Label | emoji" or just "Label"
            parts   = value.split("|", 1)
            label   = parts[0].strip()
            emoji   = parts[1].strip() if len(parts) > 1 else EMOJI_TICKET
            btns    = get_buttons_list(cfg)
            if len(btns) >= MAX_BUTTONS:
                return await interaction.followup.send(
                    f"{EMOJI_ERROR} Maximum **{MAX_BUTTONS}** buttons allowed.", ephemeral=True)
            btns.append({"label": label, "emoji": emoji})
            await db_exec("UPDATE configs SET buttons=? WHERE guild_id=?", (json.dumps(btns), self.guild_id))
            await interaction.followup.send(f"{EMOJI_SUCCESS} Button **{emoji} {label}** added.", ephemeral=True)

        elif self.field == "del_button":
            btns = get_buttons_list(cfg)
            try:
                idx = int(value) - 1
                if 0 <= idx < len(btns):
                    removed = btns.pop(idx)
                    await db_exec("UPDATE configs SET buttons=? WHERE guild_id=?", (json.dumps(btns), self.guild_id))
                    await interaction.followup.send(
                        f"{EMOJI_SUCCESS} Button **{removed['label']}** removed.", ephemeral=True)
                else:
                    await interaction.followup.send(
                        f"{EMOJI_ERROR} Invalid number. Must be 1–{len(btns)}.", ephemeral=True)
            except ValueError:
                await interaction.followup.send(f"{EMOJI_ERROR} Enter a valid number.", ephemeral=True)


# ══════════════════════════════════════
# PANEL VIEW  (persistent — multi-button)
# ══════════════════════════════════════

class PanelView(discord.ui.View):
    def __init__(self, cog, buttons: list = None):
        super().__init__(timeout=None)
        self.cog = cog

        if not buttons:
            buttons = [{"label": "Open a Ticket", "emoji": EMOJI_TICKET}]

        for i, btn_data in enumerate(buttons[:MAX_BUTTONS]):
            label = btn_data.get("label", "Open a Ticket")
            emoji = btn_data.get("emoji", EMOJI_TICKET)
            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                custom_id=f"tkt_open_{i}_{label[:20].replace(' ', '_').lower()}"
            )
            # Capture ticket_type in closure
            btn.callback = self._make_callback(label)
            self.add_item(btn)

    def _make_callback(self, ticket_type: str):
        async def callback(interaction: discord.Interaction):
            await open_ticket(interaction, self.cog, ticket_type=ticket_type)
        return callback


# ══════════════════════════════════════
# OPEN TICKET VIEW  (persistent)
# ══════════════════════════════════════

class OpenTicketView(discord.ui.View):
    def __init__(self, cog, ch_id: int):
        super().__init__(timeout=None)
        self.cog   = cog
        self.ch_id = ch_id

    @discord.ui.button(label="Close", emoji=EMOJI_LOCK, style=discord.ButtonStyle.danger, custom_id="tkt_close")
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        t   = await db_one("SELECT * FROM tickets WHERE channel_id=?", (interaction.channel.id,))
        cfg = await db_one("SELECT * FROM configs  WHERE guild_id=?",  (interaction.guild.id,))
        if not t:
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Not a ticket channel.", ephemeral=True)
        if not is_staff(interaction.user, cfg) and interaction.user.id != t["creator_id"]:
            return await safe_send(interaction, content=f"{EMOJI_ERROR} No permission to close.", ephemeral=True)

        creator = interaction.guild.get_member(t["creator_id"])
        if creator:
            try:
                await interaction.channel.set_permissions(creator, view_channel=False, send_messages=False)
            except Exception:
                pass
            await db_exec(
                "UPDATE open_counts SET count=MAX(0,count-1) WHERE guild_id=? AND user_id=?",
                (interaction.guild.id, creator.id)
            )

        try:
            closed_cat = await get_or_create_closed_category(interaction.guild)
            await interaction.channel.edit(category=closed_cat)
        except Exception:
            pass

        await db_exec(
            "UPDATE tickets SET is_closed=1, closed_at=? WHERE channel_id=?",
            (datetime.now().isoformat(), interaction.channel.id)
        )

        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

        embed = make_embed(
            title=f"{EMOJI_LOCK} Ticket Closed",
            description=(
                f"Closed by {interaction.user.mention}.\n\n"
                "Staff can **Reopen**, save **Transcript**, or **Delete** this ticket."
            ),
            color=0xff4444
        )
        if creator:
            embed.add_field(name="Creator",   value=creator.mention,         inline=True)
        embed.add_field(    name="Closed By", value=interaction.user.mention, inline=True)

        await interaction.channel.send(embed=embed, view=ClosedTicketView(self.cog, interaction.channel.id))
        await safe_send(interaction, content=f"{EMOJI_SUCCESS} Ticket closed.", ephemeral=True)
        await log_action(interaction.guild, interaction.user, "Ticket Closed", interaction.channel.mention)
        self.stop()

    @discord.ui.button(label="Claim", emoji=EMOJI_CLAIM, style=discord.ButtonStyle.success, custom_id="tkt_claim")
    async def btn_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (interaction.guild.id,))
        if not is_staff(interaction.user, cfg):
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Only staff can claim tickets.", ephemeral=True)
        await safe_send(interaction,
            content=f"{EMOJI_CLAIM} {interaction.user.mention} has claimed this ticket.",
            ephemeral=False)
        await log_action(interaction.guild, interaction.user, "Ticket Claimed", interaction.channel.mention)

    @discord.ui.button(label="Transcript", emoji=EMOJI_TRANSCRIPT, style=discord.ButtonStyle.secondary, custom_id="tkt_trans_open")
    async def btn_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        await send_transcript(interaction)


# ══════════════════════════════════════
# CLOSED TICKET VIEW  (persistent)
# ══════════════════════════════════════

class ClosedTicketView(discord.ui.View):
    def __init__(self, cog, ch_id: int):
        super().__init__(timeout=None)
        self.cog   = cog
        self.ch_id = ch_id

    @discord.ui.button(label="Reopen", emoji=EMOJI_UNLOCK, style=discord.ButtonStyle.success, custom_id="tkt_reopen")
    async def btn_reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (interaction.guild.id,))
        if not is_staff(interaction.user, cfg):
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Only staff can reopen.", ephemeral=True)

        t = await db_one("SELECT * FROM tickets WHERE channel_id=?", (interaction.channel.id,))
        if not t:
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Ticket not found.", ephemeral=True)

        creator = interaction.guild.get_member(t["creator_id"])
        if creator:
            try:
                await interaction.channel.set_permissions(creator, view_channel=True, send_messages=True)
            except Exception:
                pass
            await db_exec(
                "INSERT INTO open_counts VALUES (?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET count=count+1",
                (interaction.guild.id, creator.id)
            )

        try:
            open_cat = await get_or_create_open_category(interaction.guild)
            await interaction.channel.edit(category=open_cat)
        except Exception:
            pass

        await db_exec(
            "UPDATE tickets SET is_closed=0, closed_at=NULL WHERE channel_id=?",
            (interaction.channel.id,)
        )

        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

        embed = make_embed(
            title=f"{EMOJI_UNLOCK} Ticket Reopened",
            description=f"Reopened by {interaction.user.mention}."
        )
        await interaction.channel.send(embed=embed, view=OpenTicketView(self.cog, interaction.channel.id))
        await safe_send(interaction, content=f"{EMOJI_SUCCESS} Ticket reopened.", ephemeral=True)
        await log_action(interaction.guild, interaction.user, "Ticket Reopened", interaction.channel.mention)
        self.stop()

    @discord.ui.button(label="Transcript", emoji=EMOJI_TRANSCRIPT, style=discord.ButtonStyle.primary, custom_id="tkt_trans_closed")
    async def btn_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (interaction.guild.id,))
        if not is_staff(interaction.user, cfg):
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Only staff can save transcripts.", ephemeral=True)
        await send_transcript(interaction)

    @discord.ui.button(label="Delete", emoji=EMOJI_DELETE, style=discord.ButtonStyle.danger, custom_id="tkt_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_defer(interaction, ephemeral=True)
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (interaction.guild.id,))
        if not is_staff(interaction.user, cfg):
            return await safe_send(interaction, content=f"{EMOJI_ERROR} Only staff can delete tickets.", ephemeral=True)
        await send_transcript(interaction)
        await log_action(interaction.guild, interaction.user, "Ticket Deleted", interaction.channel.mention)
        await db_exec("DELETE FROM tickets WHERE channel_id=?", (interaction.channel.id,))
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass
        self.stop()


# ══════════════════════════════════════
# TRANSCRIPT HELPER
# ══════════════════════════════════════

async def send_transcript(interaction: discord.Interaction):
    try:
        msgs = [m async for m in interaction.channel.history(limit=None, oldest_first=True)]
    except Exception as e:
        return await safe_send(interaction, content=f"{EMOJI_ERROR} Could not fetch messages: `{e}`", ephemeral=True)

    lines = [f"Transcript — {interaction.channel.name} — {interaction.guild.name}", "=" * 50]
    for m in msgs:
        line = f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.display_name}: {m.clean_content}"
        for att in m.attachments:
            line += f"\n  {EMOJI_ATTACH} {att.url}"
        lines.append(line)

    file_bytes = "\n".join(lines).encode("utf-8")
    file = discord.File(io.BytesIO(file_bytes), filename=f"transcript-{interaction.channel.name}.txt")

    try:
        await interaction.user.send(
            f"{EMOJI_TRANSCRIPT} Transcript for `{interaction.channel.name}` in **{interaction.guild.name}**:",
            file=file
        )
        await safe_send(interaction, content=f"{EMOJI_SUCCESS} Transcript sent to your DMs.", ephemeral=True)
    except discord.Forbidden:
        file2 = discord.File(io.BytesIO(file_bytes), filename=f"transcript-{interaction.channel.name}.txt")
        try:
            await interaction.followup.send(
                f"{EMOJI_WARN} Could not DM. Here is the transcript:", file=file2, ephemeral=True)
        except Exception:
            pass
    except Exception as e:
        await safe_send(interaction, content=f"{EMOJI_ERROR} Failed: `{e}`", ephemeral=True)


# ══════════════════════════════════════
# COG
# ══════════════════════════════════════

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await init_db()
        # Re-register all persistent panel views on startup
        try:
            all_cfgs = await db_all("SELECT guild_id, buttons, button_label FROM configs")
            for cfg in all_cfgs:
                btns = get_buttons_list(cfg)
                self.bot.add_view(PanelView(self, btns))
        except Exception:
            self.bot.add_view(PanelView(self))

        try:
            open_tickets   = await db_all("SELECT channel_id FROM tickets WHERE is_closed=0")
            closed_tickets = await db_all("SELECT channel_id FROM tickets WHERE is_closed=1")
            for t in open_tickets:
                self.bot.add_view(OpenTicketView(self, t["channel_id"]))
            for t in closed_tickets:
                self.bot.add_view(ClosedTicketView(self, t["channel_id"]))
        except Exception as e:
            print(f"[TicketCog] View re-register skipped: {e}")

    # ══════════════════════════════════════
    # COMMANDS
    # ══════════════════════════════════════

    @commands.hybrid_group(name="ticket", description="Ticket system commands.", invoke_without_command=True)
    @commands.guild_only()
    async def ticket(self, ctx: commands.Context):
        embed = discord.Embed(title=f"{EMOJI_TICKET} Ticket System", color=EMBED_COLOR)
        embed.add_field(name="⚙️ Setup & Config", value=(
            f"`/ticket setup #channel @role...` — Interactive setup\n"
            f"`/ticket edit` — Edit existing ticket config\n"
            f"`/ticket config` — View current configuration\n"
            f"`/ticket setlog #channel` — Set log channel\n"
            f"`/ticket reset` — Reset all ticket data"
        ), inline=False)
        embed.add_field(name="🎫 Ticket Actions", value=(
            f"`/ticket open` — Open a ticket\n"
            f"`/ticket close` — Close current ticket\n"
            f"`/ticket transcript` — Save transcript"
        ), inline=False)
        await ctx.reply(embed=embed)

    # ── Setup ──

    @ticket.command(name="setup", description="Interactive ticket system setup with multi-buttons.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Channel to send the ticket panel in",
        role1="Support role 1",
        role2="Support role 2 (optional)",
        role3="Support role 3 (optional)",
        role4="Support role 4 (optional)",
        role5="Support role 5 (optional)",
    )
    async def cmd_setup(self, ctx: commands.Context,
                        channel: discord.TextChannel,
                        role1: discord.Role = None,
                        role2: discord.Role = None,
                        role3: discord.Role = None,
                        role4: discord.Role = None,
                        role5: discord.Role = None):

        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]

        _setup_state[ctx.guild.id] = {
            "channel":     channel,
            "roles":       roles,
            "description": None,
            "image":       None,
            "title":       None,
            "buttons":     list(DEFAULT_BUTTONS),
        }

        embed = build_setup_preview(_setup_state[ctx.guild.id])

        if ctx.interaction:
            await ctx.interaction.response.send_message(
                embed=embed,
                view=SetupDropdownView(self, ctx.guild.id),
                ephemeral=True
            )
        else:
            await ctx.reply(
                embed=embed,
                view=SetupDropdownView(self, ctx.guild.id)
            )

    # ── Edit ──

    @ticket.command(name="edit", description="Edit your existing ticket system configuration.")
    @commands.has_permissions(manage_guild=True)
    async def cmd_edit(self, ctx: commands.Context):
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (ctx.guild.id,))
        if not cfg:
            return await ctx.reply(
                f"{EMOJI_ERROR} No ticket config found. Run `ticket setup` first.")

        btns    = get_buttons_list(cfg)
        btn_lines = "\n".join(
            f"`{i+1}.` {b.get('emoji','🎫')} **{b['label']}**"
            for i, b in enumerate(btns)
        ) or "*(none)*"

        embed = discord.Embed(
            title=f"{EMOJI_SETTINGS} Edit Ticket Config",
            color=EMBED_COLOR,
            description=(
                f"**Current Panel Title:** {cfg['panel_title'] or '*(not set)*'}\n"
                f"**Description:** {(cfg['panel_description'] or '')[:80]}{'...' if len(cfg['panel_description'] or '') > 80 else ''}\n"
                f"**Image:** {'✅ Set' if cfg['panel_image'] else '*(not set)*'}\n\n"
                f"**Buttons ({len(btns)}):**\n{btn_lines}\n\n"
                f"Select a field below to edit it."
            )
        )

        view = EditDropdownView(self, ctx.guild.id)

        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.reply(embed=embed, view=view)

    # ── Config ──

    @ticket.command(name="config", description="View the current ticket system configuration.")
    @commands.has_permissions(manage_guild=True)
    async def cmd_config(self, ctx: commands.Context):
        cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (ctx.guild.id,))
        if not cfg:
            return await ctx.reply(
                f"{EMOJI_ERROR} No ticket config found. Run `/ticket setup` first.")

        guild = ctx.guild
        btns  = get_buttons_list(cfg)

        support_roles = get_support_roles(cfg, guild)
        roles_val     = ", ".join(r.mention for r in support_roles) if support_roles else "*(none)*"

        open_cat   = guild.get_channel(cfg["open_cat_id"])   if cfg["open_cat_id"]   else None
        closed_cat = guild.get_channel(cfg["closed_cat_id"]) if cfg["closed_cat_id"] else None
        log_ch     = guild.get_channel(cfg["log_channel_id"]) if cfg["log_channel_id"] else None

        btn_lines = "\n".join(
            f"• {b.get('emoji','🎫')} {b['label']}" for b in btns
        ) or "*(none)*"

        # Count tickets
        total_row  = await db_one("SELECT COUNT(*) as n FROM tickets WHERE guild_id=?", (guild.id,))
        open_row   = await db_one("SELECT COUNT(*) as n FROM tickets WHERE guild_id=? AND is_closed=0", (guild.id,))
        closed_row = await db_one("SELECT COUNT(*) as n FROM tickets WHERE guild_id=? AND is_closed=1", (guild.id,))

        embed = discord.Embed(
            title=f"{EMOJI_INFO} Ticket System Configuration",
            color=EMBED_COLOR,
            timestamp=datetime.now()
        )
        embed.add_field(name="📢 Panel Title",      value=cfg["panel_title"] or "*(not set)*",      inline=True)
        embed.add_field(name="🖼️ Panel Image",      value="Set ✅" if cfg["panel_image"] else "Not set", inline=True)
        embed.add_field(name="📝 Description",      value=(cfg["panel_description"] or "*(not set)*")[:100], inline=False)
        embed.add_field(name="👥 Support Roles",    value=roles_val,                                 inline=False)
        embed.add_field(name="📁 Open Category",    value=open_cat.mention   if open_cat   else "*(not created)*", inline=True)
        embed.add_field(name="🔒 Closed Category",  value=closed_cat.mention if closed_cat else "*(not created)*", inline=True)
        embed.add_field(name="📋 Log Channel",      value=log_ch.mention     if log_ch     else "*(not set)*",     inline=True)
        embed.add_field(name=f"🎛️ Buttons ({len(btns)})", value=btn_lines,                          inline=False)
        embed.add_field(name="📊 Total Tickets",    value=str(total_row["n"]  if total_row  else 0), inline=True)
        embed.add_field(name="✅ Open Tickets",     value=str(open_row["n"]   if open_row   else 0), inline=True)
        embed.add_field(name="🔒 Closed Tickets",   value=str(closed_row["n"] if closed_row else 0), inline=True)
        embed.set_footer(text=f"Server: {guild.name}")

        await ctx.reply(embed=embed)

    # ── Set Log Channel ──

    @ticket.command(name="setlog", description="Set the log channel for ticket actions.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Channel to send logs to")
    async def cmd_setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        await db_exec(
            "INSERT INTO configs (guild_id, log_channel_id) VALUES (?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET log_channel_id=excluded.log_channel_id",
            (ctx.guild.id, channel.id)
        )
        await ctx.reply(f"{EMOJI_SUCCESS} Log channel set to {channel.mention}.")

    # ── Open ──

    @ticket.command(name="open", description="Open a ticket.")
    @commands.guild_only()
    async def cmd_open(self, ctx: commands.Context):
        if ctx.interaction:
            await open_ticket(ctx.interaction, self)
        else:
            # Prefix command — simulate interaction flow manually
            cfg = await db_one("SELECT * FROM configs WHERE guild_id=?", (ctx.guild.id,))
            if not cfg:
                return await ctx.reply(f"{EMOJI_ERROR} Ticket system not set up. Ask an admin to run `ticket setup`.")

            btns = get_buttons_list(cfg)
            if len(btns) == 1:
                # Only one button type, open directly
                guild  = ctx.guild
                user   = ctx.author
                row    = await db_one("SELECT count FROM open_counts WHERE guild_id=? AND user_id=?", (guild.id, user.id))
                if row and row["count"] >= TICKET_LIMIT:
                    return await ctx.reply(f"{EMOJI_ERROR} You already have **{TICKET_LIMIT}** open tickets. Close one first.")
                row2   = await db_one("SELECT MAX(ticket_num) as n FROM tickets WHERE guild_id=?", (guild.id,))
                t_num  = (row2["n"] or 0) + 1
                support_roles = get_support_roles(cfg, guild)
                color  = parse_color(cfg["embed_color"]) if cfg["embed_color"] else EMBED_COLOR
                ticket_type = btns[0]["label"]
                type_slug   = ticket_type.lower().replace(" ", "-")[:12]
                ch_name     = f"ticket-{t_num:04d}-{type_slug}"
                overwrites  = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    user:               discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me:           discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_messages=True),
                }
                pings = [user.mention]
                for role in support_roles:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    pings.append(role.mention)
                try:
                    open_cat = await get_or_create_open_category(guild)
                    ch = await guild.create_text_channel(name=ch_name, overwrites=overwrites, category=open_cat)
                except Exception as e:
                    return await ctx.reply(f"{EMOJI_ERROR} Failed to create ticket: `{e}`")
                await db_exec("INSERT INTO tickets VALUES (?,?,?,?,0,?,NULL,?)",
                    (ch.id, guild.id, user.id, t_num, datetime.now().isoformat(), ticket_type))
                await db_exec("INSERT INTO open_counts VALUES (?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET count=count+1",
                    (guild.id, user.id))
                custom_desc = cfg["panel_description"] or "**Please describe your issue in detail.**"
                panel_title = cfg["panel_title"] or f"{EMOJI_TICKET} Ticket"
                ticket_desc = (f"Welcome {user.mention}! Staff has been notified.\n\n**Type:** {ticket_type}\n\n{custom_desc}\n\nUse the buttons below to manage this ticket.")
                embed = discord.Embed(title=f"{panel_title} — #{t_num:04d}", description=ticket_desc, color=color, timestamp=datetime.now())
                embed.set_image(url=TICKET_OPEN_BANNER)
                embed.add_field(name="Opened By", value=user.mention, inline=True)
                embed.add_field(name="Ticket #", value=str(t_num), inline=True)
                embed.add_field(name="Type", value=ticket_type, inline=True)
                await ch.send(content=" ".join(pings), embed=embed, view=OpenTicketView(self, ch.id))
                await ctx.reply(f"{EMOJI_SUCCESS} Your ticket: {ch.mention}")
                await log_action(guild, user, "Ticket Opened", f"{ch.mention} — Type: **{ticket_type}**")
            else:
                # Multiple buttons — show a select menu
                view = discord.ui.View(timeout=60)
                select = discord.ui.Select(
                    placeholder="🎫 Select ticket type...",
                    options=[
                        discord.SelectOption(label=b["label"], emoji=b.get("emoji", EMOJI_TICKET), value=b["label"])
                        for b in btns
                    ]
                )
                msg_ref = await ctx.reply("Select the type of ticket you want to open:", view=view)

                async def select_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
                    await open_ticket(interaction, self, ticket_type=select.values[0])
                    try:
                        await msg_ref.delete()
                    except Exception:
                        pass

                select.callback = select_cb
                view.add_item(select)

    # ── Close ──

    @ticket.command(name="close", description="Close the current ticket.")
    @commands.guild_only()
    async def cmd_close(self, ctx: commands.Context):
        t   = await db_one("SELECT * FROM tickets WHERE channel_id=?", (ctx.channel.id,))
        cfg = await db_one("SELECT * FROM configs  WHERE guild_id=?",  (ctx.guild.id,))
        if not t:
            return await ctx.reply(f"{EMOJI_ERROR} This is not a ticket channel.")
        if not is_staff(ctx.author, cfg) and ctx.author.id != t["creator_id"]:
            return await ctx.reply(f"{EMOJI_ERROR} No permission to close this ticket.")

        creator = ctx.guild.get_member(t["creator_id"])
        if creator:
            try:
                await ctx.channel.set_permissions(creator, view_channel=False, send_messages=False)
            except Exception:
                pass
            await db_exec(
                "UPDATE open_counts SET count=MAX(0,count-1) WHERE guild_id=? AND user_id=?",
                (ctx.guild.id, creator.id)
            )

        try:
            closed_cat = await get_or_create_closed_category(ctx.guild)
            await ctx.channel.edit(category=closed_cat)
        except Exception:
            pass

        await db_exec(
            "UPDATE tickets SET is_closed=1, closed_at=? WHERE channel_id=?",
            (datetime.now().isoformat(), ctx.channel.id)
        )

        embed = make_embed(
            title=f"{EMOJI_LOCK} Ticket Closed",
            description=f"Closed by {ctx.author.mention}.",
            color=0xff4444
        )
        await ctx.reply(embed=embed, view=ClosedTicketView(self, ctx.channel.id))
        await log_action(ctx.guild, ctx.author, "Ticket Closed", ctx.channel.mention)

    # ── Transcript ──

    @ticket.command(name="transcript", description="Save a transcript of the current ticket.")
    @commands.has_permissions(manage_channels=True)
    async def cmd_transcript(self, ctx: commands.Context):
        t = await db_one("SELECT * FROM tickets WHERE channel_id=?", (ctx.channel.id,))
        if not t:
            return await ctx.reply(f"{EMOJI_ERROR} This is not a ticket channel.")
        try:
            msgs = [m async for m in ctx.channel.history(limit=None, oldest_first=True)]
        except Exception as e:
            return await ctx.reply(f"{EMOJI_ERROR} Could not fetch messages: `{e}`")

        lines = [f"Transcript — {ctx.channel.name} — {ctx.guild.name}", "=" * 50]
        for m in msgs:
            lines.append(f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.display_name}: {m.clean_content}")

        file_bytes = "\n".join(lines).encode("utf-8")
        file = discord.File(io.BytesIO(file_bytes), filename=f"transcript-{ctx.channel.name}.txt")
        try:
            await ctx.author.send(f"{EMOJI_TRANSCRIPT} Transcript for `{ctx.channel.name}`:", file=file)
            await ctx.reply(f"{EMOJI_SUCCESS} Transcript sent to your DMs.")
        except discord.Forbidden:
            file2 = discord.File(io.BytesIO(file_bytes), filename=f"transcript-{ctx.channel.name}.txt")
            await ctx.reply(f"{EMOJI_WARN} Could not DM you. Here is the transcript:", file=file2)

    # ── Rename ──

    @commands.command(name="rename", aliases=["trename", "ticketrename"])
    @commands.guild_only()
    async def standalone_rename(self, ctx: commands.Context, *, new_name: str):
        await self._do_rename(ctx, new_name)

    @ticket.command(name="rename", description="Rename the current ticket channel.")
    @commands.guild_only()
    async def cmd_rename(self, ctx: commands.Context, *, new_name: str):
        await self._do_rename(ctx, new_name)

    async def _do_rename(self, ctx: commands.Context, new_name: str):
        t   = await db_one("SELECT * FROM tickets WHERE channel_id=?", (ctx.channel.id,))
        cfg = await db_one("SELECT * FROM configs  WHERE guild_id=?",  (ctx.guild.id,))
        if not t:
            return await ctx.reply(f"{EMOJI_ERROR} This is not a ticket channel.")
        if not is_staff(ctx.author, cfg):
            return await ctx.reply(f"{EMOJI_ERROR} Only staff can rename tickets.")

        sanitized = new_name.lower().strip().replace(" ", "-")
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")[:50]
        if not sanitized:
            return await ctx.reply(f"{EMOJI_ERROR} Invalid name. Use letters, numbers, or hyphens.")

        old_name = ctx.channel.name
        try:
            await ctx.channel.edit(name=sanitized)
        except discord.Forbidden:
            return await ctx.reply(f"{EMOJI_ERROR} I don't have permission to rename this channel.")
        except Exception as e:
            return await ctx.reply(f"{EMOJI_ERROR} Failed to rename: `{e}`")

        embed = discord.Embed(
            title=f"{EMOJI_SUCCESS} Ticket Renamed",
            description=f"`{old_name}` → `{sanitized}`\nRenamed by {ctx.author.mention}",
            color=0x57f287,
            timestamp=datetime.now()
        )
        await ctx.reply(embed=embed)
        await log_action(ctx.guild, ctx.author, "Ticket Renamed", f"`{old_name}` → `{sanitized}` in {ctx.channel.mention}")

    # ── Reset ──

    @ticket.command(name="reset", description="Delete ALL ticket data for this server.")
    @commands.has_permissions(administrator=True)
    async def cmd_reset(self, ctx: commands.Context):
        await db_exec("DELETE FROM configs     WHERE guild_id=?", (ctx.guild.id,))
        await db_exec("DELETE FROM tickets     WHERE guild_id=?", (ctx.guild.id,))
        await db_exec("DELETE FROM open_counts WHERE guild_id=?", (ctx.guild.id,))
        _setup_state.pop(ctx.guild.id, None)
        await ctx.reply(f"{EMOJI_RECYCLE} All ticket data reset.")

    # ── Error Handler ──

    @ticket.error
    async def ticket_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(f"{EMOJI_ERROR} You don't have permission.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.reply(f"{EMOJI_ERROR} Server only command.")
        else:
            print(f"[TicketCog] Error: {error}")


# ══════════════════════════════════════
# EDIT DROPDOWN VIEW (for /ticket edit)
# ══════════════════════════════════════

class EditDropdownView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=180)
        self.cog      = cog
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="✏️ Select what to edit...",
        custom_id="edit_select",
        options=[
            discord.SelectOption(label="📝 Edit Description",  value="description",  description="Change the panel description text"),
            discord.SelectOption(label="🖼️ Edit Image URL",    value="image",        description="Change the panel banner image"),
            discord.SelectOption(label="✏️ Edit Panel Title",  value="title",        description="Change the panel title"),
            discord.SelectOption(label="➕ Add Button",         value="add_button",   description="Add a new ticket button (format: Label | emoji)"),
            discord.SelectOption(label="🗑️ Remove Button",     value="del_button",   description="Remove a button by its number"),
        ]
    )
    async def select_option(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]
        await interaction.response.send_modal(EditFieldModal(self.cog, self.guild_id, value))


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
