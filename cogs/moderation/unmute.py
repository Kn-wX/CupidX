import discord
from discord.ext import commands
from discord import ui
from utils.ui_v2 import v2_card
from utils.Tools import *
from datetime import timedelta

class MuteUnmuteView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
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
            if item.label != "Delete":
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Add Timeout", style=discord.ButtonStyle.danger)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MuteReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

        
        for item in self.children:
            if item.label != "Delete":
                item.disabled = True
        await self.message.edit(view=self)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:delete:1327842168693461022>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class MuteReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Mute Information")
        self.user = user
        self.author = author
        self.view = view
        self.time_input = ui.TextInput(label="Duration (m/h/d)", placeholder="Leave blank for default 24h", required=False, max_length=5)
        self.reason_input = ui.TextInput(label="Reason", placeholder="Provide a reason or leave it blank.", required=False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.time_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        time_str = self.time_input.value or "24h"
        time_seconds = self.parse_duration(time_str)

        if time_seconds is None:
            await interaction.response.send_message(f"Invalid time format! Please provide in m (minutes), h (hours), or d (days).", ephemeral=True)
            return

        try:
            await self.user.edit(timed_out_until=discord.utils.utcnow() + timedelta(seconds=time_seconds))
        except discord.Forbidden:
            await interaction.response.send_message(f"Failed to mute {self.user.mention}. I lack the permissions.", ephemeral=True)
            return

        
        try:
            await self.user.send(f"<:icons_warning:1327829522573430864> You have been muted in **{interaction.guild.name}** for {time_str}. Reason: {reason}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        body = (
            f"**Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n"
            f"**User Mention:** {self.user.mention}\n"
            f"**Reason:** {reason}\n"
            f"**Duration:** {time_str}\n"
            f"**DM Sent:** {dm_status}\n\n"
            f"**Moderator:** {self.author.mention}"
        )
        view = v2_card(f"Muted {self.user.name}", body)

        await interaction.response.edit_message(view=view)

        for item in self.view.children:
            if item.label != "Delete":
                item.disabled = True
        await self.view.message.edit(view=self.view)

    def parse_duration(self, duration_str: str) -> int:
        try:
            if duration_str.endswith("m"):
                duration = int(duration_str[:-1])
                return duration * 60
            elif duration_str.endswith("h"):
                duration = int(duration_str[:-1])
                return duration * 3600
            elif duration_str.endswith("d"):
                duration = int(duration_str[:-1])
                return duration * 86400
            else:
                duration = int(duration_str)
                if duration > 60:
                    return (duration // 60) * 3600  
                else:
                    return duration * 60  
        except ValueError:
            return None


class Unmute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="unmute",
        help="Unmutes a user from the Server",
        usage="unmute <member>",
        aliases=["untimeout"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, user: discord.Member = commands.parameter(description="The member to unmute")):
        if not user.timed_out_until or user.timed_out_until <= discord.utils.utcnow():
            view = v2_card(f"{user.name} is Not Muted!", 
                           "**Requested User is not muted in this server.**\n\n"
                           "Click on the `Add Timeout` button to mute the mentioned user.")
            
            btn_view = MuteUnmuteView(user=user, author=ctx.author)
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message
            return

        try:
            await user.edit(timed_out_until=None)
            try:
                await user.send(f"<:tick:1327829594954530896> You have been unmuted in **{ctx.guild.name}**.")
                dm_status = "Yes"
            except:
                dm_status = "No"

        except discord.Forbidden:
            view = v2_card("Error ⚠️", "I can't unmute a user with higher permissions!")
            return await ctx.send(view=view)

        body = (
            f"**Target User:** [{user}](https://discord.com/users/{user.id})\n"
            f"**User Mention:** {user.mention}\n"
            f"**DM Sent:** {dm_status}\n\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        
        card_view = v2_card(f"Successfully Unmuted {user.name}", body)
        btn_view = MuteUnmuteView(user=user, author=ctx.author)
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message


"""
@Author: Sonu Jana
    + Discord: me.sonu
    + Community: https://discord.gg/odx (Olympus Development)
    + for any queries reach out Community or DM me.
"""