import discord

from discord.ext import commands

class _inviteTracker(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Invite Tracker"""

    def help_custom(self):

              emoji = '<:invite:1426801992747188224>'

              label = "Invite Tracker"

              description = "Show you Commands of Invite Tracker"

              return emoji, label, description

    @commands.group()

    async def __InviteTracker__(self, ctx: commands.Context):

        """ 
`>Inviteenable` , `>Invitedisable `, `>invites` , `>resetinvites` , `>addinvites` , `>removeinvites` , `>resetserverinvites`, `>inviteleaderboard` """