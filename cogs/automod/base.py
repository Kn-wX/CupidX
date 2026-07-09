"""
AutomodBase — shared base class for all automod cogs.

Provides:
  - get_automod_config()  : single DB connection to fetch enabled status,
                             punishment, ignored channels, ignored roles,
                             and log channel — all in one shot.
  - apply_punishment()    : executes mute/kick/ban + deletes message + sends
                             alert embed + logs — with concurrent sends.
"""

import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import timedelta


class AutomodBase(commands.Cog):
    """
    Subclasses must set:
        EVENT_NAME  : str   — e.g. "Anti spam"  (matches automod_punishments.event)
        LOG_TITLE   : str   — embed title used in the log embed
    """

    EVENT_NAME: str = ""
    LOG_TITLE: str = "Automod"

    def __init__(self, bot):
        self.bot = bot

    # ── Antinuke Whitelist Check ───────────────────────────────────────────────

    async def is_antinuke_whitelisted(self, guild_id: int, user_id: int) -> bool:
        """
        Returns True if the user is whitelisted in the antinuke system (db/anti.db).
        Whitelisted users are fully exempt from all automod actions.
        """
        try:
            async with aiosqlite.connect("db/anti.db") as db:
                async with db.execute(
                    "SELECT user_id FROM whitelisted_users WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id),
                ) as cur:
                    return await cur.fetchone() is not None
        except Exception:
            return False

    # ── Config fetch (single DB open) ─────────────────────────────────────────

    async def get_automod_config(self, guild_id: int, user_id: int | None = None) -> dict | None:
        """
        Returns a dict with keys:
            enabled, punishment, ignored_channels (set), ignored_roles (set), log_channel_id
        Returns None if automod is disabled, event is not configured,
        or the user is antinuke-whitelisted.
        """
        # Antinuke WL check — if user is WL'd, skip all automod
        if user_id is not None and await self.is_antinuke_whitelisted(guild_id, user_id):
            return None

        async with aiosqlite.connect("db/automod.db") as db:
            # 1. Global enabled flag
            async with db.execute(
                "SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row or not row[0]:
                return None

            # 2. Event punishment
            async with db.execute(
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = ?",
                (guild_id, self.EVENT_NAME),
            ) as cur:
                punishment_row = await cur.fetchone()
            if not punishment_row:
                return None
            punishment = punishment_row[0]

            # 3. Ignored channels
            async with db.execute(
                "SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'channel'",
                (guild_id,),
            ) as cur:
                ignored_channels = {row[0] for row in await cur.fetchall()}

            # 4. Ignored roles
            async with db.execute(
                "SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'role'",
                (guild_id,),
            ) as cur:
                ignored_roles = {row[0] for row in await cur.fetchall()}

            # 5. Log channel
            async with db.execute(
                "SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild_id,)
            ) as cur:
                log_row = await cur.fetchone()
            log_channel_id = log_row[0] if log_row else None

        return {
            "punishment": punishment,
            "ignored_channels": ignored_channels,
            "ignored_roles": ignored_roles,
            "log_channel_id": log_channel_id,
        }

    # ── Punishment + notification ──────────────────────────────────────────────

    async def apply_punishment(
        self,
        config: dict,
        guild: discord.Guild,
        user: discord.Member,
        message: discord.Message,
        reason: str,
        display_reason: str,  # human-readable label shown in the embed
        mute_minutes: int = 10,
    ) -> None:
        """
        Applies the configured punishment, deletes the message,
        sends an alert embed, and logs — concurrently where possible.
        """
        punishment = config["punishment"]
        action_taken: str | None = None

        try:
            if punishment == "Mute":
                timeout_until = discord.utils.utcnow() + timedelta(minutes=mute_minutes)
                await user.edit(timed_out_until=timeout_until, reason=reason)
                action_taken = f"Muted for {mute_minutes} minutes"
            elif punishment == "Kick":
                await user.kick(reason=reason)
                action_taken = "Kicked"
            elif punishment == "Ban":
                await user.ban(reason=reason)
                action_taken = "Banned"

            if action_taken is None:
                return

            alert_embed = discord.Embed(title=f"Automod — {self.LOG_TITLE}", color=0xFF4444)
            alert_embed.description = (
                f"<:CupidXtick1:1474369967271968949> | {user.mention} has been "
                f"successfully **{action_taken}** for **{display_reason}.**"
            )
            alert_embed.set_footer(
                text='Use the "automod logging" command to get automod logs if it is not enabled.',
                icon_url=self.bot.user.avatar.url,
            )

            # Delete message + send alert concurrently
            await asyncio.gather(
                message.delete(),
                message.channel.send(embed=alert_embed, delete_after=30),
                return_exceptions=True,
            )

            # Log concurrently (fire-and-forget style via gather)
            await asyncio.gather(
                self._send_log(config, guild, user, message.channel, action_taken, reason),
                return_exceptions=True,
            )

        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass
        except Exception:
            pass

    async def _send_log(
        self,
        config: dict,
        guild: discord.Guild,
        user: discord.Member,
        channel: discord.TextChannel,
        action: str,
        reason: str,
    ) -> None:
        log_channel_id = config.get("log_channel_id")
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title=f"Automod Log: {self.LOG_TITLE}", color=0xFF4444)
        embed.add_field(name="User", value=user.mention, inline=False)
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Channel", value=channel.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        embed.set_thumbnail(url=avatar_url)
        embed.timestamp = discord.utils.utcnow()

        try:
            await log_channel.send(embed=embed)
        except Exception:
            pass
