"""
AntiGuildUpdate — Cypher Speed + GOD BASE
✦ Instantly reverts guild settings (name, icon, banner, verification level etc.)
✦ Bans executor
✦ Threat detection
"""
import discord
from discord.ext import commands
from .base import AntinukeBase


class AntiGuildUpdate(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        guild = before
        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if not self.can_fetch_audit(guild.id, "guild_update"):
            return

        entry = await self.get_recent_audit_entry(
            guild, discord.AuditLogAction.guild_update,
        )
        if not entry:
            return

        executor = entry.user

        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        if executor.bot:
            return
        if await self.check_whitelist(guild.id, executor.id, "serverup"):
            return

        threat_count = self.record_threat(guild.id, executor.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, executor, "Guild Update", "Reverted guild settings & banned executor",
            punishment_coro=self.ban_executor(guild, executor, reason=f"Anti-GuildUpdate | {'MASS ATTACK' if mass else 'Unwhitelisted User'}"),
            extra_coros=[self._revert_guild(before, after)],
            reason=f"Unwhitelisted user modified **Guild Settings**. Executor was **banned** and settings were **reverted**.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, executor.id)
        return

    async def _revert_guild(self, before: discord.Guild, after: discord.Guild):
        try:
            kwargs = {}
            if before.name != after.name:
                kwargs["name"] = before.name
            if before.description != after.description:
                kwargs["description"] = before.description
            if before.verification_level != after.verification_level:
                kwargs["verification_level"] = before.verification_level
            if before.explicit_content_filter != after.explicit_content_filter:
                kwargs["explicit_content_filter"] = before.explicit_content_filter
            if before.default_notifications != after.default_notifications:
                kwargs["default_notifications"] = before.default_notifications
            if before.afk_channel != after.afk_channel:
                kwargs["afk_channel"] = before.afk_channel
            if before.afk_timeout != after.afk_timeout:
                kwargs["afk_timeout"] = before.afk_timeout
            if before.system_channel != after.system_channel:
                kwargs["system_channel"] = before.system_channel
            if before.rules_channel != after.rules_channel:
                kwargs["rules_channel"] = before.rules_channel
            if before.public_updates_channel != after.public_updates_channel:
                kwargs["public_updates_channel"] = before.public_updates_channel
            if before.icon != after.icon:
                kwargs["icon"] = await before.icon.read() if before.icon else None
            if before.banner != after.banner:
                kwargs["banner"] = await before.banner.read() if before.banner else None
            if before.splash != after.splash:
                kwargs["splash"] = await before.splash.read() if before.splash else None
            if kwargs:
                await after.edit(**kwargs, reason="Antinuke: Reverting guild update")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiGuildUpdate(bot))
