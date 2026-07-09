import discord
from discord.ext import commands
from discord import ui
from utils.ui_v2 import v2_card
from utils.Tools import *

# ===============================
#         EMOJI CATEGORY
# ===============================
class Emojis:
    DELETE = "<:CupidXdelete:1474795676251459748>"
    WARNING = "<:CupidXWarning:1474348304186867784>"
    TICK = "<:tick:1327829594954530896>"
    SUCCESS = "<:CupidXtick1:1474369967271968949>"

    TARGET = "<:CupidXuser:1475151935379341382>"
    MENTION = "<:CupidXmention:1476575411247906897>"
    DM = "<:CupidXMail:1475192722578215083>"
    REASON = "<:CupidXCommands:1475152376737566722>"


class BanView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class AlreadyUnbannedView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class ReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Ban Reason")
        self.user = user
        self.author = author
        self.view = view
        self.reason_input = ui.TextInput(label="Reason for Banning", required=False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"

        try:
            dm_embed = discord.Embed(
                description=f"{Emojis.WARNING} You have been Banned from **{self.author.guild.name}** by **{self.author}**\n\n{Emojis.REASON} **Reason:** {reason}",
                color=0x000000
            )
            await self.user.send(embed=dm_embed)
            dm_status = "Yes"
        except:
            dm_status = "No"

        body = (
            f"{Emojis.TARGET} **Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n"
            f"{Emojis.MENTION} **User Mention:** {self.user.mention}\n"
            f"{Emojis.DM} **DM Sent:** {dm_status}\n"
            f"{Emojis.REASON} **Reason:** {reason}\n\n"
            f"**Moderator:** {interaction.user.mention}"
        )
        view = v2_card(f"Successfully Banned {self.user.name}", body)

        try:
            await interaction.guild.ban(self.user, reason=f"Ban requested by {self.author}")
        except:
            pass

        await interaction.response.edit_message(view=view)
        for item in self.view.children:
            item.disabled = True
        await interaction.message.edit(view=self.view)


class Unban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(name="unban", help="Unbans a user from the Server", usage="unban <member>", aliases=["forgive", "pardon"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User = commands.parameter(description="The user to unban"), *, reason: str = commands.parameter(description="Reason for unban", default=None)):

        bans = [entry async for entry in ctx.guild.bans()]
        if not any(ban_entry.user.id == user.id for ban_entry in bans):
            view = v2_card(f"{user.name} is Not Banned!", 
                           f"**Requested User is not banned in this server.**\n\n"
                           f"Click on the `Ban` button to ban the mentioned user.")
            
            btn_view = AlreadyUnbannedView(user=user, author=ctx.author)
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message 
            return

        try:
            dm_embed = discord.Embed(
                description=f"{Emojis.TICK} You have been unbanned from **{ctx.guild.name}** by **{ctx.author}**\n\n{Emojis.REASON} **Reason:** {reason or 'No reason provided'}",
                color=self.color
            )
            await user.send(embed=dm_embed)
            dm_status = "Yes"
        except:
            dm_status = "No"

        await ctx.guild.unban(user, reason=f"Unban requested by {ctx.author}")

        body = (
            f"{Emojis.TARGET} **Target User:** [{user}](https://discord.com/users/{user.id})\n"
            f"{Emojis.MENTION} **User Mention:** {user.mention}\n"
            f"{Emojis.DM} **DM Sent:** {dm_status}\n"
            f"{Emojis.REASON} **Reason:** {reason or 'No reason provided'}\n\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Unbanned {user.name}", body)
        btn_view = BanView(user=user, author=ctx.author)
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message


async def setup(bot):
    await bot.add_cog(Unban(bot))