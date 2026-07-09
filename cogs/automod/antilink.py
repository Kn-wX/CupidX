import discord
from discord.ext import commands
import re
from .base import AutomodBase


class AntiLink(AutomodBase):
    EVENT_NAME = "Anti link"
    LOG_TITLE = "Anti-Link"

    def __init__(self, bot):
        super().__init__(bot)
        self.link_pattern = re.compile(r'http[s]?://\S+')
        self.invite_pattern = re.compile(r'(https?://)?(www\.)?(discord\.(gg|io|me|li)|discordapp\.com/invite)/\S+')
        self.gif_pattern = re.compile(r'(\.gif$|^https://(tenor\.com|giphy\.com/gifs|cdn\.discordapp\.com|media\.discordapp\.net))')
        self.spotify_pattern = re.compile(r'^https://open\.spotify\.com/track/\S+')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        if not self.link_pattern.search(message.content):
            return

        if (
            self.invite_pattern.search(message.content)
            or self.gif_pattern.search(message.content)
            or self.spotify_pattern.search(message.content)
        ):
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
            reason="Posted a link",
            display_reason="Posting a link",
            mute_minutes=7,
        )


async def setup(bot):
    await bot.add_cog(AntiLink(bot))
