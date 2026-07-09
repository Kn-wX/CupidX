"""
AntiChannelUpdate — Cypher Speed + GOD BASE
✦ Instantly reverts channel to before state
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiChannelUpdate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild = before.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "channel_update"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.channel_update,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "chup"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Channel Update", "Reverted channel & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-ChannelUpdate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._revert_channel(before, after)],
            reason=f"Unwhitelisted user **updated a Channel**. Executor was **banned** and channel settings were **reverted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return

    async def _revert_channel(self, before, after):
        try:
            kwargs = {
                "name": before.name,
                "overwrites": before.overwrites,
                "reason": "Antinuke: Reverting channel update"
            }
            if hasattr(before, "topic"):
                kwargs["topic"] = before.topic
            if hasattr(before, "nsfw"):
                kwargs["nsfw"] = before.nsfw
            if hasattr(before, "slowmode_delay"):
                kwargs["slowmode_delay"] = before.slowmode_delay
            if hasattr(before, "bitrate"):
                kwargs["bitrate"] = before.bitrate
            if hasattr(before, "user_limit"):
                kwargs["user_limit"] = before.user_limit
            await after.edit(**kwargs)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiChannelUpdate(bot))
