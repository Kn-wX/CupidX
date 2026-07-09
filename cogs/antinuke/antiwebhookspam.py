"""
AntiWebhookSpam — Cypher Speed + GOD BASE
✦ Tracks rapid webhook creation (spam window: 8s, threshold: 2)
✦ Nukes ALL guild webhooks on spam detection
✦ Bans executor
✦ Threat score integration
"""
import discord
from discord.ext import commands
import time
from .base import AntinukeBase

_webhook_create_times: dict[int, list[float]] = {}
SPAM_WINDOW = 8
SPAM_THRESHOLD = 2


class AntiWebhookSpam(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        guild = channel.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
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

        now = time.monotonic()
        times = _webhook_create_times.setdefault(guild.id, [])
        times.append(now)
        _webhook_create_times[guild.id] = [t for t in times if now - t <= SPAM_WINDOW]
        count = len(_webhook_create_times[guild.id])

        if count >= SPAM_THRESHOLD:
            _webhook_create_times[guild.id] = []
            self.record_threat(guild.id, executor.id)

            await self.punish_and_notify(
                guild, executor, "Webhook Spam Attack",
                f"Banned executor & deleted ALL {count}+ webhooks",
                punishment_coro=self.ban_executor(guild, executor, reason=f"Webhook Spam | {count} webhooks in {SPAM_WINDOW}s"),
                extra_coros=[self._nuke_all_webhooks(guild)],
                reason=f"Unwhitelisted user created **{count}+ webhooks in {SPAM_WINDOW}s** (Webhook Spam Attack). Executor was **banned** and ALL webhooks were deleted.\nAttack type: 🚨 Mass Attack",
                is_mass_attack=True,
            )

    async def _nuke_all_webhooks(self, guild: discord.Guild):
        import asyncio
        try:
            webhooks = await guild.webhooks()
        except Exception:
            return
        await asyncio.gather(
            *[self._safe_del(wh) for wh in webhooks],
            return_exceptions=True,
        )

    async def _safe_del(self, wh: discord.Webhook):
        try:
            await wh.delete(reason="Antinuke: Webhook spam — all webhooks purged")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiWebhookSpam(bot))
