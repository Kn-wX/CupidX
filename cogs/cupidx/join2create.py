import discord

from discord.ext import commands

class _join2create(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Join2Create commands"""

    def help_custom(self):

        emoji = ':champ_join_to_create:'

        label = "Join2Create Commands"

        description = "Show you Commands of Join2Create"

        return emoji, label, description

    @commands.group()

    async def __Join2Create__(self, ctx: commands.Context):

        """`join2create setup`, `join2create disable`"""