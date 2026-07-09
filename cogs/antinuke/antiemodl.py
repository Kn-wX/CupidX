"""
AntiEmojiDelete — Cypher Speed + GOD BASE
✦ Bans executor on mass, kicks on single
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiEmojiDelete(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after):
        if len(after) >= len(before):
            return
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.emoji_delete,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "mngstemo"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        action = self.ban_executor if mass else self.kick_executor
        await self.punish_and_notify(
            guild, executor, "Emoji Delete", f"{'Banned' if mass else 'Kicked'} executor",
            punishment_coro=action(guild, executor, reason=f"Anti-EmojiDelete | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user **deleted Emoji(s)**. Executor was {'**banned**' if mass else '**kicked**'}.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return


async def setup(bot):
    await bot.add_cog(AntiEmojiDelete(bot))
