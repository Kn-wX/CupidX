"""
AntiRoleDelete — Cypher Speed + GOD BASE
✦ Instantly recreates deleted role with full permissions
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiRoleDelete(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "role_delete"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.role_delete,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "rldl"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Role Delete", "Recreated role & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-RoleDelete | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._recreate_role(guild, role)],
            reason=f"Unwhitelisted user **deleted a Role**. Executor was **banned** and role was **recreated**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return

    async def _recreate_role(self, guild: discord.Guild, role: discord.Role):
        try:
            kwargs = dict(
                name=role.name,
                permissions=role.permissions,
                color=role.color,
                hoist=role.hoist,
                mentionable=role.mentionable,
                reason="Antinuke: Restoring deleted role",
            )
            if guild.premium_tier >= 2 and role.display_icon:
                try:
                    kwargs["display_icon"] = role.display_icon
                except Exception:
                    pass
            new_role = await guild.create_role(**kwargs)
            try:
                await new_role.edit(position=min(role.position, len(guild.roles) - 1))
            except Exception:
                pass
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiRoleDelete(bot))
