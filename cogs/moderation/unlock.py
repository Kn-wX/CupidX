import discord
from discord.ext import commands
from discord import ui
from utils.ui_v2 import v2_card

class LockUnlockView(ui.View):
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
            

    @ui.button(label="Lock", style=discord.ButtonStyle.danger)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        overwrite = self.channel.overwrites_for(interaction.guild.default_role)

        overwrite.send_messages = False
        overwrite.view_channel = True

        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(f"{self.channel.mention} has been locked.", ephemeral=True)

        body = (
            f"**Channel**: {self.channel.mention}\n"
            f"**Status**: Locked\n"
            f"**Reason:** Lock request\n\n"
            f"**Moderator:** {self.ctx.author.mention}"
        )
        view = v2_card(f"Successfully Locked {self.channel.name}", body)

        await self.message.edit(view=view)

        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:delete:1327842168693461022>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class Unlock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="unlock",
        help="Unlocks a channel to allow sending messages.",
        usage="unlock <channel>",
        aliases=["unlockchannel"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unlock_command(self, ctx, channel: discord.TextChannel = commands.parameter(description="The channel to unlock", default=None)):
        channel = channel or ctx.channel 
        if channel.permissions_for(ctx.guild.default_role).send_messages is True:
            view = v2_card(f"{channel.name} is Already Unlocked", 
                           f"**Channel**: {channel.mention}\n**Status**: Already Unlocked")
            
            btn_view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
            message = await ctx.send(view=view)
            await ctx.send(view=btn_view)
            btn_view.message = message
            return

        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        overwrite.view_channel = True  

        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

        body = (
            f"**Channel**: {channel.mention}\n"
            f"**Status**: Unlocked\n"
            f"**Reason:** Unlock request\n\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Unlocked {channel.name}", body)
        btn_view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message