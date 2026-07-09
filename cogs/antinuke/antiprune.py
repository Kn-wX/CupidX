"""
AntiPrune — Cypher Speed + GOD BASE
✦ Instant ban on member prune
✦ Threat detection
"""
import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase


class AntiPrune(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.member_prune,
            max_age=30.0,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "prune"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Member Prune", "Banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-Prune | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user performed **Member Prune**. Executor was **banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
            asyncio.create_task(self.emergency_lockdown(guild, f"Mass prune by {executor}"))


async def setup(bot):
    await bot.add_cog(AntiPrune(bot))
