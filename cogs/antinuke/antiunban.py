"""
AntiUnban — Cypher Speed + GOD BASE
✦ Re-bans the unbanned user instantly
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiUnban(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.unban,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "ban"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Member Unban", "Re-banned user & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-Unban | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._reban(guild, user)],
            reason=f"Unwhitelisted user performed unauthorized **Unban**. Executor was **banned** and user was **re-banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return

    async def _reban(self, guild: discord.Guild, user: discord.User):
        try:
            await guild.ban(user, reason="Antinuke: Reverting unban by unwhitelisted user")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiUnban(bot))
