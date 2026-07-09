"""
AntiRoleCreate — Cypher Speed + GOD BASE
✦ Instantly deletes unauthorized role
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiRoleCreate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "role_create"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.role_create,
            target_id=role.id,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "rlcr"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Role Create", "Deleted role & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-RoleCreate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._delete_role(role)],
            reason=f"Unwhitelisted user created an **Unauthorized Role**. Executor was **banned** and role was **deleted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)

    async def _delete_role(self, role: discord.Role):
        try:
            await role.delete(reason="Antinuke: Deleting unauthorized role")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiRoleCreate(bot))
