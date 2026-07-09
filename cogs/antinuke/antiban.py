"""
AntiBan + AntiUnban — Cypher Speed + GOD BASE
✦ Instant unban revert
✦ Instant ban executor
✦ Threat detection + mass attack
✦ No delays, no snapshots — pure speed
"""

import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase

# Track who invited which bot
_bot_inviters: dict[int, dict[int, int]] = {}


class AntiBan(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track bot inviters for commander-ban."""
        if not member.bot:
            return
        guild = member.guild
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=5):
                if entry.target and entry.target.id == member.id:
                    _bot_inviters.setdefault(guild.id, {})[member.id] = entry.user.id
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "member_ban"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.ban,
            target_id=user.id,
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

        extra = [self._revert_ban(guild, user)]
        if executor.bot:
            inviter_id = _bot_inviters.get(guild.id, {}).get(executor.id)
            if inviter_id and inviter_id not in {guild.owner_id, self.bot.user.id}:
                inviter = guild.get_member(inviter_id) or discord.Object(id=inviter_id)
                extra.append(self.ban_executor(
                    guild, inviter,
                    reason=f"Anti-Ban | Bot Commander (commanded {executor} to mass ban)"
                ))

        await self.punish_and_notify(
            guild, executor, "Member Ban", "Banned executor & reverted ban",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-Ban | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=extra,
            reason=f"Unwhitelisted user performed **Member Ban**. Executor was **banned** and original ban was **reverted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
            asyncio.create_task(self.emergency_lockdown(guild, f"Mass ban attack by {executor}"))

    async def _revert_ban(self, guild: discord.Guild, user: discord.User):
        try:
            await guild.unban(user, reason="Antinuke: Reverting ban by unwhitelisted user")
        except discord.NotFound:
            pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.unban,
            target_id=user.id,
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
            extra_coros=[guild.ban(user, reason="Antinuke: Re-banning after unauthorized unban")],
            reason=f"Unwhitelisted user performed unauthorized **Unban**. Executor was **banned** and the user was **re-banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)


async def setup(bot):
    await bot.add_cog(AntiBan(bot))
