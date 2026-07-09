import discord
from discord.ext import commands
from core.Cog import Cog  # Use your framework's Cog base

class Latest(Cog, name="Latest"):
    def __init__(self, bot):
        self.bot = bot

    def help_custom(self):
        """Return fields for help menu"""
        return [
            ("🟢 Join2Create Commands", "`join2create setup`, `join2create disable`"),
            ("🤖 Chat AI Commands", "`chat <prompt>`")
        ]

    @commands.group()
    async def __Join2Create__(self, ctx: commands.Context):
        """Group for Join2Create commands"""
        pass

    @commands.group()
    async def __ChatAI__(self, ctx: commands.Context):
        """Group for Chat AI commands"""
        pass
