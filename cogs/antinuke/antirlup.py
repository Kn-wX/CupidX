"""
AntiRoleUpdate — Cypher Speed + GOD BASE
✦ Instantly reverts role to before state (name, perms, color, hoist, mentionable)
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiRoleUpdate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = before.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "role_update"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.role_update,
            target_id=before.id,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "rlup"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Role Update", "Reverted role & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-RoleUpdate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._revert_role(before, after)],
            reason=f"Unwhitelisted user **updated a Role**. Executor was **banned** and role permissions were **reverted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)

    async def _revert_role(self, before: discord.Role, after: discord.Role):
        try:
            await after.edit(
                name=before.name,
                permissions=before.permissions,
                color=before.color,
                hoist=before.hoist,
                mentionable=before.mentionable,
                reason="Antinuke: Reverting role update",
            )
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiRoleUpdate(bot))
