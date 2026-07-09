"""
AntiChannelCreate — Cypher Speed + GOD BASE
✦ Instantly deletes attacker-created channel
✦ Bans executor immediately
✦ Threat detection + mass attack lockdown
"""
import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase


class AntiChannelCreate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "channel_create"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.channel_create,
            target_id=channel.id,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "chcr"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Channel Create", "Deleted channel & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-ChannelCreate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._delete_channel(channel)],
            reason=f"Unwhitelisted user created an **Unauthorized Channel**. Executor was **banned** and channel was **deleted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
            asyncio.create_task(self.emergency_lockdown(guild, f"Mass channel create by {executor}"))
        return

    async def _delete_channel(self, channel: discord.abc.GuildChannel):
        try:
            await channel.delete(reason="Antinuke: Deleting unauthorized channel")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiChannelCreate(bot))
