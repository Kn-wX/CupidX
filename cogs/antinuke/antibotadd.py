"""
AntiBotAdd — Cypher Speed + GOD BASE
✦ Instantly kicks unauthorized bot
✦ Bans the inviter
✦ Threat detection
"""
import discord
from discord.ext import commands
import asyncio
from .base import AntinukeBase
from .antiban import _bot_inviters


class AntiBotAdd(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return

        guild = member.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "bot_add"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.bot_add,
            target_id=member.id,
        )
        if not entry:
            return

        executor = entry.user
        _bot_inviters.setdefault(guild.id, {})[member.id] = executor.id

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if await self.check_whitelist(guild.id, executor.id, "botadd"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        reason = "Antinuke: Unwhitelisted user added a bot"
        await self.punish_and_notify(
            guild, executor, "Bot Add", "Kicked bot & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-BotAdd | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[guild.ban(member, reason=reason)],
            reason=f"Unwhitelisted user added an **Unauthorized Bot**. Executor was **banned** and bot was **kicked**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)


async def setup(bot):
    await bot.add_cog(AntiBotAdd(bot))
