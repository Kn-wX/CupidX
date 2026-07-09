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
    ENABLED  = EMOJI_ENABLE
    DISABLED = EMOJI_DISABLE
    LOADING  = EMOJI_PIN
    TICK     = EMOJI_TICK
    CROSS    = EMOJI_SWORD
    WARNING  = EMOJI_WARN
    SHIELD   = EMOJI_SHIELD
    DOT      = EMOJI_DOT

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
# V2 LAYOUT HELPER  (automod style)
# ================================================

def _layout(text: str, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=timeout)
    items = [discord.ui.TextDisplay(text)]
    if controls:
        items.append(discord.ui.Separator())
        for ctrl in controls:
            items.append(ctrl)
    view.add_item(discord.ui.Container(*items))
    return view

# ================================================
# CONFIRM UNWHITELIST VIEW  (automod ConfirmDisable style)
# ================================================

class ConfirmUnwhitelistView(discord.ui.LayoutView):
    """
    Two black/white secondary buttons — Confirm & Cancel.
    Identical pattern to automod's ConfirmDisable.
    """

    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=30)
        self.author  = author
        self.target  = target
        self.value   = None   # True = confirmed, False = cancelled
        self.done    = False

        self.confirm_btn = discord.ui.Button(
            label="Yes, Unwhitelist",
            style=discord.ButtonStyle.secondary,
            emoji=E.TICK
        )
        self.cancel_btn = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            emoji=E.CROSS
        )

        async def confirm_cb(interaction: discord.Interaction):
            self.value = True
            await interaction.response.defer()
            self.stop()

        async def cancel_cb(interaction: discord.Interaction):
            self.value = False
            await interaction.response.defer()
            self.stop()

        self.confirm_btn.callback = confirm_cb
        self.cancel_btn.callback  = cancel_cb

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {E.WARNING} Confirm Unwhitelist\n\n"
                f"**Target:** <@{self.target.id}>\n\n"
                "Are you sure? Antinuke will take action against this user if triggered."
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.confirm_btn, self.cancel_btn),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_layout(f"{E.CROSS} This isn't your session!"),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if not self.done:
            self._children.clear()
            self.add_item(discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {E.WARNING} Session Expired\n"
                    "Unwhitelist confirmation timed out."
                )
            ))

# ================================================
# UNWHITELIST COG
# ================================================

class Unwhitelist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self._init_db())

    async def _init_db(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id  INTEGER,
                    user_id   INTEGER,
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
            (ctx.guild.id, ctx.author.id), one=True
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
    # /unwhitelist
    # ================================================
    @commands.hybrid_command(name='unwhitelist', aliases=['unwl'])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def unwhitelist(self, ctx: commands.Context, member: discord.Member = None):
        """Remove a user from the antinuke whitelist."""

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
                f"## {E.SHIELD} Unwhitelist — Usage\n\n"
                "Removes a user from the whitelist.\n"
                "Antinuke will take action on them if triggered.\n\n"
                f"{E.DOT} `{ctx.prefix}unwhitelist @user`\n"
                f"{E.DOT} `{ctx.prefix}unwl @user`"
            ))

        # Check if user is actually whitelisted
        row = await db_fetch(
            "SELECT user_id FROM whitelisted_users WHERE guild_id=? AND user_id=?",
            (ctx.guild.id, member.id), one=True
        )
        if not row:
            return await ctx.send(view=_layout(
                f"## {E.CROSS} Not Whitelisted\n\n"
                f"<@{member.id}> is **not** in the whitelist."
            ))

        # Show confirm view
        confirm_view = ConfirmUnwhitelistView(ctx.author, member)
        msg = await ctx.send(view=confirm_view)
        await confirm_view.wait()

        # Cancelled or timed out
        if not confirm_view.value:
            confirm_view.done = True
            await msg.edit(view=_layout(
                f"## {E.CROSS} Cancelled\n"
                "Unwhitelist action was cancelled."
            ))
            return

        # Loading
        confirm_view.done = True
        await msg.edit(view=_layout(
            f"## {E.LOADING} Processing…\n"
            f"Removing <@{member.id}> from whitelist…"
        ))
        await asyncio.sleep(0.4)

        # Delete from DB
        await db_exec(
            "DELETE FROM whitelisted_users WHERE guild_id=? AND user_id=?",
            (ctx.guild.id, member.id)
        )

        await msg.edit(view=_layout(
            f"## {E.TICK} Unwhitelisted Successfully\n\n"
            f"**Server:** {ctx.guild.name}\n"
            f"**Executor:** <@{ctx.author.id}>\n"
            f"**Target:** <@{member.id}>\n\n"
            "Antinuke will now take action if this user triggers it."
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Unwhitelist(bot))
