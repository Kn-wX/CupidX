import discord
from discord.ext import commands
import asyncio
import aiosqlite
from utils.Tools import *

try:
    from utils.config import OWNERIDS
except ImportError:
    OWNERIDS = [1378341015181856768,1370740714165502022]

# ================================================
# EMOJI CONFIG
# ================================================

class E:
    TICK         = "✅"
    CROSS        = "❌"
    WARNING      = "⚠️"
    SETTINGS     = "⚙️"
    LOCK         = "🔒"
    UNLOCK       = "🔓"
    CROWN        = "👑"
    WRENCH       = "🔧"
    SHIELD       = "🛡️"
    INFO         = "ℹ️"
    LOADING      = "⏳"
    CLOCK        = "🕐"
    FIRE         = "🔥"

# ================================================
# OWNER IDS
# ================================================

OWNER_IDS: set[int] = set(int(i) for i in OWNERIDS if str(i).strip().isdigit() or isinstance(i, int))

# ================================================
# PREFIX HELPERS
# ================================================

PREFIX_DB   = "db/prefix.db"
NOPREFIX_DB = "db/np.db"

async def get_guild_prefix(guild_id: int) -> str:
    """Fetch guild prefix from db/prefix.db. Falls back to '!' if not set."""
    try:
        async with aiosqlite.connect(PREFIX_DB) as db:
            async with db.execute(
                "SELECT prefix FROM prefix WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return row[0]
    except Exception:
        pass
    return "!"

async def is_noprefix_user(user_id: int) -> bool:
    """Check if a user has no-prefix mode enabled via db/np.db."""
    try:
        async with aiosqlite.connect(NOPREFIX_DB) as db:
            async with db.execute(
                "SELECT 1 FROM noprefix WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                return row is not None
    except Exception:
        return False

# ================================================
# COMPONENTS V2 HELPERS
# ================================================

def _embed_to_container(embed: discord.Embed, controls=None) -> discord.ui.Container:
    items = []
    if embed.title:
        items.append(discord.ui.TextDisplay(f"## {embed.title}"))
    if embed.description:
        items.append(discord.ui.TextDisplay(embed.description))
    for field in embed.fields:
        items.append(discord.ui.TextDisplay(f"**{field.name}**\n{field.value}"))
    footer_text = getattr(getattr(embed, "footer", None), "text", None)
    if footer_text:
        items.append(discord.ui.TextDisplay(f"-# {footer_text}"))
    if controls:
        if items:
            items.append(discord.ui.Separator())
        for control in controls:
            items.append(control)
    return discord.ui.Container(*items)

def _embed_to_layout(embed: discord.Embed, controls=None, timeout: float = 60.0) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=timeout)
    view.add_item(_embed_to_container(embed, controls=controls))
    return view

def _text_to_layout(text: str, controls=None, timeout: float = 60.0) -> discord.ui.LayoutView:
    return _embed_to_layout(discord.Embed(description=text), controls=controls, timeout=timeout)

# ================================================
# MAINTENANCE STATE (in-memory)
# ================================================

_maintenance: dict = {
    "enabled": False,
    "reason":  "The bot is currently undergoing maintenance.",
}

# ================================================
# MAINTENANCE CHECK (global check)
# ================================================

async def maintenance_check(ctx: commands.Context) -> bool:
    """
    Global check injected into all commands.
    If maintenance is on and the invoker is NOT an owner, block the command.
    """
    if not _maintenance["enabled"]:
        return True
    if ctx.author.id in OWNER_IDS:
        return True
    return False

# ================================================
# CONFIRMATION VIEW (enable)
# ================================================

class ConfirmMaintenance(discord.ui.LayoutView):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=30)
        self.author = author
        self.value  = None

        self.yes_btn    = discord.ui.Button(label="Yes, Enable",  style=discord.ButtonStyle.danger,    emoji="🔒")
        self.cancel_btn = discord.ui.Button(label="Cancel",       style=discord.ButtonStyle.secondary, emoji="❌")

        async def yes_cb(interaction: discord.Interaction):
            self.value = True
            await interaction.response.defer()
            self.stop()

        async def cancel_cb(interaction: discord.Interaction):
            self.value = False
            await interaction.response.defer()
            self.stop()

        self.yes_btn.callback    = yes_cb
        self.cancel_btn.callback = cancel_cb

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("### ⚠️ Enable Maintenance Mode"),
            discord.ui.TextDisplay(
                "This will **block all commands** for non-owners.\n"
                "Only users listed in `OWNERIDS` (utils/config.py) will be able to use the bot."
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.yes_btn, self.cancel_btn),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} Only the command invoker can confirm this."),
                ephemeral=True
            )
            return False
        return True

# ================================================
# MANAGEMENT COG
# ================================================

class Management(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_check(maintenance_check)

    def cog_unload(self):
        self.bot.remove_check(maintenance_check)

    # ── OWNER GUARD ──────────────────────────────
    async def _owner_guard(self, ctx: commands.Context) -> bool:
        """Returns True if invoker is an owner, else sends an error and returns False."""
        if ctx.author.id not in OWNER_IDS:
            embed = discord.Embed(
                title=f"{E.CROWN} Owner Only",
                description=(
                    f"{E.CROSS} This command is restricted to **bot owners** only.\n\n"
                    f"Your ID (`{ctx.author.id}`) is not in the authorised owner list."
                ),
                color=0xFF4444
            )
            embed.set_footer(text=f"Requested by {ctx.author}")
            await ctx.send(view=_embed_to_layout(embed))
            return False
        return True

    # ── PREFIX HELPER ────────────────────────────
    async def _get_prefix(self, ctx: commands.Context) -> str:
        """Get the prefix for the current guild from db/prefix.db."""
        return await get_guild_prefix(ctx.guild.id) if ctx.guild else "!"

    # ── ERROR HANDLER ────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Intercepts CheckFailure caused by maintenance_check and sends
        a user-friendly maintenance message.
        """
        if isinstance(error, commands.CheckFailure) and _maintenance["enabled"]:
            if ctx.author.id not in OWNER_IDS:
                embed = discord.Embed(
                    title=f"{E.WRENCH} Bot Under Maintenance",
                    description=(
                        f"{E.LOCK} **All commands are temporarily disabled.**\n\n"
                        f"{E.INFO} **Reason:**\n{_maintenance['reason']}\n\n"
                        f"Please check back later. We're working hard to get things running again!"
                    ),
                    color=0xFEE75C
                )
                embed.set_footer(text="Maintenance Mode Active")
                try:
                    await ctx.send(view=_embed_to_layout(embed))
                except Exception:
                    pass
                return

    # ==============================================
    #        HYBRID GROUP — MAINTENANCE
    # ==============================================

    @commands.hybrid_group(name="maintenance", invoke_without_command=True, fallback="status")
    @commands.guild_only()
    async def maintenance(self, ctx: commands.Context):
        """Maintenance mode management. Shows current status."""
        if not await self._owner_guard(ctx):
            return

        prefix      = await self._get_prefix(ctx)
        status_text = f"{E.LOCK} **Enabled**" if _maintenance["enabled"] else f"{E.UNLOCK} **Disabled**"
        color       = 0xFEE75C if _maintenance["enabled"] else 0x57F287

        embed = discord.Embed(
            title=f"{E.SETTINGS} Maintenance Mode — Status",
            description=(
                f"**Current Status:** {status_text}\n\n"
                f"**Reason:** {_maintenance['reason']}\n\n"
                f"**Authorised Owners:** `{len(OWNER_IDS)} user(s)` loaded from `utils/config.py`\n"
                f"**Affected:** All non-owner users"
            ),
            color=color
        )
        embed.add_field(
            name=f"{E.WRENCH} Commands",
            value=(
                f"`{prefix}maintenance enable [reason]` — Enable maintenance\n"
                f"`{prefix}maintenance disable` — Disable maintenance\n"
                f"`{prefix}maintenance status` — Show this status"
            ),
            inline=False
        )
        embed.set_footer(text=f"Owner IDs loaded from utils/config.py OWNERIDS  •  Requested by {ctx.author}")
        await ctx.send(view=_embed_to_layout(embed))

    # ── ENABLE ────────────────────────────────────
    @maintenance.command(name="enable", help="Enable maintenance mode. Optional: provide a reason.")
    @commands.guild_only()
    async def maintenance_enable(self, ctx: commands.Context, *, reason: str = None):
        """
        Enable maintenance mode globally.
        Usage: !maintenance enable [reason]
        """
        if not await self._owner_guard(ctx):
            return

        prefix = await self._get_prefix(ctx)

        if _maintenance["enabled"]:
            embed = discord.Embed(
                title=f"{E.WARNING} Already Enabled",
                description=(
                    f"Maintenance mode is **already active**.\n\n"
                    f"**Current reason:** {_maintenance['reason']}\n\n"
                    f"Use `{prefix}maintenance disable` to turn it off."
                ),
                color=0xFEE75C
            )
            embed.set_footer(text=f"Requested by {ctx.author}")
            return await ctx.send(view=_embed_to_layout(embed))

        view = ConfirmMaintenance(ctx.author)
        msg  = await ctx.send(view=view)
        await view.wait()

        if view.value is None:
            timeout_embed = discord.Embed(
                title=f"{E.CLOCK} Timed Out",
                description="No response received. Maintenance enable cancelled.",
                color=0xFEE75C
            )
            return await msg.edit(view=_embed_to_layout(timeout_embed))

        if not view.value:
            cancel_embed = discord.Embed(
                title=f"{E.CROSS} Cancelled",
                description="Maintenance mode enable was cancelled.",
                color=0xED4245
            )
            return await msg.edit(view=_embed_to_layout(cancel_embed))

        _maintenance["enabled"] = True
        _maintenance["reason"]  = reason or "The bot is currently undergoing maintenance. Please check back soon."

        embed = discord.Embed(
            title=f"{E.LOCK} Maintenance Mode Enabled",
            description=(
                f"{E.FIRE} **Maintenance mode is now ACTIVE.**\n\n"
                f"{E.INFO} **Reason:**\n{_maintenance['reason']}\n\n"
                f"{E.CROWN} **Owners bypass:** `{len(OWNER_IDS)} user(s)` can still use all commands.\n"
                f"{E.CROSS} **All other users** will see a maintenance message when using any command.\n\n"
                f"Run `{prefix}maintenance disable` when you're done."
            ),
            color=0xFEE75C
        )
        embed.set_footer(text=f"Enabled by {ctx.author}  •  All non-owner commands are blocked")
        await msg.edit(view=_embed_to_layout(embed))
        print(f"[Management] Maintenance ENABLED by {ctx.author} ({ctx.author.id}). Reason: {_maintenance['reason']}")

    # ── DISABLE ───────────────────────────────────
    @maintenance.command(name="disable", help="Disable maintenance mode and restore all commands.")
    @commands.guild_only()
    async def maintenance_disable(self, ctx: commands.Context):
        """
        Disable maintenance mode globally.
        Usage: !maintenance disable
        """
        if not await self._owner_guard(ctx):
            return

        prefix = await self._get_prefix(ctx)

        if not _maintenance["enabled"]:
            embed = discord.Embed(
                title=f"{E.INFO} Not Active",
                description=(
                    f"Maintenance mode is **not currently enabled**.\n\n"
                    f"Use `{prefix}maintenance enable` to activate it."
                ),
                color=0x5865F2
            )
            embed.set_footer(text=f"Requested by {ctx.author}")
            return await ctx.send(view=_embed_to_layout(embed))

        loading = discord.Embed(
            title=f"{E.LOADING} Disabling Maintenance...",
            description="Restoring all bot commands...",
            color=0x5865F2
        )
        msg = await ctx.send(view=_embed_to_layout(loading))
        await asyncio.sleep(1)

        _maintenance["enabled"] = False
        _maintenance["reason"]  = "The bot is currently undergoing maintenance."

        embed = discord.Embed(
            title=f"{E.UNLOCK} Maintenance Mode Disabled",
            description=(
                f"{E.TICK} **Maintenance mode is now OFF.**\n\n"
                f"All users can use bot commands again normally.\n\n"
                f"{E.FIRE} The bot is back online and fully operational!"
            ),
            color=0x57F287
        )
        embed.set_footer(text=f"Disabled by {ctx.author}  •  All commands restored")
        await msg.edit(view=_embed_to_layout(embed))
        print(f"[Management] Maintenance DISABLED by {ctx.author} ({ctx.author.id}).")


async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))
