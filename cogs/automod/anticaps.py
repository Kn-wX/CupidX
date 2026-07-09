import discord
from discord.ext import commands
from .base import AutomodBase


class AntiCaps(AutomodBase):
    EVENT_NAME = "Anti caps"
    LOG_TITLE = "Anti-Caps"

    def __init__(self, bot):
        super().__init__(bot)
        self.caps_threshold = 70  # percent

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        content = message.content
        if not content:
            return

        caps_pct = sum(1 for c in content if c.isupper()) / len(content) * 100
        if caps_pct <= self.caps_threshold:
            return

        config = await self.get_automod_config(guild_id, message.author.id)
        if config is None:
            return

        if message.channel.id in config["ignored_channels"]:
            return
        if any(role.id in config["ignored_roles"] for role in user.roles):
            return

        await self.apply_punishment(
            config, guild, user, message,
            reason="Excessive Caps",
            display_reason="Excessive caps",
            mute_minutes=1,
        )


async def setup(bot):
    await bot.add_cog(AntiCaps(bot))
