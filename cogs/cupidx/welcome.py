import discord
from discord.ext import commands


class _welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Welcome commands"""
  
    def help_custom(self):
		      emoji = '<:nextra_welcomers:1420275555542237254>'
		      label = "Welcomer Commands"
		      description = "Show you Aura Of Welcomer"
		      return emoji, label, description

    @commands.group()
    async def __Welcomer__(self, ctx: commands.Context):
        """ **Setups Greet** -`greet setup` ,
        **Resets Greet** - `greet reset`,
        **Sets The Greet Channel** - `greet channel` , 
        **Edits The Greet**- `greet edit` ,
        **Tests The Greet** -  `greet test` ,
        **The Config Of Your Greet**- `greet config` ,
        **Deletes The Greet Automatically**-`greet autodeletete` ,
        **Autoping Users When Joined**- `fastgreet_add` `fastgreet_list` `fastgreet_remove`"""