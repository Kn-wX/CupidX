"""
AntiMemberUpdate — Cypher Speed + GOD BASE
✦ Detects dangerous role assignment (admin, ban, manage_guild etc.)
✦ Reverts role + bans executor instantly
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase

_DANGEROUS_PERMS = (
    "administrator", "ban_members", "kick_members",
    "manage_guild", "manage_channels", "manage_roles",
    "manage_webhooks", "mention_everyone",
)


class AntiMemberUpdate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = before.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "member_update"):
            return

        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        dangerous_added = [r for r in added_roles if any(getattr(r.permissions, p, False) for p in _DANGEROUS_PERMS)]
        if not dangerous_added:
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.member_role_update,
            target_id=after.id,
        )
        if not entry:
            return

        executor = entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "memup"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Member Role Update (Dangerous Perms)", "Reverted role & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-MemberUpdate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[after.remove_roles(*dangerous_added, reason="Antinuke: Removing dangerous role assignment")],
            reason=f"Unwhitelisted user assigned **Dangerous Roles** to a member. Executor was **banned** and dangerous roles were removed.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)


async def setup(bot):
    await bot.add_cog(AntiMemberUpdate(bot))
