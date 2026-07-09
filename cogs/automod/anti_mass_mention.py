import discord
from discord.ext import commands
from .base import AutomodBase


class AntiMassMention(AutomodBase):
    EVENT_NAME = "Anti mass mention"
    LOG_TITLE = "Anti Mass-Mention"

    def __init__(self, bot):
        super().__init__(bot)
        self.mass_mention_threshold = 5

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        mention_count = message.content.count("<@")
        if mention_count < self.mass_mention_threshold:
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
            reason=f"Mass Mention ({mention_count} mentions)",
            display_reason="mass mentioning",
            mute_minutes=3,
        )


async def setup(bot):
    await bot.add_cog(AntiMassMention(bot))
