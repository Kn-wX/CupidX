import discord
from discord.ext import commands
from .base import AutomodBase


class AntiSpam(AutomodBase):
    EVENT_NAME = "Anti spam"
    LOG_TITLE = "Anti-Spam"

    def __init__(self, bot):
        super().__init__(bot)
        self.spam_threshold = 5
        self.recent_messages: dict = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        config = await self.get_automod_config(guild_id, message.author.id)
        if config is None:
            return

        if message.channel.id in config["ignored_channels"]:
            return
        if any(role.id in config["ignored_roles"] for role in user.roles):
            return

        current_time = message.created_at.timestamp()
        user_messages = self.recent_messages.get(user.id, [])
        user_messages = [t for t in user_messages if current_time - t < 10]
        user_messages.append(current_time)
        self.recent_messages[user.id] = user_messages

        if len(user_messages) > self.spam_threshold:
            mute_minutes = 12
            await self.apply_punishment(
                config, guild, user, message,
                reason="Spamming",
                display_reason="Spamming",
                mute_minutes=mute_minutes,
            )


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
