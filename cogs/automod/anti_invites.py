import discord
from discord.ext import commands
import re
from .base import AutomodBase


class AntiInvite(AutomodBase):
    EVENT_NAME = "Anti invites"
    LOG_TITLE = "Anti-Invite"

    def __init__(self, bot):
        super().__init__(bot)
        self.invite_pattern = re.compile(
            r'(https?://)?(www\.)?(discord\.gg|discordapp\.com/invite|discord\.com/invite)/\S+'
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        user = message.author
        guild_id = guild.id

        if user.id == guild.owner_id or user == self.bot.user:
            return

        match = self.invite_pattern.search(message.content)
        if not match:
            return

        # Check if the invite belongs to this guild before hitting DB
        invite_code = match.group(0).split("/")[-1]
        try:
            guild_invites = await guild.invites()
            if any(inv.code == invite_code for inv in guild_invites):
                return
        except Exception:
            pass

        config = await self.get_automod_config(guild_id, message.author.id)
        if config is None:
            return

        if message.channel.id in config["ignored_channels"]:
            return
        if any(role.id in config["ignored_roles"] for role in user.roles):
            return

        await self.apply_punishment(
            config, guild, user, message,
            reason="Posted an invite link",
            display_reason="posting an invite link",
            mute_minutes=12,
        )


async def setup(bot):
    await bot.add_cog(AntiInvite(bot))
