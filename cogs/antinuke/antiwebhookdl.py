"""
AntiWebhookDelete — Cypher Speed + GOD BASE
✦ Bans executor on unauthorized webhook deletion
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiWebhookDelete(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        guild = channel.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "webhook_delete", max_requests=6):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.webhook_delete,
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
            guild, executor, "Webhook Delete", "Banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-WebhookDelete | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            reason=f"Unwhitelisted user **deleted a Webhook**. Executor was **banned**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return


async def setup(bot):
    await bot.add_cog(AntiWebhookDelete(bot))
