import discord

from discord.ext import commands

class _vanity(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Vanity Roles"""

    def help_custom(self):

              emoji = '<:nextra_vanity:1420278485024510025>'

              label = "Vanity"

              description = "Show you Commands of Vanity Roles"

              return emoji, label, description

    @commands.group()

    async def __Vanity__(self, ctx: commands.Context):

        """`vanityroles setup` - **Setups VanityRoles** ,
        `vanityroles reset` - **Resets The VanityRoles**,
        `vanityroles show`- **Shows The VanityRoles**,"""