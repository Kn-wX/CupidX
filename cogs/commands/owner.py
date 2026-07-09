from __future__ import annotations
from discord.ext import commands
from discord import *
from PIL import Image, ImageDraw, ImageFont
import discord
import json
import datetime
import asyncio
import aiosqlite
from typing import Optional
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from utils.Tools import *
from utils.config import OWNER_IDS
from core import Cog, cupidx, Context
import sqlite3
import os
import requests
from io import BytesIO
from discord.errors import Forbidden
from discord import Embed
from discord.ui import Button, View

# ═══════════════════════════════════════════════════════
#                    EMOJI CONFIG
# ═══════════════════════════════════════════════════════
TICK      = "<:CupidXtick1:1474369967271968949>"
CROSS     = "<:CupidXCross:1473996646873436336>"
WARN      = "<:CupidXWarning:1474348304186867784>"
LOADING   = "<a:CupidXloading:1474386958741536891>"
OWNER_EMJ = ""

EMJ_STAFF    = "<:CupidXstaff:1475168642525303007>"
EMJ_SHIELD   = ""
EMJ_CROWN    = "<:crown:1486975202125680753>"
EMJ_GLOBE    = ""
EMJ_CLOCK    = ""
EMJ_BADGE    = ""
EMJ_PROFILE  = ""
EMJ_STAR     = ""
EMJ_FIRE     = ""
EMJ_PIN      = " "
EMJ_LINK     = ""
EMJ_BOT      = ""
EMJ_BAN      = ""
EMJ_UNBAN    = "🔓"
EMJ_LEAVE    = "📥"
EMJ_NITRO    = ""
EMJ_BOOST    = ""
EMJ_DM       = ""
EMJ_GUILD    = ""
EMJ_CROSS_R  = ""
EMJ_CHECK    = "<:CupidXtick1:1474369967271968949>"

# ═══════════════════════════════════════════════════════
#                 COLORS CONFIG
# ═══════════════════════════════════════════════════════
COLOR_PRIMARY = 0x000000
COLOR_SUCCESS = 0x000000
COLOR_DANGER  = 0x000000
COLOR_WARN    = 0x000000
COLOR_DARK    = 0x000000
COLOR_BLUE    = 0x000000
COLOR_GOLD    = 0x000000
COLOR_TEAL    = 0x000000

# ═══════════════════════════════════════════════════════
#                 BADGE CONFIG
# ═══════════════════════════════════════════════════════
BADGE_URLS = {
    "owner":   "https://cdn.discordapp.com/emojis/1228227536207740989.png",
    "staff":   "https://cdn.discordapp.com/emojis/1228227884481515613.png",
    "partner": "https://cdn.discordapp.com/emojis/1228228301089144976.png",
    "sponsor": "https://cdn.discordapp.com/emojis/1228246375180013678.png",
    "friend":  "https://cdn.discordapp.com/emojis/1228229690376982549.png",
    "early":   "https://cdn.discordapp.com/emojis/1228241490246111302.png",
    "vip":     "https://cdn.discordapp.com/emojis/1228230884583276584.png",
    "bug":     "https://cdn.discordapp.com/emojis/1228231513456382015.png"
}

BADGE_NAMES = {
    "owner":   "Owner",
    "staff":   "Staff",
    "partner": "Partner",
    "sponsor": "Sponsor",
    "friend":  "Owner's Friend",
    "early":   "Early Supporter",
    "vip":     "VIP",
    "bug":     "Bug Hunter"
}

DISCORD_BADGE_MAP = {
    "staff":                        "Discord Employee",
    "partner":                      "Partnered Server Owner",
    "discord_certified_moderator":  "Moderator Programs Alumni",
    "hypesquad_balance":            "HypeSquad Balance",
    "hypesquad_bravery":            "HypeSquad Bravery",
    "hypesquad_brilliance":         "HypeSquad Brilliance",
    "hypesquad":                    "HypeSquad Events",
    "early_supporter":              "Early Supporter",
    "bug_hunter":                   "Bug Hunter Level 1",
    "bug_hunter_level_2":           "Bug Hunter Level 2",
    "verified_bot":                 "Verified Bot",
    "verified_bot_developer":       "Verified Bot Developer",
    "active_developer":             "Active Developer",
    "early_verified_bot_developer": "Early Verified Bot Developer",
    "system":                       "System User",
    "team_user":                    "Team User",
    "spammer":                      "Marked as Spammer",
    "bot_http_interactions":        "HTTP Interactions Bot",
}

# ═══════════════════════════════════════════════════════
#                 DATABASE SETUP
# ═══════════════════════════════════════════════════════
db_folder = 'db'
db_file   = 'badges.db'
db_path   = os.path.join(db_folder, db_file)
FONT_PATH = os.path.join('utils', 'arial.ttf')

conn = sqlite3.connect(db_path)
c    = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER PRIMARY KEY,
    owner   INTEGER DEFAULT 0,
    staff   INTEGER DEFAULT 0,
    partner INTEGER DEFAULT 0,
    sponsor INTEGER DEFAULT 0,
    friend  INTEGER DEFAULT 0,
    early   INTEGER DEFAULT 0,
    vip     INTEGER DEFAULT 0,
    bug     INTEGER DEFAULT 0
)''')
conn.commit()

# ── Badge helpers ──
def add_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute(f"INSERT INTO badges (user_id, {badge}) VALUES (?, 1)", (user_id,))
    elif result[0] == 0:
        c.execute(f"UPDATE badges SET {badge} = 1 WHERE user_id = ?", (user_id,))
    else:
        return False
    conn.commit()
    return True

def remove_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        c.execute(f"UPDATE badges SET {badge} = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    return False

# ── Misc helpers ──
def convert_time_to_seconds(time_str):
    time_units = {"h": "hours", "d": "days", "m": "months"}
    num  = int(time_str[:-1])
    unit = time_units.get(time_str[-1])
    return datetime.timedelta(**{unit: num})

def load_owner_ids():
    return OWNER_IDS

async def is_staff(user, staff_ids):
    return user.id in staff_ids

async def is_owner_or_staff(ctx):
    return await is_staff(ctx.author, ctx.cog.staff) or ctx.author.id in OWNER_IDS

async def is_bot_owner(ctx):
    """Bot ka added owner check — OWNER_IDS ya owner_add se added."""
    if ctx.author.id in OWNER_IDS:
        return True
    if hasattr(ctx.cog, 'owners') and ctx.author.id in ctx.cog.owners:
        return True
    return False

async def do_removal(ctx, limit, predicate, *, before=None, after=None):
    if limit > 2000:
        return await ctx.error(f"Too many messages to search given ({limit}/2000)")
    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)
    if after is not None:
        after = discord.Object(id=after)
    try:
        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
    except discord.Forbidden:
        return await ctx.error("I do not have permissions to delete messages.")
    except discord.HTTPException as e:
        return await ctx.error(f"Error: {e} (try a smaller search?)")

    spammers = Counter(m.author.display_name for m in deleted)
    deleted  = len(deleted)
    messages = [f'{TICK} | {deleted} message{" was" if deleted == 1 else "s were"} removed.']
    if deleted:
        messages.append("")
        spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
        messages.extend(f"**{name}**: {count}" for name, count in spammers)

    to_send = "\n".join(messages)
    if len(to_send) > 2000:
        await ctx.send(f"{TICK} | Successfully removed {deleted} messages.", delete_after=3)
    else:
        await ctx.send(to_send, delete_after=3)


# ═══════════════════════════════════════════════════════
#           V2 CARD HELPERS
# ═══════════════════════════════════════════════════════
def _v2_card(text: str, controls=None, timeout: float = 120.0) -> discord.ui.LayoutView:
    """Quick helper — text → LayoutView container card."""
    items: list = [discord.ui.TextDisplay(text)]
    if controls:
        items.append(discord.ui.Separator())
        for c_ in controls:
            items.append(c_)
    view = discord.ui.LayoutView(timeout=timeout)
    view.add_item(discord.ui.Container(*items))
    return view


def _v2_loading(text: str) -> discord.ui.LayoutView:
    return _v2_card(f"{LOADING} {text}")


def _v2_simple(text: str) -> discord.ui.LayoutView:
    return _v2_card(text)


# ═══════════════════════════════════════════════════════
#                   OWNER COG
# ═══════════════════════════════════════════════════════
class Owner(commands.Cog):

    def __init__(self, client):
        self.client        = client
        self.staff         = set(
        self.np_cache      = []
        self.db_path       = 'db/np.db'
        self.stop_tour     = False
        self.bot_owner_ids = [1378341015181856768]
        self.client.loop.create_task(self.setup_database())
        self.client.loop.create_task(self.load_staff())

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_owners (
                    id INTEGER PRIMARY KEY
                )
            ''')
            await db.commit()

    async def load_staff(self):
        await self.client.wait_until_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id FROM staff') as cursor:
                self.staff = {row[0] for row in await cursor.fetchall()}

    # ════════════════════════════════════════════
    #   STAFF ADD
    # ════════════════════════════════════════════
    @commands.command(name="staff_add", aliases=["staffadd", "addstaff"], help="Add a user to the staff list.")
    @commands.check(is_bot_owner)
    async def staff_add(self, ctx, user: discord.User):
        if user.id in self.staff:
            return await ctx.reply(
                view=_v2_simple(
                    f"## {WARN}  Already a Staff Member\n"
                    f"{EMJ_STAFF} **{user}** is already in the staff list.\n"
                    f"{EMJ_PIN} Use `staff_remove` to remove them first."
                ),
                mention_author=False
            )

        self.staff.add(user.id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT OR IGNORE INTO staff (id) VALUES (?)', (user.id,))
            await db.commit()

        await ctx.reply(
            view=_v2_simple(
                f"## {TICK}  Staff Member Added\n"
                f"{EMJ_STAFF} **{user}** has been added to the staff team!\n"
                f"{EMJ_SHIELD} They now have access to staff-only commands.\n"
                f"{EMJ_PIN} User ID: `{user.id}`"
            ),
            mention_author=False
        )

    # ════════════════════════════════════════════
    #   STAFF REMOVE
    # ════════════════════════════════════════════
    @commands.command(name="staff_remove", aliases=["staffremove", "removestaff"], help="Remove a user from the staff list.")
    @commands.check(is_bot_owner)
    async def staff_remove(self, ctx, user: discord.User):
        if user.id not in self.staff:
            return await ctx.reply(
                view=_v2_simple(
                    f"## {WARN}  Not a Staff Member\n"
                    f"{EMJ_STAFF} **{user}** is not in the staff list.\n"
                    f"{EMJ_PIN} Use `staff_add` to add them first."
                ),
                mention_author=False
            )

        self.staff.remove(user.id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM staff WHERE id = ?', (user.id,))
            await db.commit()

        await ctx.reply(
            view=_v2_simple(
                f"## {TICK}  Staff Member Removed\n"
                f"{EMJ_CROSS_R} **{user}** has been removed from the staff team.\n"
                f"{EMJ_SHIELD} Their staff access has been revoked.\n"
                f"{EMJ_PIN} User ID: `{user.id}`"
            ),
            mention_author=False
        )

    # ════════════════════════════════════════════
    #   STAFF LIST
    # ════════════════════════════════════════════
    @commands.command(name="staff_list", aliases=["stafflist", "liststaff", "staffs"], help="List all staff members.")
    @commands.check(is_bot_owner)
    async def staff_list(self, ctx):
        if not self.staff:
            return await ctx.send(
                view=_v2_simple(
                    f"## {EMJ_STAFF}  Staff List\n"
                    f"{EMJ_CROSS_R} The staff list is currently **empty**.\n"
                    f"Use `staff_add @user` to add members."
                )
            )

        msg = await ctx.send(view=_v2_loading("Loading staff list..."))

        staff_users = []
        for staff_id in self.staff:
            try:
                user = await self.client.fetch_user(staff_id)
                staff_users.append(user)
            except Exception:
                continue

        PER_PAGE = 5
        pages    = [staff_users[i:i+PER_PAGE] for i in range(0, len(staff_users), PER_PAGE)]
        total    = len(pages)

        def make_page(page_idx):
            lines = [f"## {EMJ_STAFF}  CupidX Staff Team\n"]
            for user in pages[page_idx]:
                lines.append(f"{EMJ_STAFF} **[{user.name}](https://discord.com/users/{user.id})**\n> `{user.id}`\n")
            lines.append(f"-# Page {page_idx+1}/{total}  •  Total Staff: {len(staff_users)}")
            return "\n".join(lines)

        class StaffPaginator(discord.ui.LayoutView):
            def __init__(self_, page=0):
                super().__init__(timeout=120)
                self_.page = page
                self_._rebuild()

            def _rebuild(self_):
                self_.clear_items()
                prev_btn = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=self_.page == 0)
                next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=self_.page == total - 1)

                async def prev_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page -= 1
                    self_._rebuild()
                    await interaction.message.edit(view=self_)

                async def next_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page += 1
                    self_._rebuild()
                    await interaction.message.edit(view=self_)

                prev_btn.callback = prev_cb
                next_btn.callback = next_cb

                container = discord.ui.Container(
                    discord.ui.TextDisplay(make_page(self_.page)),
                    discord.ui.Separator(),
                    discord.ui.ActionRow(prev_btn, next_btn),
                )
                self_.add_item(container)

        view = StaffPaginator(0)
        await msg.edit(view=view)
        
    # ════════════════════════════════════════════
    #   SERVER LIST
    # ════════════════════════════════════════════
    @commands.command(name="slist")
    @commands.check(is_owner_or_staff)
    async def _slist(self, ctx):
        is_root  = ctx.author.id in OWNER_IDS
        servers  = sorted(self.client.guilds, key=lambda g: g.member_count, reverse=True)
        msg      = await ctx.send(view=_v2_loading("Loading server list..."))

        PER_PAGE = 8
        pages    = [servers[i:i+PER_PAGE] for i in range(0, len(servers), PER_PAGE)]
        total    = len(pages)

        def make_page(page_idx):
            lines = [f"## {EMJ_GLOBE}  Guild List of CupidX  [{len(servers)}]\n"]
            start = page_idx * PER_PAGE
            for i, g in enumerate(pages[page_idx], start=start + 1):
                lines.append(f"`#{i}` {EMJ_GUILD} **[{g.name}](https://discord.com/channels/{g.id})**\n　　👥 Members: **{g.member_count}**\n")
            lines.append(f"-# Page {page_idx+1}/{total}  •  CupidX")
            return "\n".join(lines)

        class SlistPaginator(discord.ui.LayoutView):
            def __init__(self_, page=0):
                super().__init__(timeout=120)
                self_.page = page
                self_._rebuild()

            def _rebuild(self_):
                self_.clear_items()
                first_btn = discord.ui.Button(label="⏮", style=discord.ButtonStyle.secondary, disabled=self_.page == 0)
                prev_btn  = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self_.page == 0)
                next_btn  = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self_.page == total - 1)
                last_btn  = discord.ui.Button(label="⏭", style=discord.ButtonStyle.secondary, disabled=self_.page == total - 1)

                async def first_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page = 0; self_._rebuild(); await interaction.message.edit(view=self_)

                async def prev_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page -= 1; self_._rebuild(); await interaction.message.edit(view=self_)

                async def next_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page += 1; self_._rebuild(); await interaction.message.edit(view=self_)

                async def last_cb(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                    await interaction.response.defer()
                    self_.page = total - 1; self_._rebuild(); await interaction.message.edit(view=self_)

                first_btn.callback = first_cb
                prev_btn.callback  = prev_cb
                next_btn.callback  = next_cb
                last_btn.callback  = last_cb

                action_row = discord.ui.ActionRow(first_btn, prev_btn, next_btn, last_btn)

                if is_root:
                    leave_btn = discord.ui.Button(label="Leave Server 🚪", style=discord.ButtonStyle.danger)
                    async def leave_cb(interaction: discord.Interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(view=_v2_simple(f"{CROSS} This menu is not for you."), ephemeral=True)
                        current_servers = pages[self_.page]
                        options = [
                            discord.SelectOption(label=g.name[:100], value=str(g.id), description=f"{g.member_count} members")
                            for g in current_servers
                        ]
                        class LeaveSelect(discord.ui.View):
                            def __init__(self_inner):
                                super().__init__(timeout=30)
                            @discord.ui.select(placeholder="Which server to leave?", options=options)
                            async def select_guild(self_inner, inter: discord.Interaction, select: discord.ui.Select):
                                guild_id = int(select.values[0])
                                guild    = inter.client.get_guild(guild_id)
                                if not guild:
                                    return await inter.response.edit_message(content=f"{CROSS} Server not found.", view=None)
                                class ConfirmLeave(discord.ui.View):
                                    def __init__(self_c):
                                        super().__init__(timeout=30)
                                    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
                                    async def confirm(self_c, inter2: discord.Interaction, b: discord.ui.Button):
                                        try:
                                            await guild.leave()
                                            await inter2.response.edit_message(content=f"{TICK} Left **{guild.name}**.", embed=None, view=None)
                                        except Exception as e:
                                            await inter2.response.edit_message(content=f"{CROSS} Error: `{e}`", embed=None, view=None)
                                        self_c.stop()
                                    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                                    async def cancel(self_c, inter2: discord.Interaction, b: discord.ui.Button):
                                        await inter2.response.edit_message(content=f"{WARN} Cancelled.", embed=None, view=None)
                                        self_c.stop()
                                confirm_view = ConfirmLeave()
                                await inter.response.edit_message(
                                    content=f"{WARN} Leave **{guild.name}**? ({guild.member_count} members)",
                                    view=confirm_view
                                )
                        await interaction.response.send_message("Which server to leave?", view=LeaveSelect(), ephemeral=True)
                    leave_btn.callback = leave_cb

                    container = discord.ui.Container(
                        discord.ui.TextDisplay(make_page(self_.page)),
                        discord.ui.Separator(),
                        action_row,
                        discord.ui.ActionRow(leave_btn),
                    )
                else:
                    container = discord.ui.Container(
                        discord.ui.TextDisplay(make_page(self_.page)),
                        discord.ui.Separator(),
                        action_row,
                    )
                self_.add_item(container)

        await msg.edit(view=SlistPaginator(0))

    # ════════════════════════════════════════════
    #   MUTUALS
    # ════════════════════════════════════════════
    @commands.command(name="mutuals", aliases=["mutual"])
    @commands.check(is_bot_owner)
    async def mutuals(self, ctx, user: discord.User):
        guilds  = [guild for guild in self.client.guilds if user in guild.members]
        entries = [
            f"`#{no}` {EMJ_GUILD} [{guild.name}](https://discord.com/channels/{guild.id}) — **{guild.member_count}** members"
            for no, guild in enumerate(guilds, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            description="",
            title=f"{EMJ_GLOBE} Mutual Guilds of {user.name}  [{len(guilds)}]",
            color=COLOR_TEAL,
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    # ════════════════════════════════════════════
    #   GET INVITE
    # ════════════════════════════════════════════
    @commands.hybrid_command(name="getinvite", aliases=["gi", "guildinvite"])
    @commands.check(is_bot_owner)
    async def getinvite(self, ctx: Context, *, server_id: int):
        guild = self.client.get_guild(server_id)

        if not guild:
            return await ctx.send(view=_v2_simple(f"{CROSS} Invalid server ID or bot is not in that server."))

        if not guild.me.guild_permissions.create_instant_invite:
            return await ctx.send(view=_v2_simple(f"{CROSS} I don't have permission to create invites in **{guild.name}**."))

        msg = await ctx.send(view=_v2_loading(f"Fetching invites for **{guild.name}**..."))

        try:
            invites = await guild.invites()
            if invites:
                entries = [
                    f"{EMJ_LINK} {invite.url} — Uses: **{invite.uses}**"
                    for invite in invites
                ]
                await msg.delete()
                paginator = Paginator(source=DescriptionEmbedPaginator(
                    entries=entries,
                    title=f"{EMJ_LINK} Invites for {guild.name}",
                    color=COLOR_TEAL),
                    ctx=ctx)
                await paginator.paginate()
            else:
                channel = guild.system_channel or next(
                    (ch for ch in guild.text_channels if ch.permissions_for(guild.me).create_instant_invite), None
                )
                if channel:
                    invite = await channel.create_invite(max_age=86400, max_uses=1)
                    await msg.edit(view=_v2_simple(
                        f"## {TICK}  Invite Created\n"
                        f"{EMJ_LINK} **Server:** {guild.name}\n"
                        f"{EMJ_LINK} **Link:** {invite.url}\n"
                        f"-# Expires in 24h • Max 1 use"
                    ))
                else:
                    await msg.edit(view=_v2_simple(f"{CROSS} No suitable text channel found to create an invite."))
        except Exception as e:
            await msg.edit(view=_v2_simple(f"{CROSS} Error: `{e}`"))

    # ════════════════════════════════════════════
    #   RESTART — ROOT ONLY (no is_bot_owner)
    # ════════════════════════════════════════════
    @commands.command(name="restart", help="Restarts the client.")
    @commands.is_owner()
    async def _restart(self, ctx: Context):
        msg = await ctx.reply(
            view=_v2_simple(
                f"## {LOADING}  Restarting...\n"
                f"**Bot:** {self.client.user.mention}\n"
                f"**Requested By:** {ctx.author.mention}\n"
                f"**Status:** Shutting down processes..."
            ),
            mention_author=False
        )
        await asyncio.sleep(2)
        await msg.edit(
            view=_v2_simple(
                f"## {TICK}  Restart Initiated\n"
                f"**Bot:** {self.client.user.mention}\n"
                f"**Requested By:** {ctx.author.mention}\n"
                f"**Status:** Bot will be back online shortly..."
            )
        )
        restart_program()

    # ════════════════════════════════════════════
    #   $SYNC — ROOT ONLY
    # ════════════════════════════════════════════
    @commands.command(name="$sync", help="Syncs slash commands and database.")
    @commands.is_owner()
    async def _sync(self, ctx):
        msg = await ctx.reply(
            view=_v2_simple(
                f"## {LOADING}  Syncing...\n"
                f"**Bot:** {self.client.user.mention}\n"
                f"**Guilds:** `{len(self.client.guilds)}`\n"
                f"**Status:** Syncing slash commands & database..."
            ),
            mention_author=False
        )

        try:
            synced       = await self.client.tree.sync()
            slash_status = f"{TICK} `{len(synced)}` commands synced"
        except Exception as e:
            synced       = []
            slash_status = f"{CROSS} Failed: `{e}`"

        events_added = 0
        try:
            with open('events.json', 'r') as f:
                data = json.load(f)
            for guild in self.client.guilds:
                if str(guild.id) not in data['guilds']:
                    data['guilds'][str(guild.id)] = 'on'
                    events_added += 1
            with open('events.json', 'w') as f:
                json.dump(data, f, indent=4)
            events_status = f"{TICK} `{events_added}` new guilds added"
        except Exception as e:
            events_status = f"{CROSS} Failed: `{e}`"

        config_cleaned = 0
        try:
            with open('config.json', 'r') as f:
                data = json.load(f)
            to_pop = [op for op in data["guilds"] if not self.client.get_guild(int(op))]
            for op in to_pop:
                data["guilds"].pop(str(op))
                config_cleaned += 1
            with open('config.json', 'w') as f:
                json.dump(data, f, indent=4)
            config_status = f"{TICK} `{config_cleaned}` stale guilds removed"
        except Exception as e:
            config_status = f"{CROSS} Failed: `{e}`"

        await msg.edit(
            view=_v2_simple(
                f"## {TICK}  Sync Complete\n"
                f"**Bot:** {self.client.user.mention}\n"
                f"**Requested By:** {ctx.author.mention}\n"
                f"**Total Guilds:** `{len(self.client.guilds)}`\n\n"
                f"**Slash Commands:** {slash_status}\n"
                f"**Events DB:** {events_status}\n"
                f"**Config DB:** {config_status}"
            )
        )

    # ════════════════════════════════════════════
    #   OWNERS LIST
    # ════════════════════════════════════════════
    @commands.command(name="owners", aliases=["devs"])
    @commands.check(is_bot_owner)
    async def own_list(self, ctx):
        developer_ids = [1378341015181856768, 1408463932649373800]
        partner_ids   = []
        friend_ids    = [1086563807314313266]

        msg = await ctx.reply(view=_v2_loading("Loading dev team..."), mention_author=False)

        lines = [f"## {OWNER_EMJ}  CupidX Development Team\n{EMJ_SHIELD} The elite developers behind the CupidX security system.\n"]

        for i, uid in enumerate(developer_ids, 1):
            try:
                user = self.client.get_user(uid) or await self.client.fetch_user(uid)
                lines.append(
                    f"**{EMJ_CROWN} Developer & Bot Owner #{i}**\n"
                    f"> {EMJ_STAR} **Name:** {user.name}\n"
                    f"> {EMJ_PIN} **ID:** `{user.id}`\n"
                    f"> {EMJ_LINK} **Profile:** [Click Here](https://discord.com/users/{user.id})\n"
                    f"> **Mention:** {user.mention}\n"
                )
            except Exception:
                pass

        for i, uid in enumerate(partner_ids, 1):
            try:
                user = self.client.get_user(uid) or await self.client.fetch_user(uid)
                lines.append(
                    f"**{EMJ_LINK} Partner #{i}**\n"
                    f"> {EMJ_STAR} **Name:** {user.name}\n"
                    f"> {EMJ_PIN} **ID:** `{user.id}`\n"
                    f"> {EMJ_LINK} **Profile:** [Click Here](https://discord.com/users/{user.id})\n"
                    f"> **Mention:** {user.mention}\n"
                )
            except Exception:
                pass

        for i, uid in enumerate(friend_ids, 1):
            try:
                user = self.client.get_user(uid) or await self.client.fetch_user(uid)
                lines.append(
                    f"**{EMJ_STAR} Owner's Friend #{i}**\n"
                    f"> {EMJ_STAR} **Name:** {user.name}\n"
                    f"> {EMJ_PIN} **ID:** `{user.id}`\n"
                    f"> {EMJ_LINK} **Profile:** [Click Here](https://discord.com/users/{user.id})\n"
                    f"> **Mention:** {user.mention}\n"
                )
            except Exception:
                pass

        await msg.edit(view=_v2_simple("\n".join(lines)))

    # ════════════════════════════════════════════
    #   DM USER
    # ════════════════════════════════════════════
    @commands.command()
    @commands.check(is_bot_owner)
    async def dm(self, ctx, user: discord.User, *, message: str):
        msg = await ctx.send(view=_v2_loading(f"Sending DM to **{user}**..."))
        try:
            await user.send(message)
            await msg.edit(view=_v2_simple(
                f"## {TICK}  DM Sent\n"
                f"{EMJ_DM} Successfully sent a DM to **{user}** (`{user.id}`)"
            ))
        except discord.Forbidden:
            await msg.edit(view=_v2_simple(
                f"{CROSS} Could not DM **{user}** — DMs may be disabled or it's a bot account."
            ))

    # ════════════════════════════════════════════
    #   OWNER DM (BROADCAST)
    # ════════════════════════════════════════════
    @commands.hybrid_command(name="ownerdm", description="Send a message to all guild owners the bot is in.")
    @commands.check(is_bot_owner)
    async def ownerdm(self, ctx: Context, *, message: str):
        msg = await ctx.reply(
            view=_v2_loading("Sending messages to all guild owners, please wait..."),
            mention_author=False
        )

        owners  = {guild.owner for guild in self.client.guilds if guild.owner}
        success = 0
        failed  = 0

        for owner in owners:
            try:
                dm_embed = discord.Embed(
                    title=f"{EMJ_DM}  Message from Bot Owner",
                    description=message,
                    color=COLOR_GOLD,
                    timestamp=discord.utils.utcnow()
                )
                dm_embed.set_footer(text=f"Sent by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                await owner.send(embed=dm_embed)
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

        await msg.edit(view=_v2_simple(
            f"## {TICK}  Broadcast Complete\n"
            f"{EMJ_CHECK} **Delivered:** `{success}` owners\n"
            f"{EMJ_CROSS_R} **Failed:** `{failed}` owners\n"
            f"-# Total targets: {success + failed}"
        ))

    # ════════════════════════════════════════════
    #   GLOBAL DM (ALL USERS)
    # ════════════════════════════════════════════
    @commands.hybrid_command(name="globaldm", description="Send a DM to all users in all servers the bot is in.")
    @commands.check(is_bot_owner)
    async def globaldm(self, ctx: Context, *, message: str):
        msg = await ctx.reply(
            view=_v2_loading("Collecting users, please wait..."),
            mention_author=False
        )

        seen    = set()
        users   = []
        for guild in self.client.guilds:
            for member in guild.members:
                if member.bot or member.id in seen:
                    continue
                seen.add(member.id)
                users.append(member)

        total   = len(users)
        success = 0
        failed  = 0

        await msg.edit(view=_v2_loading(f"Sending DMs to `{total}` unique users..."))

        for i, member in enumerate(users, 1):
            personalized = message.replace("{user}", member.display_name)
            try:
                dm_embed = discord.Embed(
                    title=f"{EMJ_DM}  Message from Bot Owner",
                    description=personalized,
                    color=COLOR_GOLD,
                    timestamp=discord.utils.utcnow()
                )
                dm_embed.set_footer(text=f"Sent by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                await member.send(embed=dm_embed)
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

            if i % 50 == 0:
                await msg.edit(view=_v2_loading(f"Progress: `{i}/{total}` — ✅ `{success}` | ❌ `{failed}`"))

            await asyncio.sleep(1.2)

        await msg.edit(view=_v2_simple(
            f"## {TICK}  Global DM Complete\n"
            f"{EMJ_CHECK} **Delivered:** `{success}` users\n"
            f"{EMJ_CROSS_R} **Failed:** `{failed}` users\n"
            f"-# Total targets: {total}"
        ))

    # ════════════════════════════════════════════
    #   CHANGE GROUP
    # ════════════════════════════════════════════
    @commands.group()
    @commands.check(is_bot_owner)
    async def change(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(
                view=_v2_simple(
                    f"## 🔧  Change Settings\n"
                    f"Modify bot-specific attributes.\n\n"
                    f"**Subcommands**\n"
                    f"`{ctx.prefix}change nickname` — Change bot nickname"
                ),
                mention_author=False
            )

    @change.command(name="nickname")
    @commands.check(is_bot_owner)
    async def change_nickname(self, ctx, *, name: str = None):
        msg = await ctx.send(view=_v2_loading("Updating nickname..."))
        try:
            await ctx.guild.me.edit(nick=name)
            await msg.edit(view=_v2_simple(
                f"## {TICK}  Nickname Updated\n"
                f"{EMJ_BOT} Nickname changed to **{name}**" if name
                else f"## {TICK}  Nickname Updated\n{EMJ_BOT} Nickname has been **removed**."
            ))
        except Exception as err:
            await msg.edit(view=_v2_simple(f"{CROSS} Error: `{err}`"))

    # ════════════════════════════════════════════
    #   OWNER BAN / UNBAN
    # ════════════════════════════════════════════
    @commands.command(name="ownerban", aliases=["forceban", "dna"])
    @commands.check(is_bot_owner)
    async def _ownerban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        member = ctx.guild.get_member(user_id)
        if member:
            try:
                await member.ban(reason=reason)
                await ctx.reply(
                    view=_v2_simple(
                        f"## {EMJ_BAN}  Member Banned\n"
                        f"{TICK} **{member.name}** has been banned from **{ctx.guild.name}**.\n"
                        f"{EMJ_PIN} **Reason:** {reason}\n"
                        f"{EMJ_SHIELD} Executed by the Bot Owner."
                    ),
                    mention_author=False, delete_after=5
                )
                await ctx.message.delete()
            except discord.Forbidden:
                await ctx.reply(view=_v2_simple(f"{CROSS} Missing permissions to ban **{member.name}**."), mention_author=False, delete_after=5)
                await ctx.message.delete()
            except discord.HTTPException:
                await ctx.reply(view=_v2_simple(f"{CROSS} An error occurred while banning **{member.name}**."), mention_author=False, delete_after=5)
                await ctx.message.delete()
        else:
            await ctx.reply(view=_v2_simple(f"{CROSS} User not found in this guild."), mention_author=False, delete_after=3)
            await ctx.message.delete()

    @commands.command(name="ownerunban", aliases=["forceunban"])
    @commands.check(is_bot_owner)
    async def _ownerunban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        user = self.client.get_user(user_id)
        if user:
            try:
                await ctx.guild.unban(user, reason=reason)
                await ctx.reply(
                    view=_v2_simple(
                        f"## {EMJ_UNBAN}  Member Unbanned\n"
                        f"{TICK} **{user.name}** has been unbanned from **{ctx.guild.name}**.\n"
                        f"{EMJ_PIN} **Reason:** {reason}"
                    ),
                    mention_author=False
                )
            except discord.Forbidden:
                await ctx.reply(view=_v2_simple(f"{CROSS} Missing permissions to unban **{user.name}**."), mention_author=False)
            except discord.HTTPException:
                await ctx.reply(view=_v2_simple(f"{CROSS} An error occurred while unbanning **{user.name}**."), mention_author=False)
        else:
            await ctx.reply(view=_v2_simple(f"{CROSS} User not found."), mention_author=False)

    # ════════════════════════════════════════════
    #   GLOBAL UNBAN
    # ════════════════════════════════════════════
    @commands.command(name="globalunban")
    @commands.check(is_bot_owner)
    async def globalunban(self, ctx: Context, user: discord.User):
        msg = await ctx.reply(view=_v2_loading(f"Running global unban for **{user}**..."), mention_author=False)
        success_guilds = []
        error_guilds   = []

        for guild in self.client.guilds:
            bans = await guild.bans()
            if any(ban_entry.user.id == user.id for ban_entry in bans):
                try:
                    await guild.unban(user, reason="Global Unban")
                    success_guilds.append(guild.name)
                except (discord.HTTPException, discord.Forbidden):
                    error_guilds.append(guild.name)

        await msg.edit(view=_v2_simple(
            f"## {EMJ_UNBAN}  Global Unban Result\n"
            f"{EMJ_CHECK} **Success ({len(success_guilds)}):** {', '.join(success_guilds) or 'None'}\n"
            f"{EMJ_CROSS_R} **Failed ({len(error_guilds)}):** {', '.join(error_guilds) or 'None'}\n"
            f"-# User: {user}"
        ))

    # ════════════════════════════════════════════
    #   GUILD BAN / UNBAN
    # ════════════════════════════════════════════
    @commands.command(name="guildban")
    @commands.check(is_bot_owner)
    async def guildban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            return await ctx.reply(view=_v2_simple(f"{CROSS} Bot is not in that guild."), mention_author=False)
        member = guild.get_member(user_id)
        if member:
            try:
                await guild.ban(member, reason=reason)
                await ctx.reply(
                    view=_v2_simple(
                        f"## {EMJ_BAN}  Guild Ban\n"
                        f"{TICK} Banned **{member.name}** from **{guild.name}**.\n"
                        f"{EMJ_PIN} **Reason:** {reason}"
                    ),
                    mention_author=False
                )
            except discord.Forbidden:
                await ctx.reply(view=_v2_simple(f"{CROSS} Missing permissions in **{guild.name}**."), mention_author=False)
            except discord.HTTPException as e:
                await ctx.reply(view=_v2_simple(f"{CROSS} Error: `{str(e)}`"), mention_author=False)
        else:
            await ctx.reply(view=_v2_simple(f"{CROSS} User not found in **{guild.name}**."), mention_author=False)

    @commands.command(name="guildunban")
    @commands.check(is_bot_owner)
    async def guildunban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            return await ctx.reply(view=_v2_simple(f"{CROSS} Bot is not in that guild."), mention_author=False)
        try:
            await self.client.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.reply(view=_v2_simple(f"{CROSS} User with ID `{user_id}` not found."), mention_author=False)
        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
            await ctx.reply(
                view=_v2_simple(
                    f"## {EMJ_UNBAN}  Guild Unban\n"
                    f"{TICK} Unbanned user `{user_id}` from **{guild.name}**.\n"
                    f"{EMJ_PIN} **Reason:** {reason}"
                ),
                mention_author=False
            )
        except discord.Forbidden:
            await ctx.reply(view=_v2_simple(f"{CROSS} Missing permissions in **{guild.name}**."), mention_author=False)
        except discord.HTTPException as e:
            await ctx.reply(view=_v2_simple(f"{CROSS} Error: `{str(e)}`"), mention_author=False)

    # ════════════════════════════════════════════
    #   LEAVE GUILD
    # ════════════════════════════════════════════
    @commands.command(name="leaveguild", aliases=["leavesv"])
    @commands.check(is_bot_owner)
    async def leave_guild(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            return await ctx.send(view=_v2_simple(f"{CROSS} Guild with ID `{guild_id}` not found."))
        await ctx.send(view=_v2_simple(f"## {EMJ_LEAVE}  Left Guild\n{TICK} Successfully left **{guild.name}** (`{guild.id}`)"))
        await guild.leave()

    # ════════════════════════════════════════════
    #   GUILD INFO
    # ════════════════════════════════════════════
    @commands.command(name="guildinfo")
    @commands.check(is_owner_or_staff)
    async def guild_info(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            return await ctx.send(view=_v2_simple(f"{CROSS} Guild with ID `{guild_id}` not found."))
        await ctx.send(view=_v2_simple(
            f"## {EMJ_GUILD}  {guild.name}\n"
            f"**ID:** `{guild.id}`\n"
            f"{EMJ_CROWN} **Owner:** {guild.owner}\n"
            f"👥 **Members:** {guild.member_count}\n"
            f"💬 **Text Channels:** {len(guild.text_channels)}\n"
            f"🔊 **Voice Channels:** {len(guild.voice_channels)}\n"
            f"🎭 **Roles:** {len(guild.roles)}\n"
            f"{EMJ_CLOCK} **Created:** <t:{int(guild.created_at.timestamp())}:R>"
        ))

    # ════════════════════════════════════════════
    #   SERVER TOUR
    # ════════════════════════════════════════════
    @commands.command()
    @commands.check(is_bot_owner)
    async def servertour(self, ctx, time_in_seconds: int, member: discord.Member):
        guild = ctx.guild
        if time_in_seconds > 3600:
            return await ctx.send(view=_v2_simple(f"{CROSS} Time cannot exceed **3600 seconds** (1 hour)."))
        if not member.voice:
            return await ctx.send(view=_v2_simple(f"{CROSS} **{member.display_name}** is not in a voice channel."))

        voice_channels = [ch for ch in guild.voice_channels if ch.permissions_for(guild.me).move_members]
        if len(voice_channels) < 2:
            return await ctx.send(view=_v2_simple(f"{CROSS} Not enough voice channels to run the tour."))

        self.stop_tour = False

        stop_btn = discord.ui.Button(label="⛔  Stop Tour", style=discord.ButtonStyle.danger)

        class TourView(discord.ui.LayoutView):
            def __init__(self_, text):
                super().__init__(timeout=time_in_seconds)
                self_._stop_btn = stop_btn

                async def stop_cb(interaction: discord.Interaction):
                    if interaction.user.id not in self.bot_owner_ids:
                        return await interaction.response.send_message("Only the bot owner can stop this.", ephemeral=True)
                    self.stop_tour = True
                    await interaction.response.defer()
                    self_.stop()

                stop_btn.callback = stop_cb
                self_.add_item(discord.ui.Container(
                    discord.ui.TextDisplay(text),
                    discord.ui.Separator(),
                    discord.ui.ActionRow(stop_btn),
                ))

        message = await ctx.send(
            view=TourView(
                f"## 🎢  Server Tour Started\n"
                f"👤 Moving **{member.display_name}** for **{time_in_seconds}s**\n"
                f"🔊 Across **{len(voice_channels)}** voice channels"
            )
        )

        end_time = asyncio.get_event_loop().time() + time_in_seconds
        while asyncio.get_event_loop().time() < end_time and not self.stop_tour:
            for ch in voice_channels:
                if self.stop_tour:
                    await ctx.send(view=_v2_simple(f"{TICK} Tour stopped."))
                    return
                if not member.voice:
                    return await ctx.send(view=_v2_simple(f"{WARN} **{member.display_name}** left the voice channel."))
                try:
                    await member.move_to(ch)
                    await asyncio.sleep(5)
                except Forbidden:
                    return await ctx.send(view=_v2_simple(f"{CROSS} Missing permissions to move **{member.display_name}**."))
                except Exception as e:
                    return await ctx.send(view=_v2_simple(f"{CROSS} Error: `{str(e)}`"))

        if not self.stop_tour:
            await message.edit(view=_v2_simple(
                f"## {TICK}  Server Tour Complete\n"
                f"Finished moving **{member.display_name}** after **{time_in_seconds}s**."
            ))

    # ════════════════════════════════════════════
    #   BADGE MANAGEMENT GROUP
    # ════════════════════════════════════════════
    @commands.group()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bdg(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(
                view=_v2_simple(
                    f"## {EMJ_BADGE}  Badge Management\n"
                    f"Grant or revoke special CupidX badges from users.\n\n"
                    f"**Subcommands**\n"
                    f"`{ctx.prefix}bdg add @user <badge>` — Grant a badge\n"
                    f"`{ctx.prefix}bdg remove @user <badge>` — Revoke a badge\n\n"
                    f"**Available Badges**\n"
                    + " | ".join(f"`{b}`" for b in BADGE_URLS.keys())
                ),
                mention_author=False
            )

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def add(self, ctx, member: discord.Member, badge: str):
        badge   = badge.lower()
        user_id = member.id

        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    add_badge(user_id, b)
                text = f"## {TICK}  All Badges Granted\n{EMJ_BADGE} All badges have been granted to {member.mention}."
            else:
                success = add_badge(user_id, badge)
                if success:
                    text = f"## {TICK}  Badge Granted\n{EMJ_BADGE} Badge `{badge}` has been granted to {member.mention}."
                else:
                    text = f"## {WARN}  Already Has Badge\n{member.mention} already has the `{badge}` badge."
        else:
            text = f"## {CROSS}  Invalid Badge\nBadge `{badge}` does not exist.\nAvailable: {', '.join(f'`{b}`' for b in BADGE_URLS)}"

        await ctx.send(view=_v2_simple(text))

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def remove(self, ctx, member: discord.Member, badge: str):
        badge   = badge.lower()
        user_id = member.id

        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    remove_badge(user_id, b)
                text = f"## {TICK}  All Badges Removed\n{EMJ_BADGE} All badges have been removed from {member.mention}."
            else:
                success = remove_badge(user_id, badge)
                if success:
                    text = f"## {TICK}  Badge Removed\n{EMJ_BADGE} Badge `{badge}` has been removed from {member.mention}."
                else:
                    text = f"## {WARN}  Badge Not Found\n{member.mention} does not have the `{badge}` badge."
        else:
            text = f"## {CROSS}  Invalid Badge\nBadge `{badge}` does not exist.\nAvailable: {', '.join(f'`{b}`' for b in BADGE_URLS)}"

        await ctx.send(view=_v2_simple(text))

    # ════════════════════════════════════════════
    #   PURGE BOTS / USER
    # ════════════════════════════════════════════
    @commands.command(name="forcepurgebots", aliases=["fpb"], help="Clear recent bot messages in channel.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.check(is_bot_owner)
    @commands.bot_has_permissions(manage_messages=True)
    async def _purgebot(self, ctx, prefix=None, search=100):
        await ctx.message.delete()
        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))
        await do_removal(ctx, search, predicate)

    @commands.command(name="forcepurgeuser", aliases=["fpu"], help="Clear recent messages of a user in channel.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.check(is_bot_owner)
    @commands.bot_has_permissions(manage_messages=True)
    async def purguser(self, ctx, member: discord.Member, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)


# ═══════════════════════════════════════════════════════
#                   BADGES COG (PROFILE)
# ═══════════════════════════════════════════════════════
class Badges(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self.db_path = 'db/np.db'

    @commands.hybrid_command(aliases=['profile', 'pr'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def badges(self, ctx, member: discord.Member = None):

        loading_embed = discord.Embed(
            description=f"{LOADING} Loading **{(member or ctx.author).display_name}**'s profile...",
            color=COLOR_DARK
        )
        processing_message = await ctx.send(embed=loading_embed)

        member  = member or ctx.author
        user_id = member.id

        c.execute("SELECT * FROM badges WHERE user_id = ?", (user_id,))
        badges = c.fetchone()
        if badges:
            badges = dict(zip([column[0] for column in c.description], badges))
        else:
            badges = {k: 0 for k in BADGE_URLS.keys()}

        full_user   = await self.bot.fetch_user(member.id)
        has_nitro   = bool(full_user.avatar and full_user.avatar.is_animated()) or bool(full_user.banner)
        has_boost   = False
        if not member.bot:
            for guild in self.bot.guilds:
                if member in guild.members and guild.premium_subscription_count > 0 and member in guild.premium_subscribers:
                    has_boost = True
                    break

        user_flags  = member.public_flags
        user_badges = [label for flag, label in DISCORD_BADGE_MAP.items() if getattr(user_flags, flag, False)]
        if has_nitro and not member.bot:
            user_badges.append(f"{EMJ_NITRO} Nitro Subscriber")
        if has_boost:
            user_badges.append(f"{EMJ_BOOST} Server Booster")

        has_bot_badges = any(value == 1 for value in badges.values())

        badge_size   = 120
        padding      = 80
        num_columns  = 4
        image_width  = 960
        image_height = 540

        embed = discord.Embed(
            title=f"{EMJ_PROFILE}  {member.display_name}'s Profile",
            color=COLOR_GOLD
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        embed.add_field(
            name=f"{EMJ_CLOCK} Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:F>\n(<t:{int(member.created_at.timestamp())}:R>)",
            inline=True
        )
        embed.add_field(
            name=f"{EMJ_GUILD} Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:F>\n(<t:{int(member.joined_at.timestamp())}:R>)",
            inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"][:8]
        embed.add_field(
            name=f"🎭 Roles [{len(member.roles) - 1}]",
            value=" ".join(roles) if roles else "No roles",
            inline=False
        )
        embed.add_field(
            name="🏷️ Discord Badges",
            value="\n".join(user_badges) if user_badges else "No Discord badges",
            inline=False
        )
        bot_badge_names = [f"`{BADGE_NAMES[k]}`" for k, v in badges.items() if v == 1]
        embed.add_field(
            name=f"{EMJ_BADGE} CupidX Badges",
            value=" ".join(bot_badge_names) if bot_badge_names else "No CupidX badges",
            inline=False
        )
        embed.set_footer(
            text=f"Requested by {ctx.author} • ID: {member.id}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        embed.timestamp = discord.utils.utcnow()

        if has_bot_badges:
            def calculate_text_dimensions(badge_name, font, pad=1):
                text_bbox   = draw.textbbox((0, 0), badge_name, font=font)
                text_width  = (text_bbox[2] - text_bbox[0]) + 2 * pad
                text_height = (text_bbox[3] - text_bbox[1]) + 2 * pad
                return text_width, text_height

            def draw_badges(badges, draw, img):
                upper_y     = (image_height // 4) - (badge_size // 2)
                lower_y     = (3 * image_height // 4) - (badge_size // 2)
                x_positions = [padding + i * ((image_width - 2 * padding) // (num_columns - 1)) for i in range(num_columns)]
                badge_positions = [badge for badge in BADGE_URLS.keys() if badges[badge]]
                for i, badge in enumerate(badge_positions):
                    y = upper_y if i < num_columns else lower_y
                    x = x_positions[i % num_columns]
                    response  = requests.get(BADGE_URLS[badge])
                    badge_img = Image.open(BytesIO(response.content)).resize((badge_size, badge_size))
                    img.paste(badge_img, (x - badge_size // 2, y), badge_img)
                    text_width, _ = calculate_text_dimensions(BADGE_NAMES[badge], font)
                    draw.text((x - text_width // 2, y + badge_size + 5), BADGE_NAMES[badge], fill=(255, 215, 0), font=font)

            img  = Image.new('RGBA', (image_width, image_height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_PATH, 25)
            draw_badges(badges, draw, img)

            with BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='badge.png')

            embed.set_image(url="attachment://badge.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

        await processing_message.delete()


async def setup(client):
    await client.add_cog(Owner(client))
    await client.add_cog(Badges(client))
pe(FONT_PATH, 25)
            draw_badges(badges, draw, img)

            with BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='badge.png')

            embed.set_image(url="attachment://badge.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

        await processing_message.delete()


async def setup(client):
    await client.add_cog(Owner(client))
    await client.add_cog(Badges(client))
