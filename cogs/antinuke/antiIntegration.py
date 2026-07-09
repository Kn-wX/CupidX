"""
AntiIntegration — Cypher Speed + GOD BASE
✦ Blocks unauthorized integration (OAuth bot) additions
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiIntegration(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild):
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "integration_create", max_requests=6):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.integration_create,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "mngweb"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Integration Create", "Banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-Integration | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user added an **Unauthorized Integration**. Executor was **banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)


async def setup(bot):
    await bot.add_cog(AntiIntegration(bot))
