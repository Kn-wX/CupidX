"""
AntiSticker — Cypher Speed + GOD BASE
✦ Detects create/delete/update of stickers
✦ Bans executor on mass, kicks on single
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiSticker(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before, after):
        if len(after) > len(before):
            action = discord.AuditLogAction.sticker_create
            event = "Sticker Create"
        elif len(after) < len(before):
            action = discord.AuditLogAction.sticker_delete
            event = "Sticker Delete"
        else:
            action = discord.AuditLogAction.sticker_update
            event = "Sticker Update"

        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return

        entry = await self.get_recent_audit_entry(guild, action)
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

        action_fn = self.ban_executor if mass else self.kick_executor
        await self.punish_and_notify(
            guild, executor, event, f"{'Banned' if mass else 'Kicked'} executor",
            punishment_coro=action_fn(guild, executor, reason=f"{event} | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user performed **{event}**. Executor was {'**banned**' if mass else '**kicked**'}.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)


async def setup(bot):
    await bot.add_cog(AntiSticker(bot))
