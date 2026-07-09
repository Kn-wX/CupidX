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
    STAFF = "<a:CupidXping:1474771697289924721>"
    DELETE = "<:CupidXdelete:1474795676251459748>"


# ===============================
#        LOCK / UNLOCK VIEW
# ===============================
class LockUnlockView(ui.View):
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
            except:
                pass

    # ===============================
    #            UNLOCK
    # ===============================
    @ui.button(label="Unlock", style=discord.ButtonStyle.success)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):

        overwrite = self.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None  # RESET instead of forcing True
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        await interaction.response.send_message(
            f"{self.channel.mention} has been unlocked.",
            ephemeral=True
        )

        body = (
            f"{Emojis.CHANNEL} **Channel**: {self.channel.mention}\n"
            f"{Emojis.TICK} **Status**: Unlocked"
        )
        view = v2_card(f"Successfully Unlocked {self.channel.name}", body)

        await self.message.edit(view=view)

        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    # ===============================
    #            DELETE
    # ===============================
    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


# ===============================
#               COG
# ===============================
class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color(0x000000)

    @commands.hybrid_command(
        name="lock",
        help="Locks a channel safely.",
        aliases=["lockchannel"]
    )
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def lock_command(
        self,
        ctx,
        channel: discord.TextChannel = None
    ):
        channel = channel or ctx.channel

        # Check already locked
        perms = channel.permissions_for(ctx.guild.default_role)

        if perms.send_messages is False:
            view = v2_card(f"{channel.name} is Already Locked", 
                           f"{Emojis.CHANNEL} **Channel**: {channel.mention}\n{Emojis.TICK} **Status**: Already Locked")
            
            btn_view = LockUnlockView(channel, ctx.author, ctx)
            message = await ctx.send(view=view)
            await ctx.send(view=btn_view)
            btn_view.message = message
            return

        # SAFE LOCK SYSTEM
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

        body = (
            f"{Emojis.CHANNEL} **Channel**: {channel.mention}\n"
            f"{Emojis.TICK} **Status**: Locked\n\n"
            f"**{Emojis.ADMIN} Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Locked {channel.name}", body)
        btn_view = LockUnlockView(channel, ctx.author, ctx)
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message


async def setup(bot):
    await bot.add_cog(Lock(bot))