"""
AntiKick — Cypher Speed + GOD BASE
✦ Instant ban executor on kick
✦ Threat detection + mass attack
"""
import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase


class AntiKick(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "kick"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.kick,
            target_id=member.id,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "kick"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Member Kick", "Banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-Kick | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user performed **Member Kick**. Executor was **banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
            asyncio.create_task(self.emergency_lockdown(guild, f"Mass kick attack by {executor}"))


async def setup(bot):
    await bot.add_cog(AntiKick(bot))
