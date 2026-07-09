import discord
from discord.ext import commands


class _antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def help_custom(self):
        emoji = '<:nextra_antinuke:1432211094214283356>'
        label = "Security Commands"
        description = "Show you Aura Of CupidX's Security Power 💥"
        return emoji, label, description

    @commands.group()
    async def __Antinuke__(self, ctx: commands.Context):
        """`antinuke`, `antinuke enable`, `antinuke disable`, `antinuke status`,
        `whitelist @user [perm]`, `unwhitelist @user`, `whitelisted`,
        `whitelist reset`, `extraowner set @user`, `extraowner view`,
        `extraowner remove @user`, `extraowner reset`"""


async def setup(bot):
    await bot.add_cog(_antinuke(bot))

