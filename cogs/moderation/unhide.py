import discord
from discord.ext import commands
from discord import ui
from utils.ui_v2 import v2_card

class HideUnhideView(ui.View):
    def __init__(self, channel, author, ctx):
        super().__init__(timeout=120)
        self.channel = channel
        self.author = author
        self.ctx = ctx  
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
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

    @ui.button(label="Hide", style=discord.ButtonStyle.danger)
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.channel.set_permissions(interaction.guild.default_role, read_messages=False)
        await interaction.response.send_message(f"{self.channel.mention} has been hidden.", ephemeral=True)

        body = (
            f"**Channel**: {self.channel.mention}\n"
            f"**Status**: Hidden\n"
            f"**Reason:** Hide request\n\n"
            f"**Moderator:** {self.ctx.author.mention}"
        )
        view = v2_card(f"Successfully Hidden {self.channel.name}", body)

        await self.message.edit(view=view)

        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:delete:1327842168693461022>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class Unhide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="unhide",
        help="Unhides a channel to allow the default role (@everyone) to read messages.",
        usage="unhide <channel>",
        aliases=["unhidechannel"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unhide_command(self, ctx, channel: discord.TextChannel = commands.parameter(description="The channel to unhide", default=None)):
        channel = channel or ctx.channel 
        if channel.permissions_for(ctx.guild.default_role).read_messages:
            view = v2_card(f"{channel.name} is Already Unhidden", 
                           f"**Channel**: {channel.mention}\n**Status**: Already Unhidden")
            
            btn_view = HideUnhideView(channel=channel, author=ctx.author, ctx=ctx)  
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message
            return

        await channel.set_permissions(ctx.guild.default_role, read_messages=True)

        body = (
            f"**Channel**: {channel.mention}\n"
            f"**Status**: Unhidden\n"
            f"**Reason:** Unhide request\n\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Unhidden {channel.name}", body)
        btn_view = HideUnhideView(channel=channel, author=ctx.author, ctx=ctx)  
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message



"""
@Author: Sonu Jana
    + Discord: me.sonu
    + Community: https://discord.gg/odx (Olympus Development)
    + for any queries reach out Community or DM me.
"""