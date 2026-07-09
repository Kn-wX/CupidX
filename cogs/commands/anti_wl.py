import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.Tools import blacklist_check, ignore_check
from utils.detectfile import *

# ================================================
# EMOJI CONFIG  (same as automod.py)
# ================================================

class E:
    # Status
    ENABLED  = EMOJI_ENABLE
    DISABLED = EMOJI_DISABLE
    LOADING  = EMOJI_PIN
    TIMER    = EMOJI_TIMER

    # Actions
    TICK     = EMOJI_TICK
    CROSS    = EMOJI_SWORD
    WARNING  = EMOJI_WARN
    DELETE   = EMOJI_TRASH
    SHIELD   = EMOJI_SHIELD
    SETTINGS = ""

    # Info
    USER    = EMOJI_USER
    MENTION = EMOJI_ROBOT3
    MAIL    = EMOJI_MAIL
    REASON  = EMOJI_APP
    ROLE    = EMOJI_USE

    # Antinuke specific
    WL_ON   = EMOJI_ENABLE
    WL_OFF  = EMOJI_DISABLE
    DOT     = EMOJI_DOT

# ================================================
# DB HELPERS
# ================================================

DB = "db/anti.db"

async def db_fetch(query: str, params: tuple = (), one: bool = False):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone() if one else await cur.fetchall()

async def db_exec(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB) as db:
        await db.execute(query, params)
        await db.commit()

# ================================================
# V2 LAYOUT HELPERS  (automod style)
# ================================================

def _layout(text: str = None, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    """Create a LayoutView with optional text and control rows."""
    view = discord.ui.LayoutView(timeout=timeout)
    items = []
    if text:
        items.append(discord.ui.TextDisplay(text))
    if controls:
        if items:
            items.append(discord.ui.Separator())
        for ctrl in controls:
            items.append(ctrl)
    view.add_item(discord.ui.Container(*items))
    return view

# ================================================
# WHITELIST FIELDS CONFIG
# ================================================

WL_FIELDS = {
    'ban':      'Ban',
    'kick':     'Kick',
    'prune':    'Prune',
    'botadd':   'Bot Add',
    'serverup': 'Server Update',
    'memup':    'Member Update',
    'chcr':     'Channel Create',
    'chdl':     'Channel Delete',
    'chup':     'Channel Update',
    'rlcr':     'Role Create',
    'rlup':     'Role Update',
    'rldl':     'Role Delete',
    'meneve':   'Mention @everyone',
    'mngweb':   'Manage Webhooks',
}

# ================================================
# WHITELIST SELECT + BUTTON VIEW
# ================================================

class WhitelistView(discord.ui.LayoutView):
    """
    Step 1 → User picks permissions via dropdown.
    "Whitelist All" button whitelists everything at once.
    All buttons are secondary (black/white) — automod style.
    """

    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.author  = author
        self.target  = target
        self.done    = False

        # ── Select ──
        self.select = discord.ui.Select(
            placeholder=f"{E.SETTINGS} Choose permissions to whitelist…",
            min_values=1,
            max_values=len(WL_FIELDS),
            options=[
                discord.SelectOption(label=name, value=key)
                for key, name in WL_FIELDS.items()
            ]
        )
        self.select.callback = self._select_cb

        # ── Whitelist All button  (black/white secondary) ──
        self.wl_all_btn = discord.ui.Button(
            label="Whitelist All",
            style=discord.ButtonStyle.secondary,
            emoji=E.TICK
        )
        self.wl_all_btn.callback = self._wl_all_cb

        self._build()

    # ── build / rebuild the Container ──
    def _build(self, header: str = None, body: str = None):
        self._children.clear()

        h = header or f"## {E.SHIELD} Whitelist Setup"
        b = body   or (
            f"**Server:** {self.author.guild.name}\n"
            f"**Executor:** <@{self.author.id}>\n"
            f"**Target:** <@{self.target.id}>\n\n"
            + "\n".join(f"{E.WL_OFF} **{name}**" for name in WL_FIELDS.values())
        )

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(h),
            discord.ui.TextDisplay(b),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.select),
            discord.ui.ActionRow(self.wl_all_btn),
        ))

    # ── interaction guard ──
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_layout(f"{E.CROSS} This isn't your whitelist session!"),
                ephemeral=True
            )
            return False
        return True

    # ── helpers ──
    async def _save_fields(self, selected: list):
        await db_exec(
            "INSERT OR IGNORE INTO whitelisted_users "
            "(guild_id, user_id) VALUES (?, ?)",
            (self.author.guild.id, self.target.id)
        )
        for key in selected:
            await db_exec(
                f"UPDATE whitelisted_users SET {key}=1 "
                "WHERE guild_id=? AND user_id=?",
                (self.author.guild.id, self.target.id)
            )

    def _result_body(self, selected: list) -> str:
        lines = []
        for key, name in WL_FIELDS.items():
            icon = E.WL_ON if key in selected else E.WL_OFF
            lines.append(f"{icon} **{name}**")
        return (
            f"**Server:** {self.author.guild.name}\n"
            f"**Executor:** <@{self.author.id}>\n"
            f"**Target:** <@{self.target.id}>\n\n"
            + "\n".join(lines)
        )

    # ── select callback ──
    async def _select_cb(self, interaction: discord.Interaction):
        # Loading state
        await interaction.response.defer()

        selected = self.select.values

        # Show loading
        loading_view = _layout(
            f"## {E.LOADING} Processing…\n"
            f"Saving whitelist for <@{self.target.id}>…"
        )
        await interaction.edit_original_response(view=loading_view)
        await asyncio.sleep(0.4)

        await self._save_fields(selected)
        self.done = True
        self.stop()

        result_view = _layout(
            f"## {E.TICK} Whitelist Complete\n"
            + self._result_body(selected),
            timeout=None
        )
        await interaction.edit_original_response(view=result_view)

    # ── whitelist all callback ──
    async def _wl_all_cb(self, interaction: discord.Interaction):
        await interaction.response.defer()

        loading_view = _layout(
            f"## {E.LOADING} Processing…\n"
            f"Whitelisting all permissions for <@{self.target.id}>…"
        )
        await interaction.edit_original_response(view=loading_view)
        await asyncio.sleep(0.4)

        all_keys = list(WL_FIELDS.keys())

        # Insert row first then set all columns
        await db_exec(
            "INSERT OR IGNORE INTO whitelisted_users "
            "(guild_id, user_id) VALUES (?, ?)",
            (self.author.guild.id, self.target.id)
        )
        set_clause = ", ".join(f"{k}=1" for k in all_keys)
        await db_exec(
            f"UPDATE whitelisted_users SET {set_clause} "
            "WHERE guild_id=? AND user_id=?",
            (self.author.guild.id, self.target.id)
        )

        self.done = True
        self.stop()

        result_view = _layout(
            f"## {E.TICK} Whitelist Complete\n"
            + self._result_body(all_keys),
            timeout=None
        )
        await interaction.edit_original_response(view=result_view)

    # ── timeout ──
    async def on_timeout(self):
        if not self.done:
            self._children.clear()
            self.add_item(discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {E.WARNING} Session Expired\n"
                    "Whitelist setup timed out. Run the command again."
                )
            ))

# ================================================
# WHITELIST COG
# ================================================

class Whitelist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        await self._init_db()

    async def _init_db(self) -> None:
        async with aiosqlite.connect(DB) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id  INTEGER,
                    user_id   INTEGER,
                    ban       BOOLEAN DEFAULT FALSE,
                    kick      BOOLEAN DEFAULT FALSE,
                    prune     BOOLEAN DEFAULT FALSE,
                    botadd    BOOLEAN DEFAULT FALSE,
                    serverup  BOOLEAN DEFAULT FALSE,
                    memup     BOOLEAN DEFAULT FALSE,
                    chcr      BOOLEAN DEFAULT FALSE,
                    chdl      BOOLEAN DEFAULT FALSE,
                    chup      BOOLEAN DEFAULT FALSE,
                    rlcr      BOOLEAN DEFAULT FALSE,
                    rlup      BOOLEAN DEFAULT FALSE,
                    rldl      BOOLEAN DEFAULT FALSE,
                    meneve    BOOLEAN DEFAULT FALSE,
                    mngweb    BOOLEAN DEFAULT FALSE,
                    mngstemo  BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            await db.commit()

    # ── permission helpers ──
    async def _has_perm(self, ctx: commands.Context) -> bool:
        if ctx.author.id == ctx.guild.owner_id:
            return True
        row = await db_fetch(
            "SELECT owner_id FROM extraowners WHERE guild_id=? AND owner_id=?",
            (ctx.guild.id, ctx.author.id),
            one=True
        )
        return bool(row)

    async def _antinuke_enabled(self, ctx: commands.Context) -> bool:
        row = await db_fetch(
            "SELECT status FROM antinuke WHERE guild_id=?",
            (ctx.guild.id,), one=True
        )
        if not row or not row[0]:
            await ctx.send(view=_layout(
                f"## {E.SHIELD} Security Disabled\n\n"
                f"**Server:** {ctx.guild.name}\n"
                f"**Status:** {E.DISABLED} Disabled\n\n"
                f"Use `{ctx.prefix}antinuke enable` to activate."
            ))
            return False
        return True

    # ================================================
    # /whitelist  —  main command
    # ================================================
    @commands.hybrid_command(name='whitelist', aliases=['wl'])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def whitelist(self, ctx: commands.Context, member: discord.Member = None):
        """Whitelist a user from specific antinuke actions."""

        if ctx.guild.member_count < 2:
            return await ctx.send(view=_layout(
                f"## {E.CROSS} Server Too Small\n"
                "Your server doesn't meet the 2-member criteria."
            ))

        if not await self._has_perm(ctx):
            return await ctx.send(view=_layout(
                f"## {E.CROSS} Access Denied\n"
                "Only **Server Owner** or **Extra Owner** can run this command!"
            ))

        if not await self._antinuke_enabled(ctx):
            return

        if not member:
            return await ctx.send(view=_layout(
                f"## {E.SHIELD} Whitelist — Usage\n\n"
                "Adds a user to the whitelist so antinuke won't take actions against them.\n\n"
                f"{E.DOT} `{ctx.prefix}whitelist @user`\n"
                f"{E.DOT} `{ctx.prefix}wl @user`"
            ))

        # Already whitelisted?
        row = await db_fetch(
            "SELECT user_id FROM whitelisted_users WHERE guild_id=? AND user_id=?",
            (ctx.guild.id, member.id), one=True
        )
        if row:
            return await ctx.send(view=_layout(
                f"## {E.WARNING} Already Whitelisted\n\n"
                f"<@{member.id}> is **already** in the whitelist.\n"
                f"Use `{ctx.prefix}unwhitelist @user` first, then try again."
            ))

        # Show interactive view
        view = WhitelistView(ctx.author, member)
        await ctx.send(view=view)

    # ================================================
    # /whitelisted  —  list
    # ================================================
    @commands.hybrid_command(name='whitelisted', aliases=['wlist'])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def whitelisted(self, ctx: commands.Context):
        """Show all whitelisted users."""
        if not await self._has_perm(ctx) or not await self._antinuke_enabled(ctx):
            return

        rows = await db_fetch(
            "SELECT user_id FROM whitelisted_users WHERE guild_id=?",
            (ctx.guild.id,)
        )
        if not rows:
            return await ctx.send(view=_layout(
                f"## {E.CROSS} No Whitelisted Users\n"
                "No users are currently in the whitelist."
            ))

        mentions = " ".join(f"<@{r[0]}>" for r in rows)
        await ctx.send(view=_layout(
            f"## {E.SHIELD} Whitelisted Users — {ctx.guild.name}\n\n{mentions}"
        ))

    # ================================================
    # /whitelistreset
    # ================================================
    @commands.hybrid_command(name='whitelistreset', aliases=['wlreset'])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def whitelistreset(self, ctx: commands.Context):
        """Reset all whitelisted users."""
        if not await self._has_perm(ctx) or not await self._antinuke_enabled(ctx):
            return

        rows = await db_fetch(
            "SELECT user_id FROM whitelisted_users WHERE guild_id=?",
            (ctx.guild.id,)
        )
        if not rows:
            return await ctx.send(view=_layout(
                f"## {E.CROSS} Nothing to Reset\n"
                "No whitelisted users found."
            ))

        # Loading
        msg = await ctx.send(view=_layout(
            f"## {E.LOADING} Resetting…\n"
            "Clearing all whitelisted users…"
        ))
        await asyncio.sleep(0.4)

        await db_exec(
            "DELETE FROM whitelisted_users WHERE guild_id=?",
            (ctx.guild.id,)
        )

        await msg.edit(view=_layout(
            f"## {E.TICK} Whitelist Reset\n\n"
            f"All whitelisted users removed from **{ctx.guild.name}**."
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Whitelist(bot))
