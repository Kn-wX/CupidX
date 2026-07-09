"""
AntiWebhookCreate — Cypher Speed + GOD BASE
✦ Instantly deletes unauthorized webhook
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiWebhookCreate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        guild = channel.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "webhook_create", max_requests=6):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.webhook_create,
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

        extra = None
        if entry.target and isinstance(entry.target, discord.Webhook):
            extra = [self._delete_webhook(entry.target)]

        await self.punish_and_notify(
            guild, executor, "Webhook Create", "Deleted webhook & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-WebhookCreate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=extra,
            reason=f"Unwhitelisted user **created an Unauthorized Webhook**. Executor was **banned** and webhook was deleted.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return

    async def _delete_webhook(self, webhook: discord.Webhook):
        try:
            await webhook.delete(reason="Antinuke: Webhook created by unwhitelisted user")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiWebhookCreate(bot))
