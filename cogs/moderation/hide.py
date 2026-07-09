import discord
from discord.ext import commands
from discord import ui
from utils.ui_v2 import v2_card
from utils.detectfile import *

# ===============================
#          EMOJI CATEGORY
# ===============================
class Emojis:
    CHANNEL = EMOJI_CHANNEL
    TICK = "<:CupidXtick1:1474369967271968949>"
    COMMANDS = "<:CupidXCommands:1475152376737566722>"
    ADMIN = "<:CupidXautomod:1474356609122697382>"
    DELETE = "<:CupidXdelete:1474795676251459748>"


class HideUnhideView(ui.View):
    def __init__(self, channel, author, ctx):
        super().__init__(timeout=120)
        self.channel = channel
        self.author = author
        self.ctx = ctx
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You are not allowed to interact with this!",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Unhide", style=discord.ButtonStyle.success)
    async def unhide(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.channel.set_permissions(interaction.guild.default_role, read_messages=True)
        await interaction.response.send_message(
            f"{self.channel.mention} has been unhidden.",
            ephemeral=True
        )

        body = (
            f"{Emojis.CHANNEL} **Channel**: {self.channel.mention}\n"
            f"{Emojis.TICK} **Status**: Unhidden\n"
            f"{Emojis.COMMANDS} **Reason:** Unhide request\n\n"
            f"**{Emojis.ADMIN} Moderator:** {self.ctx.author.mention}"
        )
        view = v2_card(f"Successfully Unhidden {self.channel.name}", body)

        await self.message.edit(view=view)

        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class Hide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="hide",
        help="Hides a channel from the default role (@everyone).",
        usage="hide <channel>",
        aliases=["hidechannel"]
    )
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def hide_command(
        self,
        ctx,
        channel: discord.TextChannel = commands.parameter(
            description="The channel to hide",
            default=None
        )
    ):
        channel = channel or ctx.channel

        if not channel.permissions_for(ctx.guild.default_role).read_messages:
            view = v2_card(f"{channel.name} is Already Hidden", 
                           f"{Emojis.CHANNEL} **Channel**: {channel.mention}\n{Emojis.TICK} **Status**: Already Hidden")
            
            btn_view = HideUnhideView(channel=channel, author=ctx.author, ctx=ctx)
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message
            return

        await channel.set_permissions(ctx.guild.default_role, read_messages=False)

        body = (
            f"{Emojis.CHANNEL} **Channel**: {channel.mention}\n"
            f"{Emojis.TICK} **Status**: Hidden\n"
            f"{Emojis.COMMANDS} **Reason:** Hide request\n\n"
            f"**{Emojis.ADMIN} Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Hidden {channel.name}", body)
        btn_view = HideUnhideView(channel=channel, author=ctx.author, ctx=ctx)
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message


async def setup(bot):
    await bot.add_cog(Hide(bot))