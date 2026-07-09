from __future__ import annotations
import discord
from utils.detectfile import *
from discord.ext import commands, tasks
import aiosqlite
import datetime
import random
import string
import asyncio
from typing import Optional
from core import Cog, Context
from utils.config import OWNER_IDS
from utils import Paginator, DescriptionEmbedPaginator
from discord.ui import View, Button


# ============================================================
#  COLORS ONLY - NO EMOJIS
# ============================================================
COLORS = {
    "premium":  0x000000,
    "success":  0x000000,
    "danger":   0x000000,
    "warning":  0x000000,
    "info":     0x000000,
    "dark":     0x000000,
    "black":    0x000000,
    "purple":   0x000000,
}


def make_embed(
    title: str,
    description: str,
    color_key: str = "premium",
    footer_text: str | None = None,
    footer_icon: str | None = None,
    author_name: str | None = None,
    author_icon: str | None = None,
    thumbnail: str | None = None,
    image: str | None = None,
    fields: list | None = None,
    bot_user=None,
) -> discord.Embed:
    color = COLORS.get(color_key, COLORS["premium"])

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.utcnow(),
    )

    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if fields:
        for f in fields:
            embed.add_field(
                name=f.get("name", "\u200b"),
                value=f.get("value", "\u200b"),
                inline=f.get("inline", False),
            )

    footer_icon_url = footer_icon or (
        bot_user.display_avatar.url if bot_user else None
    )
    embed.set_footer(
        text=footer_text or "Premium System",
        icon_url=footer_icon_url,
    )
    return embed


def generate_code(length: int = 16) -> str:
    """Random premium code generate kare: XXXX-XXXX-XXXX-XXXX"""
    chars = string.ascii_uppercase + string.digits
    raw = "".join(random.choices(chars, k=length))
    return "-".join(raw[i:i+4] for i in range(0, length, 4))


# ============================================================
#  EMOJIS  (same as help.py)
# ============================================================
E = {
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "premium":  EMOJI_DIAMOND,
    "tick":     EMOJI_TICK,
    "cross":    EMOJI_CROSS,
    "shield":   EMOJI_SHIELD,
    "settings": "<:cog:1487152125069889677>",
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "fire":     EMOJI_FIRE,
    "bot":      EMOJI_ROBOT,
    "user":     EMOJI_USER,
    "link":     EMOJI_BOND2,
    "timer":    EMOJI_TIMER2,
    "loading":  EMOJI_LOADING,
    "gift":     EMOJI_GIFT,
    "lock":     EMOJI_KEY,
    "chat":     EMOJI_APP2,
    "home":     EMOJI_UTILITY4B,
    "trash":    EMOJI_TRASH,
}

# BANNER_URL imported from utils.detectfile
BOT_COLOR  = 0x000000

# ============================================================
#  DROPDOWN
# ============================================================
import re as _re
from discord.ui import Select

def _parse_emoji(raw):
    if not raw:
        return None
    m = _re.match(r"<(a?):([\w]+):([0-9]+)>", str(raw))
    if m:
        return discord.PartialEmoji(name=m.group(2), id=int(m.group(3)), animated=bool(m.group(1)))
    cleaned = str(raw).replace("\ufe0f", "").replace("\ufe0e", "")
    return cleaned if cleaned else None


class PremiumDropdown(Select):
    def __init__(self, user, mapping: dict):
        options = [
            discord.SelectOption(
                label=name,
                value=str(data["page"]),
                description=data.get("desc", "")[:50],
            )
            for name, data in list(mapping.items())[:25]
        ]
        super().__init__(placeholder="Browse Premium Categories...", options=options, row=1)
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                f"{E['cross']} This menu belongs to someone else!", ephemeral=True
            )
        self.view.current_page = int(self.values[0])
        await self.view.refresh(interaction)


# ============================================================
#  PAGINATION VIEW  (exact help.py style)
# ============================================================
class PremiumHelpView(View):
    def __init__(self, bot, user, pages: list, mapping: dict):
        super().__init__(timeout=180)
        self.bot          = bot
        self.user         = user
        self.pages        = pages
        self.mapping      = mapping
        self.current_page = 0
        self.message      = None

        self.btn_first = Button(label="Home",  style=discord.ButtonStyle.secondary, row=0)
        self.btn_back  = Button(label="Back",  style=discord.ButtonStyle.secondary, row=0)
        self.btn_close = Button(emoji=E["trash"], style=discord.ButtonStyle.danger,  row=0)
        self.btn_next  = Button(label="Next",  style=discord.ButtonStyle.secondary, row=0)
        self.btn_last  = Button(label="Last",  style=discord.ButtonStyle.secondary, row=0)

        self.btn_first.callback = self.go_first
        self.btn_back.callback  = self.go_back
        self.btn_close.callback = self.close_menu
        self.btn_next.callback  = self.go_next
        self.btn_last.callback  = self.go_last

        self.add_item(self.btn_first)
        self.add_item(self.btn_back)
        self.add_item(self.btn_close)
        self.add_item(self.btn_next)
        self.add_item(PremiumDropdown(self.user, self.mapping))
        self.add_item(self.btn_last)

        self._sync_buttons()

    def _sync_buttons(self):
        last = len(self.pages) - 1
        self.btn_first.disabled = self.current_page == 0
        self.btn_back.disabled  = self.current_page == 0
        self.btn_next.disabled  = self.current_page == last
        self.btn_last.disabled  = self.current_page == last

    async def refresh(self, interaction: discord.Interaction):
        self._sync_buttons()
        embed = self.pages[self.current_page]
        try:
            if interaction.response.is_done():
                await interaction.message.edit(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            pass

    async def _guard(self, interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{E['cross']} Only the command executor can use this!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        try:
            if self.message:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except Exception:
            pass

    async def go_first(self, interaction):
        if not await self._guard(interaction): return
        self.current_page = 0
        await self.refresh(interaction)

    async def go_back(self, interaction):
        if not await self._guard(interaction): return
        if self.current_page > 0:
            self.current_page -= 1
        await self.refresh(interaction)

    async def close_menu(self, interaction):
        if not await self._guard(interaction): return
        try:
            await interaction.message.delete()
        except Exception:
            await interaction.response.defer()

    async def go_next(self, interaction):
        if not await self._guard(interaction): return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        await self.refresh(interaction)

    async def go_last(self, interaction):
        if not await self._guard(interaction): return
        self.current_page = len(self.pages) - 1
        await self.refresh(interaction)


# ============================================================
#  EMBED BUILDERS
# ============================================================
def _footer(user, page, total):
    return f"Page {page} of {total}  •  {user.name}"


def _build_premium_home(bot, user, prefix, total, is_owner: bool) -> discord.Embed:
    em = discord.Embed(
        title=f"{E['premium']}  CupidX — Premium Help Center",
        description=(
            f"-# *Exclusive premium features for your server.*\n"
            f"Browse categories using the **dropdown** or the **arrow buttons** below.\n"
            f"You can also run `{prefix}premium status` to check your server's status.\n\u200b"
        ),
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name=f"Requested by {user.name}", icon_url=user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)

    em.add_field(
        name=f"{E['shield']}  Server Features",
        value=(
            f"{E['dot']} `Backup, Restore, ServerHealth`\n"
            f"{E['dot']} `Scan, GhostAudit, LockRole`"
        ),
        inline=True,
    )
    em.add_field(
        name=f"{E['fire']}  Extra Tools",
        value=(
            f"{E['dot']} `Scheduled Giveaways, Global GA`\n"
            f"{E['dot']} `Music 24/7, Autoplay, Lavalink`\n"
            f"{E['dot']} `Custom Bot Profile, Say, Stock`"
        ),
        inline=True,
    )

    if is_owner:
        em.add_field(
            name=f"{E['crown']}  Owner Commands  (this page only)",
            value=(
                f"{E['dot']} `premium add/remove/list/gen/codes`\n"
                f"{E['dot']} `trialsetup`"
            ),
            inline=False,
        )

    em.set_image(url=BANNER_URL)
    em.set_footer(text=_footer(user, 1, total), icon_url=bot.user.display_avatar.url)
    return em


def _build_page(bot, user, title: str, emoji: str, fields: list, page: int, total: int) -> discord.Embed:
    em = discord.Embed(
        title=f"{emoji}  {title}",
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name="CupidX Premium Help", icon_url=bot.user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)
    for name, value in fields:
        em.add_field(name=f"{E['dot']}  {name}", value=value, inline=False)
    em.set_footer(text=_footer(user, page, total), icon_url=bot.user.display_avatar.url)
    return em


# ============================================================
#  COG
# ============================================================
class Premium(Cog):
    def __init__(self, client):
        self.client = client
        self.db_path = "db/premium.db"
        self.log_channel_id = 1477684118916567102
        self.trial_channel_id = 1487370590930206871

        self.client.loop.create_task(self.setup_database())
        self.check_expiries.start()

    def _e(self, *args, **kwargs) -> discord.Embed:
        return make_embed(*args, **kwargs, bot_user=self.client.user)

    # ----------------------------------------------------------
    #  DATABASE SETUP
    # ----------------------------------------------------------
    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS premium_guilds (
                    guild_id         INTEGER PRIMARY KEY,
                    expiry_time      TEXT,
                    custom_pfp       TEXT,
                    custom_banner    TEXT,
                    added_by         INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trial_claims (
                    guild_id    INTEGER PRIMARY KEY,
                    claimed_at  TEXT,
                    claimed_by  INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS premium_codes (
                    code        TEXT PRIMARY KEY,
                    duration    TEXT,
                    created_by  INTEGER,
                    created_at  TEXT,
                    used_by     INTEGER DEFAULT NULL,
                    used_at     TEXT DEFAULT NULL,
                    used_guild  INTEGER DEFAULT NULL
                )
            """)
            await db.commit()

    def cog_unload(self):
        self.check_expiries.cancel()

    # ----------------------------------------------------------
    #  DURATION PARSER
    # ----------------------------------------------------------
    def parse_duration(self, duration_str: str) -> Optional[datetime.timedelta]:
        if duration_str.lower() == "lifetime":
            return None
        import re
        units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
        match = re.match(r"(\d+)(mo|[smhdwy])", duration_str.lower())
        if not match:
            return None
        amount, unit = int(match.group(1)), match.group(2)
        if unit == "mo":
            return datetime.timedelta(days=amount * 30)
        if unit == "y":
            return datetime.timedelta(days=amount * 365)
        if unit in units:
            return datetime.timedelta(**{units[unit]: amount})
        return None

    def _fmt_expiry(self, delta: Optional[datetime.timedelta]) -> str:
        if delta is None:
            return "Never"
        ts = int((datetime.datetime.utcnow() + delta).timestamp())
        return f"<t:{ts}:F>"

    # ----------------------------------------------------------
    #  EXPIRY CHECKER
    # ----------------------------------------------------------
    @tasks.loop(minutes=5)
    async def check_expiries(self):
        await self.client.wait_until_ready()
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.utcnow().isoformat()
            async with db.execute(
                "SELECT guild_id, added_by FROM premium_guilds "
                "WHERE expiry_time IS NOT NULL AND expiry_time <= ?",
                (now,),
            ) as cursor:
                expired = await cursor.fetchall()

            for guild_id, added_by in expired:
                await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (guild_id,))
                await db.commit()

                # Reset bot profile customizations when premium expires
                guild = self.client.get_guild(guild_id)
                if guild:
                    try:
                        await guild.me.edit(nick=None)
                    except Exception:
                        pass
                    try:
                        route = discord.http.Route("PATCH", f"/guilds/{guild_id}/members/@me")
                        await self.client.http.request(route, json={"avatar": None, "banner": None})
                    except Exception:
                        pass

                log_channel = self.client.get_channel(self.log_channel_id)
                if log_channel:
                    guild_name = guild.name if guild else "Unknown Guild"
                    await log_channel.send(embed=self._e(
                        title="Premium Expired",
                        description=f"**Guild:** {guild_name} (`{guild_id}`)\n**Status:** Premium Removed",
                        color_key="danger",
                    ))

    # ----------------------------------------------------------
    #  PREMIUM CHECK HELPER
    # ----------------------------------------------------------
    async def is_premium(self, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM premium_guilds WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                return await cursor.fetchone() is not None

    def _premium_required_embed(self) -> discord.Embed:
        return self._e(
            title="Premium Required",
            description="This command is only available for **Premium Guilds**.\nUse `premium redeem <code>` or contact the bot owner.",
            color_key="warning",
        )

    # ============================================================
    #  MAIN premium COMMAND - ZENO STYLE CLEAN MENU
    # ============================================================
    @commands.group(name="premium", invoke_without_command=True)
    async def premium_group(self, ctx: Context):
        is_owner = ctx.author.id in OWNER_IDS

        if is_owner:
            await self._send_owner_premium_menu(ctx)
        else:
            await self._send_user_premium_menu(ctx)

    # ── Owner Menu ─────────────────────────────────────────────
    async def _send_owner_premium_menu(self, ctx: Context):
        """Bot owner ke liye full paginated premium help — help.py exact style"""
        import asyncio as _asyncio
        p    = ctx.prefix or "$"
        user = ctx.author

        pages   = []
        mapping = {}
        TOTAL   = 9  # home + 8 category pages

        # Page 0 — Home
        pages.append(_build_premium_home(self.client, user, p, TOTAL, is_owner=True))
        mapping["Home"] = {"emoji": E["premium"], "page": 0, "desc": "Premium overview & owner tools"}

        # Page 1 — Owner: Premium Management
        pages.append(_build_page(
            self.client, user,
            "Premium Management  (Owner Only)", E["crown"],
            [
                ("premium add <guild_id> <duration>",  "`Manually activate premium for any guild`\nDurations: `1d` `7d` `30d` `1mo` `1y` `lifetime`"),
                ("premium remove <guild_id>",          "`Remove premium from a guild immediately`\nAlso resets custom bot profile"),
                ("premium list",                       "`View all currently active premium guilds`\nShows guild name, ID and expiry"),
                ("premium gen <duration>",             "`Generate a redeemable premium code`\nCode is shown in channel"),
                ("premium codes",                      "`View all generated codes and their status`\nShows used / available + guild info"),
                ("trialsetup",                         "`Post the 7-day trial instructions embed`\nOnly works inside the trial channel"),
            ],
            2, TOTAL,
        ))
        mapping["Owner — Premium Mgmt"] = {"emoji": E["crown"], "page": 1, "desc": "add, remove, list, gen, codes, trialsetup"}

        # Page 2 — Backup
        pages.append(_build_page(
            self.client, user,
            "Server Backup", E["shield"],
            [
                ("backup create <n>",  "`Create a full server backup`\nSaves channels, roles, permissions & settings"),
                ("backup restore <n>", "`Restore server from a saved backup`\nOverwrites current server structure"),
                ("backup list",        "`View all saved backups for this server`"),
                ("backup delete <n>",  "`Delete a specific backup permanently`"),
            ],
            3, TOTAL,
        ))
        mapping["Backup"] = {"emoji": E["shield"], "page": 2, "desc": "create, restore, list, delete"}

        # Page 3 — Security+
        pages.append(_build_page(
            self.client, user,
            "Security+", E["settings"],
            [
                ("scan",         "`Deep-scan server for suspicious activity`\nDetects bots, raider accounts & more"),
                ("serverhealth", "`Full server health & stats report`\nSecurity score, member quality, activity"),
                ("ghostaudit",   "`Audit ghost members & inactive bots`\nFind accounts that never spoke or reacted"),
            ],
            4, TOTAL,
        ))
        mapping["Security+"] = {"emoji": E["settings"], "page": 3, "desc": "scan, serverhealth, ghostaudit"}

        # Page 4 — Giveaways & LockRole
        pages.append(_build_page(
            self.client, user,
            "Giveaways & LockRole", E["gift"],
            [
                ("gschedule",                                   "`Schedule a giveaway for a future time`"),
                ("gsgend",                                      "`End a scheduled giveaway early`"),
                ("gsreroll",                                    "`Reroll winner of a scheduled giveaway`"),
                ("glstart",                                     "`Start a global cross-server giveaway`\nPremium exclusive"),
                ("lockrole add/remove/list/reset/config",       "`Lock roles — only WL users can assign`"),
                ("lockrole wl add/remove/list <@user> <@role>", "`Whitelist users for locked roles`"),
                ("lockrole punishment set <@role> <action>",    "`Set ban/kick/remove for violators`"),
                ("lockrole logging setup <#channel>",           "`Log all lockrole violations`"),
            ],
            5, TOTAL,
        ))
        mapping["Giveaways & LockRole"] = {"emoji": E["gift"], "page": 4, "desc": "gschedule, gsreroll, glstart, lockrole"}

        # Page 5 — Music Premium
        pages.append(_build_page(
            self.client, user,
            "Music  (Premium)", E["fire"],
            [
                ("music autoplay", "`Toggle autoplay — auto-queue related tracks`\nPremium only"),
                ("music 247",      "`Toggle 24/7 mode — stay in VC forever`\nPremium only"),
                ("music lavalink", "`Show Lavalink node connection status`\nPremium only"),
            ],
            6, TOTAL,
        ))
        mapping["Music Premium"] = {"emoji": E["fire"], "page": 5, "desc": "autoplay, 247, lavalink"}

        # Page 6 — Custom Profile & Extras
        pages.append(_build_page(
            self.client, user,
            "Custom Profile & Extras", E["star"],
            [
                ("customprofile avatar <url>", "`Set a custom server-specific bot avatar`"),
                ("customprofile banner <url>", "`Set a custom server-specific bot banner`"),
                ("customprofile reset",        "`Reset bot profile back to default`"),
                ("say <message>",              "`Make the bot send a message as itself`"),
                ("stock",                      "`View bot invite / premium stock info`"),
                ("applytemplate <link>",       "`Apply a Discord template to the server`\nChanges channels, roles & structure"),
            ],
            7, TOTAL,
        ))
        mapping["Custom Profile & Extras"] = {"emoji": E["star"], "page": 6, "desc": "customprofile, say, stock, applytemplate"}

        # Page 7 — Premium Extras
        pages.append(_build_page(
            self.client, user,
            "Premium Extras", E["fire"],
            [
                ("antiraid on/off",                  "`Auto-lockdown server when raid is detected`\nLocks all text channels if 10+ users join in 1 min"),
                ("serverlock [reason]",              "`Lock the entire server instantly`"),
                ("serverunlock [reason]",            "`Unlock the entire server`"),
                ("fakepermit @user <permission>",    "`Send a fake 'Permission Granted' embed (prank)`"),
                ("embedbuilder [#channel]",          "`Step-by-step interactive embed creator`\nNo coding needed"),
                ("reminder <time> <message>",        "`Bot will DM you a reminder`\nTime format: `10m`, `2h`, `1d` (max 7d)"),
            ],
            8, TOTAL,
        ))
        mapping["Premium Extras"] = {"emoji": E["fire"], "page": 7, "desc": "antiraid, serverlock, shadowban, massdm..."}

        # Page 8 — Activate Premium
        pages.append(_build_page(
            self.client, user,
            "Activate Premium", E["premium"],
            [
                ("premium redeem <code>", "`Redeem a premium code for this server`\nRequires Administrator"),
                ("premium status",        "`Check current premium status of this server`\nShows expiry & who granted it"),
                ("premium trial",         "`Claim a free 7-day premium trial`\nOne per server — visit the trial channel"),
            ],
            9, TOTAL,
        ))
        mapping["Activate Premium"] = {"emoji": E["premium"], "page": 8, "desc": "redeem, status, trial"}

        # Loading then send
        loading_em = discord.Embed(
            description=f"{E['loading']}  Loading Premium Help...",
            color=BOT_COLOR,
        )
        msg = await ctx.reply(embed=loading_em, mention_author=False)
        await _asyncio.sleep(1)

        view = PremiumHelpView(self.client, user, pages, mapping)
        view._sync_buttons()
        await msg.edit(embed=pages[0], view=view)
        view.message = msg

    # ── User Menu ──────────────────────────────────────────────
    async def _send_user_premium_menu(self, ctx: Context):
        """Normal user ke liye paginated premium help — help.py exact style"""
        import asyncio as _asyncio
        p    = ctx.prefix or "$"
        user = ctx.author

        pages   = []
        mapping = {}
        TOTAL   = 7  # home + 6 category pages

        # Page 0 — Home
        pages.append(_build_premium_home(self.client, user, p, TOTAL, is_owner=False))
        mapping["Home"] = {"emoji": E["premium"], "page": 0, "desc": "Premium overview & features"}

        # Page 1 — Backup
        pages.append(_build_page(
            self.client, user,
            "Server Backup", E["shield"],
            [
                ("backup create <n>",  "`Create a full server backup`\nSaves channels, roles, permissions & settings"),
                ("backup restore <n>", "`Restore server from a saved backup`\nOverwrites current server structure"),
                ("backup list",        "`View all saved backups for this server`"),
                ("backup delete <n>",  "`Delete a specific backup permanently`"),
            ],
            2, TOTAL,
        ))
        mapping["Backup"] = {"emoji": E["shield"], "page": 1, "desc": "create, restore, list, delete"}

        # Page 3 — Security+
        pages.append(_build_page(
            self.client, user,
            "Security+", E["settings"],
            [
                ("scan",         "`Deep-scan server for suspicious activity`\nDetects bots, raider accounts & more"),
                ("serverhealth", "`Full server health & stats report`\nSecurity score, member quality, activity"),
                ("ghostaudit",   "`Audit ghost members & inactive bots`\nFind accounts that never spoke or reacted"),
            ],
            3, TOTAL,
        ))
        mapping["Security+"] = {"emoji": E["settings"], "page": 2, "desc": "scan, serverhealth, ghostaudit"}

        # Page 4 — Giveaways & LockRole
        pages.append(_build_page(
            self.client, user,
            "Giveaways & LockRole", E["gift"],
            [
                ("gschedule",                                   "`Schedule a giveaway for a future time`"),
                ("gsgend",                                      "`End a scheduled giveaway early`"),
                ("gsreroll",                                    "`Reroll winner of a scheduled giveaway`"),
                ("glstart",                                     "`Start a global cross-server giveaway`\nPremium exclusive"),
                ("lockrole add/remove/list/reset/config",       "`Lock roles — only WL users can assign`"),
                ("lockrole wl add/remove/list <@user> <@role>", "`Whitelist users for locked roles`"),
                ("lockrole punishment set <@role> <action>",    "`Set ban/kick/remove for violators`"),
                ("lockrole logging setup <#channel>",           "`Log all lockrole violations`"),
            ],
            4, TOTAL,
        ))
        mapping["Giveaways & LockRole"] = {"emoji": E["gift"], "page": 3, "desc": "gschedule, gsreroll, glstart, lockrole"}

        # Page 5 — Music Premium + Custom Profile
        pages.append(_build_page(
            self.client, user,
            "Music Premium & Custom Profile", E["fire"],
            [
                ("music autoplay",             "`Toggle autoplay — auto-queue related tracks`\nPremium only"),
                ("music 247",                  "`Toggle 24/7 mode — stay in VC forever`\nPremium only"),
                ("music lavalink",             "`Show Lavalink node connection status`\nPremium only"),
                ("customprofile avatar <url>", "`Set a custom server-specific bot avatar`"),
                ("customprofile banner <url>", "`Set a custom server-specific bot banner`"),
                ("customprofile reset",        "`Reset bot profile back to default`"),
                ("say <message>",              "`Make the bot send a message as itself`"),
                ("stock",                      "`View bot invite / premium stock info`"),
                ("applytemplate <link>",       "`Apply a Discord template to the server`"),
            ],
            5, TOTAL,
        ))
        mapping["Music & Custom Profile"] = {"emoji": E["fire"], "page": 4, "desc": "music autoplay/247, customprofile, say"}

        # Page 6 — Premium Extras
        pages.append(_build_page(
            self.client, user,
            "Premium Extras", E["fire"],
            [
                ("antiraid on/off",                  "`Auto-lockdown server when raid is detected`\nLocks all text channels if 10+ users join in 1 min"),
                ("serverlock [reason]",              "`Lock the entire server instantly`"),
                ("serverunlock [reason]",            "`Unlock the entire server`"),
                ("fakepermit @user <permission>",    "`Send a fake 'Permission Granted' embed (prank)`"),
                ("embedbuilder [#channel]",          "`Step-by-step interactive embed creator`\nNo coding needed"),
                ("reminder <time> <message>",        "`Bot will DM you a reminder`\nTime format: `10m`, `2h`, `1d` (max 7d)"),
                ("shadowban @user [reason]",         "`Silently delete all messages — user won't know`"),
                ("shadowunban @user",                "`Remove a shadow ban`"),
                ("shadowlist",                       "`View all shadow banned users in this server`"),
                ("massdm <message>",                 "`Send a DM to all server members`"),
                ("massdm role @role <message>",      "`Send a DM to all members with a specific role`"),
            ],
            6, TOTAL,
        ))
        mapping["Premium Extras"] = {"emoji": E["fire"], "page": 5, "desc": "antiraid, serverlock, shadowban, massdm..."}

        # Page 7 — Activate Premium
        pages.append(_build_page(
            self.client, user,
            "Activate Premium", E["premium"],
            [
                ("premium redeem <code>", "`Redeem a premium code for this server`\nRequires Administrator"),
                ("premium status",        "`Check current premium status of this server`\nShows expiry & who granted it"),
                ("premium trial",         "`Claim a free 7-day premium trial`\nOne per server — visit the trial channel"),
            ],
            7, TOTAL,
        ))
        mapping["Activate Premium"] = {"emoji": E["premium"], "page": 6, "desc": "redeem, status, trial"}

        # Loading then send
        loading_em = discord.Embed(
            description=f"{E['loading']}  Loading Premium Help...",
            color=BOT_COLOR,
        )
        msg = await ctx.reply(embed=loading_em, mention_author=False)
        await _asyncio.sleep(1)

        view = PremiumHelpView(self.client, user, pages, mapping)
        view._sync_buttons()
        await msg.edit(embed=pages[0], view=view)
        view.message = msg

    # ============================================================
    #  OWNER COMMANDS
    # ============================================================
    @premium_group.command(name="add")
    @commands.is_owner()
    async def premium_add(self, ctx: Context, guild_id: int, duration: str):
        delta = self.parse_duration(duration)
        if delta is None and duration.lower() != "lifetime":
            return await ctx.reply(embed=self._e(
                title="Invalid Duration",
                description=f"Could not parse `{duration}`.\nValid: `1d`, `7d`, `30d`, `1mo`, `1y`, `lifetime`",
                color_key="warning",
            ))

        expiry = (datetime.datetime.utcnow() + delta).isoformat() if delta else None
        expiry_display = self._fmt_expiry(delta)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO premium_guilds (guild_id, expiry_time, added_by) VALUES (?, ?, ?)",
                (guild_id, expiry, ctx.author.id),
            )
            await db.commit()

        guild = self.client.get_guild(guild_id)
        guild_name = guild.name if guild else "Unknown Guild"

        await ctx.reply(embed=self._e(
            title="Premium Added",
            description=f"**Guild:** {guild_name} (`{guild_id}`)\n**Expires:** {expiry_display}\n**Added By:** {ctx.author.mention}",
            color_key="success",
        ))

        log_channel = self.client.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(embed=self._e(
                title="Premium Activated",
                description=f"**Guild:** {guild_name} (`{guild_id}`)\n**Duration:** `{duration}`\n**Expires:** {expiry_display}\n**Added By:** {ctx.author.mention}",
                color_key="success",
            ))

    @premium_group.command(name="remove")
    @commands.is_owner()
    async def premium_remove(self, ctx: Context, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (guild_id,))
            await db.commit()

        guild = self.client.get_guild(guild_id)

        # Reset bot profile customizations on manual premium removal
        if guild:
            try:
                await guild.me.edit(nick=None)
            except Exception:
                pass
            try:
                route = discord.http.Route("PATCH", f"/guilds/{guild_id}/members/@me")
                await self.client.http.request(route, json={"avatar": None, "banner": None})
            except Exception:
                pass

        guild_name = guild.name if guild else "Unknown Guild"

        await ctx.reply(embed=self._e(
            title="Premium Removed",
            description=f"**Guild:** {guild_name} (`{guild_id}`)\nPremium has been removed successfully.",
            color_key="success",
        ))

        log_channel = self.client.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(embed=self._e(
                title="Premium Removed",
                description=f"**Guild:** {guild_name} (`{guild_id}`)\n**Removed By:** {ctx.author.mention}",
                color_key="danger",
            ))

    @premium_group.command(name="list")
    @commands.is_owner()
    async def premium_list(self, ctx: Context):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id, expiry_time FROM premium_guilds") as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.reply(embed=self._e(
                title="No Premium Guilds",
                description="No premium guilds found.",
                color_key="warning",
            ))

        entries = []
        for gid, expiry in rows:
            expiry_str = (
                f"<t:{int(datetime.datetime.fromisoformat(expiry).timestamp())}:R>"
                if expiry else "Lifetime"
            )
            guild = self.client.get_guild(gid)
            guild_name = f" — **{guild.name}**" if guild else ""
            entries.append(f"`{gid}`{guild_name} | {expiry_str}")

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Premium Guilds [{len(rows)}]",
                per_page=10,
                color=COLORS["premium"],
            ),
            ctx=ctx,
        )
        await paginator.paginate()

    @premium_group.command(name="status")
    async def premium_status(self, ctx: Context):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT expiry_time, added_by FROM premium_guilds WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return await ctx.reply(embed=self._e(
                title="Premium Status",
                description=f"This server does **not** have Premium.\n\nUse `{ctx.prefix}premium redeem <code>` to activate.",
                color_key="warning",
                thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
            ))

        expiry, added_by = row
        if expiry:
            ts = int(datetime.datetime.fromisoformat(expiry).timestamp())
            expiry_display = f"<t:{ts}:F>\n*(expires <t:{ts}:R>)*"
        else:
            expiry_display = "**Lifetime** — Never expires"

        adder = self.client.get_user(added_by)
        adder_str = f"{adder.mention}" if adder else f"`{added_by}`"

        await ctx.reply(embed=self._e(
            title="Premium Status",
            description="This server has **Active Premium**!",
            color_key="success",
            thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
            fields=[
                {"name": "Server", "value": f"**{ctx.guild.name}**\n`{ctx.guild.id}`", "inline": True},
                {"name": "Expires", "value": expiry_display, "inline": True},
                {"name": "Granted By", "value": adder_str, "inline": True},
            ],
        ))

    # ============================================================
    #  PREMIUM CODE SYSTEM - MODIFIED: SHOW IN CHANNEL NOT DM
    # ============================================================
    @premium_group.command(name="gen")
    @commands.is_owner()
    async def premium_gen(self, ctx: Context, duration: str):
        delta = self.parse_duration(duration)
        if delta is None and duration.lower() != "lifetime":
            return await ctx.reply(embed=self._e(
                title="Invalid Duration",
                description=f"Could not parse `{duration}`.\nValid: `1d`, `7d`, `30d`, `1mo`, `1y`, `lifetime`",
                color_key="warning",
            ))

        code = generate_code()
        now = datetime.datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO premium_codes (code, duration, created_by, created_at) VALUES (?, ?, ?, ?)",
                (code, duration, ctx.author.id, now),
            )
            await db.commit()

        expiry_display = self._fmt_expiry(delta)

        # SHOW IN CHANNEL - NOT DM
        await ctx.reply(embed=self._e(
            title="Premium Code Generated",
            description=f"**Code:**\n```\n{code}\n```\n**Duration:** `{duration}` ({expiry_display})\n\n**Usage:** `{ctx.prefix}premium redeem {code}`",
            color_key="premium",
        ))

        log_channel = self.client.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(embed=self._e(
                title="Premium Code Created",
                description=f"**Code:** `{code}`\n**Duration:** `{duration}`\n**Created By:** {ctx.author.mention}",
                color_key="info",
            ))

    @premium_group.command(name="redeem")
    @commands.has_permissions(administrator=True)
    async def premium_redeem(self, ctx: Context, code: str):
        code = code.upper().strip()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT duration, used_by FROM premium_codes WHERE code = ?", (code,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return await ctx.reply(embed=self._e(
                title="Invalid Code",
                description=f"The code `{code}` is **invalid** or does not exist.\nMake sure you typed it correctly.",
                color_key="danger",
            ))

        duration, used_by = row

        if used_by is not None:
            return await ctx.reply(embed=self._e(
                title="Code Already Used",
                description="This code has already been **redeemed**.\nContact the bot owner for a new code.",
                color_key="warning",
            ))

        delta = self.parse_duration(duration)
        expiry = (datetime.datetime.utcnow() + delta).isoformat() if delta else None
        expiry_display = self._fmt_expiry(delta)
        now = datetime.datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE premium_codes SET used_by = ?, used_at = ?, used_guild = ? WHERE code = ?",
                (ctx.author.id, now, ctx.guild.id, code),
            )
            await db.execute(
                "INSERT OR REPLACE INTO premium_guilds (guild_id, expiry_time, added_by) VALUES (?, ?, ?)",
                (ctx.guild.id, expiry, ctx.author.id),
            )
            await db.commit()

        await ctx.reply(embed=self._e(
            title="Premium Activated!",
            description="**Premium has been activated for this server!**",
            color_key="success",
            thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
            fields=[
                {"name": "Server", "value": f"**{ctx.guild.name}**", "inline": True},
                {"name": "Expires", "value": expiry_display, "inline": True},
                {"name": "Redeemed By", "value": ctx.author.mention, "inline": True},
            ],
        ))

        log_channel = self.client.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(embed=self._e(
                title="Premium Code Redeemed",
                description=f"**Code:** `{code}`\n**Guild:** {ctx.guild.name} (`{ctx.guild.id}`)\n**Expires:** {expiry_display}\n**Redeemed By:** {ctx.author.mention}",
                color_key="success",
            ))

    @premium_group.command(name="codes")
    @commands.is_owner()
    async def premium_codes(self, ctx: Context):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT code, duration, used_by, used_guild FROM premium_codes ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.reply(embed=self._e(
                title="No Codes",
                description="No premium codes have been generated yet.",
                color_key="info",
            ))

        entries = []
        for code, duration, used_by, used_guild in rows:
            if used_by:
                status = f"Used — Guild `{used_guild}`"
            else:
                status = "Available"
            entries.append(f"`{code}` | `{duration}` | {status}")

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Premium Codes [{len(rows)}]",
                per_page=10,
                color=COLORS["premium"],
            ),
            ctx=ctx,
        )
        await paginator.paginate()

    # ============================================================
    #  TRIAL SYSTEM
    # ============================================================
    def _build_trial_instructions_embed(self) -> discord.Embed:
        return discord.Embed(
            title="CupidX 7-Day Free Trial",
            description="**Get 7 Days of Premium Absolutely FREE!**\n\n"
                       "**How to Claim:**\n"
                       "1. Type your **Server ID** in this channel\n"
                       "2. Bot will automatically activate premium\n"
                       "3. Enjoy all premium features for 7 days!\n\n"
                       "**Rules:**\n"
                       "• One trial per server only\n"
                       "• Cannot claim again after expiry\n"
                       "• Premium auto-removes after 7 days\n\n"
                       "**Features Included:**\n"
                       "• Server Backup & Restore\n"
                       "• Message Leaderboards\n"
                       "• Exclusive Admin Tools\n"
                       "• Custom Bot Profile",
            color=COLORS["premium"],
            timestamp=datetime.datetime.utcnow()
        ).set_footer(
            text="CupidX Premium Trial System",
            icon_url=self.client.user.display_avatar.url if self.client.user else None
        )

    async def _has_claimed_trial(self, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM trial_claims WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def _claim_trial(self, guild_id: int, user_id: int) -> bool:
        try:
            expiry = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO trial_claims (guild_id, claimed_at, claimed_by) VALUES (?, ?, ?)",
                    (guild_id, datetime.datetime.utcnow().isoformat(), user_id)
                )
                await db.execute(
                    "INSERT OR REPLACE INTO premium_guilds (guild_id, expiry_time, added_by) VALUES (?, ?, ?)",
                    (guild_id, expiry, user_id),
                )
                await db.commit()
            return True
        except Exception as e:
            print(f"Trial claim error: {e}")
            return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Trial Channel
        if message.channel.id == self.trial_channel_id:
            content = message.content.strip()
            if not content.isdigit():
                return

            guild_id = int(content)

            if await self._has_claimed_trial(guild_id):
                await message.reply(embed=self._e(
                    title="Trial Already Claimed",
                    description="**This server has already claimed the free trial!**\n\nEach server can only claim once.\nContact the bot owner to purchase premium.",
                    color_key="warning",
                ), delete_after=10)
                await message.delete(delay=5)
                return

            success = await self._claim_trial(guild_id, message.author.id)
            if success:
                expiry_timestamp = int(
                    (datetime.datetime.utcnow() + datetime.timedelta(days=7)).timestamp()
                )
                await message.reply(embed=self._e(
                    title="Premium Activated!",
                    description=f"**7-Day Premium Trial Activated!**\n\n"
                               f"**Server ID:** `{guild_id}`\n"
                               f"**Expires:** <t:{expiry_timestamp}:F>\n"
                               f"**Claimed By:** {message.author.mention}\n\n"
                               f"Enjoy your premium features!",
                    color_key="success",
                ))
                log_channel = self.client.get_channel(self.log_channel_id)
                if log_channel:
                    await log_channel.send(embed=self._e(
                        title="Trial Claimed",
                        description=f"**Guild ID:** `{guild_id}`\n"
                                   f"**Claimed By:** {message.author.mention} (`{message.author.id}`)\n"
                                   f"**Expires:** <t:{expiry_timestamp}:F>\n"
                                   f"**Type:** 7-Day Free Trial",
                        color_key="success",
                    ))
                await message.delete()
                await asyncio.sleep(5)
                await message.channel.send(embed=self._build_trial_instructions_embed())
            else:
                await message.reply(embed=self._e(
                    title="Activation Failed",
                    description="Failed to activate premium.\nContact the bot owner for help.",
                    color_key="danger",
                ), delete_after=10)
                await message.delete(delay=5)
            return


    @commands.command(name="trialsetup")
    @commands.is_owner()
    async def trial_setup(self, ctx: Context):
        if ctx.channel.id != self.trial_channel_id:
            return await ctx.reply("This command only works in the trial channel!")
        embed = self._build_trial_instructions_embed()
        await ctx.send(embed=embed)
        await ctx.message.delete()

    # ============================================================
    #  ERROR HANDLERS
    # ============================================================
    @premium_add.error
    @premium_remove.error
    @premium_list.error
    @premium_gen.error
    @premium_codes.error
    async def owner_command_error(self, ctx: Context, error):
        if isinstance(error, commands.NotOwner):
            await ctx.reply(embed=self._e(
                title="Unauthorized",
                description="Only the **bot owner** can use this command.",
                color_key="danger",
            ))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=self._e(
                title="Missing Argument",
                description=f"Please provide all required arguments.\nUsage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                color_key="warning",
            ))

    @premium_redeem.error
    async def redeem_error(self, ctx: Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(embed=self._e(
                title="Missing Permissions",
                description="You need **Administrator** to redeem a code.",
                color_key="danger",
            ))



async def setup(client):
    await client.add_cog(Premium(client))
