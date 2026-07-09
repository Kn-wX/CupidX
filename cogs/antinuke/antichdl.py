"""
AntiChannelDelete — Cypher Speed + GOD BASE
✦ Instantly clones deleted channel back (Cypher style — no snapshot needed)
✦ Restores position exactly
✦ Bans executor
✦ Threat detection + mass attack
"""
import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase


class AntiChannelDelete(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "channel_delete"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.channel_delete,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "chdl"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Channel Delete", "Restored channel & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-ChannelDelete | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._restore_channel(channel)],
            reason=f"Unwhitelisted user **deleted a Channel**. Executor was **banned** and channel was **restored**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
            asyncio.create_task(self.emergency_lockdown(guild, f"Mass channel delete by {executor}"))
        return

    async def _restore_channel(self, channel: discord.abc.GuildChannel):
        try:
            cloned = await channel.clone(
                name=channel.name,
                reason="Antinuke: Restoring deleted channel"
            )
            if channel.category:
                try:
                    await cloned.edit(category=channel.category, reason="Antinuke: Restoring category")
                except Exception:
                    pass
            try:
                await cloned.edit(position=channel.position, reason="Antinuke: Restoring position")
            except Exception:
                pass
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiChannelDelete(bot))
