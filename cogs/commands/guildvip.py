from __future__ import annotations

import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime

from utils.config import OWNER_IDS
from utils.detectfile import *
from core import Cog, cupidx

# ══════════════════════════════════════════════════════════════════
#  EMOJI CONFIG  (matches anti_wl.py / automod.py pattern)
# ══════════════════════════════════════════════════════════════════

class E:
    TICK    = EMOJI_TICK
    CROSS   = EMOJI_SWORD
    WARNING = EMOJI_WARN
    SHIELD  = EMOJI_SHIELD
    USER    = EMOJI_USER
    DOT     = EMOJI_DOT


# ══════════════════════════════════════════════════════════════════
#  DB HELPER
# ══════════════════════════════════════════════════════════════════

DB_PATH = "db/block.db"


async def ensure_vip_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_vip (
                guild_id   INTEGER PRIMARY KEY,
                added_by   INTEGER,
                timestamp  TEXT
            )
        """)
        await db.commit()


async def is_guild_vip(guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM guild_vip WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone() is not None


# ══════════════════════════════════════════════════════════════════
#  OWNER CHECK
# ══════════════════════════════════════════════════════════════════

async def _is_bot_owner(ctx: commands.Context) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if hasattr(ctx.cog, "owners") and ctx.author.id in ctx.cog.owners:
        return True
    return False


# ══════════════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════════════

class GuildVIP(Cog):
    """Marks guilds as VIP so they are never auto-blacklisted."""

    def __init__(self, client: cupidx):
        self.client = client
        self.client.loop.create_task(ensure_vip_table())

    # ── embed helper ─────────────────────────────────────────────

    @staticmethod
    def _embed(title: str, desc: str) -> discord.Embed:
        return discord.Embed(title=title, description=desc, color=0x000000)

    # ── group ────────────────────────────────────────────────────

    @commands.group(
        name="guildvip",
        invoke_without_command=True,
        hidden=True
    )
    @commands.check(_is_bot_owner)
    async def guildvip(self, ctx: commands.Context):
        """Guild VIP management — bot owner only."""
        p = ctx.prefix
        embed = self._embed(
            f"{E.SHIELD} Guild VIP Manager",
            (
                f"{E.DOT} `{p}guildvip add <guild_id>` — Add a guild to VIP\n"
                f"{E.DOT} `{p}guildvip remove <guild_id>` — Remove a guild from VIP\n"
                f"{E.DOT} `{p}guildvip show` — List all VIP guilds"
            )
        )
        await ctx.reply(embed=embed)

    # ── add ───────────────────────────────────────────────────────

    @guildvip.command(name="add")
    @commands.check(_is_bot_owner)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def vip_add(self, ctx: commands.Context, guild_id: int):
        """Add a guild to the VIP list."""
        if await is_guild_vip(guild_id):
            await ctx.reply(embed=self._embed(
                f"{E.WARNING} Already VIP",
                f"Guild `{guild_id}` is already on the VIP list."
            ))
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO guild_vip (guild_id, added_by, timestamp) VALUES (?, ?, ?)",
                (guild_id, ctx.author.id, datetime.utcnow().isoformat())
            )
            await db.commit()

        guild = self.client.get_guild(guild_id)
        name  = f"**{guild.name}**" if guild else f"`{guild_id}`"
        await ctx.reply(embed=self._embed(
            f"{E.TICK} Guild VIP Added",
            f"{name} has been added to the VIP list and will never be auto-blacklisted."
        ))

    # ── remove ────────────────────────────────────────────────────

    @guildvip.command(name="remove")
    @commands.check(_is_bot_owner)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def vip_remove(self, ctx: commands.Context, guild_id: int):
        """Remove a guild from the VIP list."""
        if not await is_guild_vip(guild_id):
            await ctx.reply(embed=self._embed(
                f"{E.CROSS} Not Found",
                f"Guild `{guild_id}` is not on the VIP list."
            ))
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM guild_vip WHERE guild_id = ?", (guild_id,))
            await db.commit()

        guild = self.client.get_guild(guild_id)
        name  = f"**{guild.name}**" if guild else f"`{guild_id}`"
        await ctx.reply(embed=self._embed(
            f"{E.TICK} Guild VIP Removed",
            f"{name} has been removed from the VIP list."
        ))

    # ── show ──────────────────────────────────────────────────────

    @guildvip.command(name="show")
    @commands.check(_is_bot_owner)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def vip_show(self, ctx: commands.Context):
        """Display all VIP guilds."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id, added_by, timestamp FROM guild_vip ORDER BY timestamp DESC"
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await ctx.reply(embed=self._embed(
                f"{E.SHIELD} VIP Guild List",
                "No VIP guilds have been added yet."
            ))
            return

        lines = []
        for guild_id, added_by, ts in rows:
            guild = self.client.get_guild(guild_id)
            name  = guild.name if guild else "Unknown"
            date  = ts[:10] if ts else "N/A"
            lines.append(
                f"{E.DOT} **{name}** (`{guild_id}`) — Added by <@{added_by}> • `{date}`"
            )

        embed = self._embed(
            f"{E.SHIELD} VIP Guild List [{len(rows)}]",
            "\n".join(lines)
        )
        await ctx.reply(embed=embed)

    # ── error handler ─────────────────────────────────────────────

    @guildvip.error
    @vip_add.error
    @vip_remove.error
    @vip_show.error
    async def vip_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CheckFailure):
            await ctx.reply(embed=self._embed(
                f"{E.CROSS} Access Denied",
                "This command is restricted to bot owners only."
            ))
        elif isinstance(error, commands.BadArgument):
            await ctx.reply(embed=self._embed(
                f"{E.CROSS} Invalid Argument",
                "Please provide a valid guild ID (numbers only)."
            ))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(embed=self._embed(
                f"{E.WARNING} Slow Down",
                f"Try again in `{error.retry_after:.1f}s`."
            ))


async def setup(client: cupidx):
    await client.add_cog(GuildVIP(client))
