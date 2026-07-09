import discord
from discord.ext import commands
from discord import ui
from datetime import timedelta
import re
from utils.Tools import *
from utils.ui_v2 import v2_card

# ===============================
#         EMOJI CATEGORY
# ===============================
class Emojis:
    DELETE = "<:CupidXdelete:1474795676251459748>"
    WARNING = "<:CupidXWarning:1474348304186867784>"
    CROSS = "<:CupidXCross:1473996646873436336>"
    CHECK = "<:CupidXtick:1473996329125675105>"
    QUESTION = "<:CupidXQuestion:1474795676251459750>"

    TARGET = "<:CupidXuser:1475151935379341382>"
    MENTION = "<:CupidXmention:1476575411247906897>"
    DM = "<:CupidXMail:1475192722578215083>"
    REASON = "<:CupidXCommands:1475152376737566722>"
    DURATION = "<a:CupidXtimer:1475327919558496370>"

# ===============================
#      CONFIRMATION VIEW
# ===============================
class ConfirmMuteView(ui.View):
    def __init__(self, user, author, time_delta, duration_text, reason, guild_name):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.time_delta = time_delta
        self.duration_text = duration_text
        self.reason = reason
        self.guild_name = guild_name  # <-- guild name pass karo DM ke liye
        self.confirmed = False
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
            try:
                timeout_embed = discord.Embed(
                    title=f"{Emojis.WARNING} Confirmation Timed Out",
                    description="The mute action has been cancelled due to inactivity.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=timeout_embed, view=self)
            except:
                pass

    @ui.button(label="✅ Confirm Mute", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        for item in self.children:
            item.disabled = True

        await interaction.response.defer()

        # ===== MUTE APPLY =====
        try:
            await self.user.edit(
                timed_out_until=discord.utils.utcnow() + self.time_delta,
                reason=f"Muted by {self.author} for {self.duration_text}. Reason: {self.reason or 'None'}"
            )
            mute_success = True
        except Exception:
            mute_success = False

        # ===== DM SEND KARO MUTE HONE KE BAAD =====
        dm_status = "No"
        if mute_success:
            try:
                dm_embed = discord.Embed(
                    description=(
                        f"{Emojis.WARNING} You have been **muted** in **{self.guild_name}** by **{self.author}**\n\n"
                        f"{Emojis.DURATION} **Duration:** {self.duration_text}\n"
                        f"{Emojis.REASON} **Reason:** {self.reason or 'None'}"
                    ),
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await self.user.send(embed=dm_embed)
                dm_status = "Yes"
            except Exception:
                dm_status = "No"

        # ===== SUCCESS EMBED =====
        if mute_success:
            embed = discord.Embed(
                title=f"{Emojis.CHECK} Successfully Muted",
                description=(
                    f"{Emojis.TARGET} **Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n"
                    f"{Emojis.MENTION} **User Mention:** {self.user.mention}\n"
                    f"{Emojis.DM} **DM Sent:** {dm_status}\n"
                    f"{Emojis.REASON} **Reason:** {self.reason or 'None'}\n"
                    f"{Emojis.DURATION} **Duration:** {self.duration_text}\n\n"
                    f"**Moderator:** {self.author.mention}"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title=f"{Emojis.CROSS} Mute Failed",
                description="An error occurred while trying to mute the user. Please check my permissions.",
                color=discord.Color.red()
            )

        await interaction.message.edit(embed=embed, view=self)
        self.confirmed = True
        self.stop()

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        
        for item in self.children:
            item.disabled = True
            
        cancel_embed = discord.Embed(
            title=f"{Emojis.CROSS} Cancelled",
            description=f"Mute action for {self.user.mention} has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=cancel_embed, view=self)

# ===============================
#      TIMEOUT VIEW (After Mute)
# ===============================
class TimeoutView(ui.View):
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
            except:
                pass

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

# ===============================
#      ALREADY TIMEOUT VIEW
# ===============================
class AlreadyTimedoutView(ui.View):
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
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

# ===============================
#      UNMUTE REASON MODAL
# ===============================
class ReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Unmute Reason")
        self.user = user
        self.author = author
        self.view = view
        self.reason_input = ui.TextInput(
            label="Reason for Unmuting", 
            placeholder="Provide a reason to unmute or leave it blank.", 
            required=False, 
            max_length=2000, 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            dm_embed = discord.Embed(
                description=f"{Emojis.WARNING} You have been Unmuted in **{self.author.guild.name}** by **{self.author}**\n\n{Emojis.REASON} **Reason:** {reason}",
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
        
        card_view = v2_card(f"Successfully Unmuted {self.user.name}", body)

        await self.user.edit(timed_out_until=None, reason=f"Unmute requested by {self.author}")
        
        for item in self.view.children:
            item.disabled = True
        
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(view=card_view)

# ===============================
#      MAIN MUTE COG
# ===============================
class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    def parse_time(self, time_str):
        time_pattern = r"(\d+)([mhd])"
        match = re.match(time_pattern, time_str)
        if match:
            time_value = int(match.group(1))
            time_unit = match.group(2)
            if time_unit == 'm' and 0 < time_value <= 60:
                return timedelta(minutes=time_value), f"{time_value} minutes"
            elif time_unit == 'h' and 0 < time_value <= 24:
                return timedelta(hours=time_value), f"{time_value} hours"
            elif time_unit == 'd' and 0 < time_value <= 28:
                return timedelta(days=time_value), f"{time_value} days"
        return None, None

    @commands.hybrid_command(
        name="mute", 
        help="Mutes a user with optional time and reason", 
        usage="mute <member> [time] [reason]", 
        aliases=["timeout", "stfu"]
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(
        self, 
        ctx, 
        user: discord.Member = commands.parameter(description="The member to mute"), 
        time: str = commands.parameter(description="Duration (e.g. 10m, 1h)", default=None), 
        *, 
        reason: str = commands.parameter(description="Reason for the mute", default=None)
    ):
        # Check if user is already muted
        if user.is_timed_out():
            view = v2_card(
                f"{user.name} is Already Timed Out!", 
                f"**Requested User is already muted in this server.**\n\nClick on the `Unmute` button below to remove the timeout."
            )
            btn_view = AlreadyTimedoutView(user=user, author=ctx.author)
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message
            return

        # Check owner
        if user == ctx.guild.owner:
            view = v2_card("Error ⚠️", "You can't timeout the Server Owner!")
            return await ctx.send(view=view)

        # Check role hierarchy (author vs user)
        if ctx.author != ctx.guild.owner and user.top_role >= ctx.author.top_role:
            view = v2_card("Error ⚠️", "You can't timeout users having higher or equal role than yours!")
            return await ctx.send(view=view)

        # Check role hierarchy (bot vs user)
        if user.top_role >= ctx.guild.me.top_role:
            view = v2_card("Error ⚠️", "I can't timeout users having higher or equal role than mine.")
            return await ctx.send(view=view)

        # Parse time
        time_delta, duration_text = self.parse_time(time) if time else (timedelta(hours=24), "24 hours")

        if not time_delta:
            view = v2_card("Error ⚠️", "Invalid time format! Use something like `10m`, `1h`, or `1d`.")
            return await ctx.send(view=view)

        # ===== CONFIRMATION STEP =====
        confirm_embed = discord.Embed(
            title=f"{Emojis.WARNING} Confirm Mute Action",
            description=(
                f"Are you sure you want to mute {user.mention}?\n\n"
                f"{Emojis.TARGET} **User:** {user} (`{user.id}`)\n"
                f"{Emojis.DURATION} **Duration:** {duration_text}\n"
                f"{Emojis.REASON} **Reason:** {reason or 'None'}\n\n"
                f"Click **Confirm Mute** to proceed or **Cancel** to abort."
            ),
            color=discord.Color.orange()
        )
        confirm_embed.set_thumbnail(url=self.get_user_avatar(user))
        
        # guild_name pass karo confirm view mein
        confirm_view = ConfirmMuteView(user, ctx.author, time_delta, duration_text, reason, ctx.guild.name)
        confirm_msg = await ctx.send(embed=confirm_embed, view=confirm_view)
        confirm_view.message = confirm_msg
        
        # Wait for confirmation - sab kuch confirm button ke andar hi ho jata hai
        await confirm_view.wait()


async def setup(bot):
    await bot.add_cog(Mute(bot))
