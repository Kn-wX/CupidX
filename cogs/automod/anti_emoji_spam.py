import discord
from discord.ext import commands
import re
from .base import AutomodBase


class AntiEmojiSpam(AutomodBase):
    EVENT_NAME = "Anti emoji spam"
    LOG_TITLE = "Anti Emoji Spam"

    # Compiled once at class level — not per-message
    EMOJI_PATTERN = re.compile(
        r"<a?:[a-zA-Z0-9_]+:([0-9]+)>"
        r"|"
        r"([\U0001F600-\U0001F64F]"
        r"|[\U0001F300-\U0001F5FF]"
        r"|[\U0001F680-\U0001F6FF]"
        r"|[\U0001F700-\U0001F77F]"
        r"|[\U0001F780-\U0001F7FF]"
        r"|[\U0001F800-\U0001F8FF]"
        r"|[\U0001F900-\U0001F9FF]"
        r"|[\U0001FA00-\U0001FAFF]"
        r"|[\U00002700-\U000027BF]"
        r"|[\U0001F1E6-\U0001F1FF]"
        r"|[\U0001F004-\U0001F0CF]"
        r"|[\U0001F9B0-\U0001F9FF])"
    )

    def __init__(self, bot):
        super().__init__(bot)
        self.emoji_threshold = 5

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        emoji_count = len(self.EMOJI_PATTERN.findall(message.content))
        if emoji_count <= self.emoji_threshold:
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
            reason=f"Emoji Spam ({emoji_count} emojis)",
            display_reason="Spamming Emojis",
            mute_minutes=1,
        )


async def setup(bot):
    await bot.add_cog(AntiEmojiSpam(bot))
