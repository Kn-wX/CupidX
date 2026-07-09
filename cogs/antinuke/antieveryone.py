"""
AntiEveryone — Cypher Speed + GOD BASE
✦ Deletes @everyone/@here messages instantly
✦ Purges last 20 msgs from user in channel
✦ Timeout on single, ban on mass attack
✦ Threat detection
"""
import discord
from discord.ext import commands
from datetime import timedelta
from .base import AntinukeBase


class AntiEveryone(AntinukeBase):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or not message.mention_everyone:
            return

        guild = message.guild
        author = message.author

        if await self.is_blacklisted_guild(guild.id):
            return
        if not await self.is_antinuke_enabled(guild.id):
            return
        if author.id in {guild.owner_id, self.bot.user.id}:
            return
        if author.bot:
            return
        if await self.check_whitelist(guild.id, author.id, "meneve"):
            return

        threat_count = self.record_threat(guild.id, author.id)
        mass = threat_count >= 3

        await self.punish_and_notify(
            guild, author, "@everyone / @here Mention",
            f"{'Banned' if mass else '2hr Timeout'} & deleted messages",
            punishment_coro=self._punish(author, message.channel, mass),
            reason=f"Unwhitelisted user sent **@everyone / @here** mention. User was {'**banned**' if mass else '**muted for 2 hours**'} and messages were deleted.\nAttack type: {'🚨 Mass Attack' if mass else 'Single Event'}",
            is_mass_attack=mass,
        )

        if mass:
            self.clear_threat(guild.id, author.id)

    async def _punish(self, user: discord.Member, channel, mass: bool) -> bool:
        guild = user.guild
        punished = False

        if mass:
            punished = await self.ban_executor(guild, user, reason="Mass @everyone Spam | Unwhitelisted User")
        else:
            try:
                await user.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(hours=2),
                    reason="@everyone/@here Mention | Unwhitelisted User",
                )
                punished = True
            except Exception:
                pass

        try:
            def check(m):
                return m.author.id == user.id and m.mention_everyone

            await channel.purge(limit=20, check=check, reason="Antinuke: Removing @everyone spam")
        except Exception:
            pass

        return punished


async def setup(bot):
    await bot.add_cog(AntiEveryone(bot))
