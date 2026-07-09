import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.ui_v2 import v2_card

# ===============================
#         EMOJI CATEGORY
# ===============================
class Emojis:
    DELETE   = "<:CupidXdelete:1474795676251459748>"
    WARNING  = "<:CupidXWarning:1474348304186867784>"
    CROSS    = "<:CupidXCross:1473996646873436336>"
    CHECK    = "<:CupidXtick:1473996329125675105>"
    QUESTION = "<:CupidXQuestion:1474795676251459750>"

    TARGET   = "<:CupidXuser:1475151935379341382>"
    MENTION  = "<:CupidXmention:1476575411247906897>"
    DM       = "<:CupidXMail:1475192722578215083>"
    REASON   = "<:CupidXCommands:1475152376737566722>"
    MOD      = "<:CupidXautomod:1474356609122697382>"

# ===============================
#      CONFIRMATION VIEW
# ===============================
class ConfirmBanView(ui.View):
    def __init__(self, user, author, reason, guild_name):
        super().__init__(timeout=60)
        self.user       = user
        self.author     = author
        self.reason     = reason
        self.guild_name = guild_name
        self.confirmed  = False
        self.message    = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You are not allowed to interact with this!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                timeout_embed = discord.Embed(
                    title=f"{Emojis.WARNING} Confirmation Timed Out",
                    description="The ban action has been cancelled due to inactivity.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=timeout_embed, view=self)
            except:
                pass

    @ui.button(label="✅ Confirm Ban", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True

        await interaction.response.defer()

        # ── BAN APPLY ────────────────────────────────────────────────────────
        try:
            await interaction.guild.ban(
                self.user,
                reason=f"Ban requested by {self.author} | Reason: {self.reason or 'No reason provided'}"
            )
            ban_success = True
        except Exception:
            ban_success = False

        # ── DM AFTER BAN ─────────────────────────────────────────────────────
        dm_status = "No"
        if ban_success:
            try:
                dm_embed = discord.Embed(
                    description=(
                        f"{Emojis.WARNING} You have been **banned** from **{self.guild_name}** "
                        f"by **{self.author}**\n\n"
                        f"{Emojis.REASON} **Reason:** {self.reason or 'None'}"
                    ),
                    color=discord.Color.from_rgb(0, 0, 0)
                )
                await self.user.send(embed=dm_embed)
                dm_status = "Yes"
            except Exception:
                dm_status = "No"

        # ── RESULT EMBED ─────────────────────────────────────────────────────
        if ban_success:
            embed = discord.Embed(
                title=f"{Emojis.CHECK} Successfully Banned",
                description=(
                    f"{Emojis.TARGET} **Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n"
                    f"{Emojis.MENTION} **User Mention:** {self.user.mention}\n"
                    f"{Emojis.DM} **DM Sent:** {dm_status}\n"
                    f"{Emojis.REASON} **Reason:** {self.reason or 'None'}\n\n"
                    f"**Moderator:** {self.author.mention}"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title=f"{Emojis.CROSS} Ban Failed",
                description="An error occurred while trying to ban the user. Please check my permissions.",
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
            description=f"Ban action for {self.user.mention} has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=cancel_embed, view=self)

# ===============================
#      BAN VIEW (After Ban)
# ===============================
class BanView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user    = user
        self.author  = author
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You are not allowed to interact with this!", ephemeral=True
            )
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

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UnbanReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

# ===============================
#      ALREADY BANNED VIEW
# ===============================
class AlreadyBannedView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user    = user
        self.author  = author
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You are not allowed to interact with this!", ephemeral=True
            )
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

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UnbanReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

# ===============================
#      UNBAN REASON MODAL
# ===============================
class UnbanReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Unban Reason")
        self.user   = user
        self.author = author
        self.view   = view
        self.reason_input = ui.TextInput(
            label="Reason for Unbanning",
            placeholder="Provide a reason to unban or leave it blank.",
            required=False,
            max_length=2000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"

        try:
            dm_embed = discord.Embed(
                description=(
                    f"{Emojis.CHECK} You have been **Unbanned** from "
                    f"**{interaction.guild.name}** by **{self.author}**\n\n"
                    f"{Emojis.REASON} **Reason:** {reason}"
                ),
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
            f"**{Emojis.MOD} Moderator:** {interaction.user.mention}"
        )

        card_view = v2_card(f"Successfully Unbanned {self.user.name}", body)

        try:
            await interaction.guild.unban(
                self.user,
                reason=f"Unban requested by {self.author}"
            )
        except:
            pass

        for item in self.view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(view=card_view)

# ===============================
#      MAIN BAN COG
# ===============================
class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot   = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="ban",
        help="Bans a user from the Server",
        usage="ban <member> [reason]",
        aliases=["fuckban", "hackban"]
    )
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        user: discord.User = commands.parameter(description="The user to ban"),
        *,
        reason: str = commands.parameter(description="Reason for the ban", default=None)
    ):
        member = ctx.guild.get_member(user.id)
        if not member:
            try:
                user = await self.bot.fetch_user(user.id)
            except:
                view = v2_card("Error ⚠️", f"User with ID `{user.id}` not found.")
                return await ctx.send(view=view)

        # ── Already banned check ──────────────────────────────────────────────
        bans = [entry async for entry in ctx.guild.bans()]
        if any(ban_entry.user.id == user.id for ban_entry in bans):
            view     = v2_card(
                f"{user.name} is Already Banned!",
                "**Requested User is already banned in this server.**\n\n"
                "Click on the `Unban` button below to unban the mentioned user."
            )
            btn_view = AlreadyBannedView(user=user, author=ctx.author)
            await ctx.send(view=view)
            message = await ctx.send(view=btn_view)
            btn_view.message = message
            return

        # ── Hierarchy checks ──────────────────────────────────────────────────
        if member == ctx.guild.owner:
            view = v2_card("Access Denied ⚠️", "I can't ban the Server Owner!")
            return await ctx.send(view=view)

        if isinstance(member, discord.Member) and member.top_role >= ctx.guild.me.top_role:
            view = v2_card("Access Denied ⚠️", "I can't ban a user with a higher or equal role than mine!")
            return await ctx.send(view=view)

        if isinstance(member, discord.Member) and ctx.author != ctx.guild.owner:
            if member.top_role >= ctx.author.top_role:
                view = v2_card("Access Denied ⚠️", "You can't ban a user with a higher or equal role than yours!")
                return await ctx.send(view=view)

        # ── Confirmation step ─────────────────────────────────────────────────
        confirm_embed = discord.Embed(
            title=f"{Emojis.WARNING} Confirm Ban Action",
            description=(
                f"Are you sure you want to ban {user.mention}?\n\n"
                f"{Emojis.TARGET} **User:** {user} (`{user.id}`)\n"
                f"{Emojis.REASON} **Reason:** {reason or 'None'}\n\n"
                "Click **Confirm Ban** to proceed or **Cancel** to abort."
            ),
            color=discord.Color.orange()
        )
        confirm_embed.set_thumbnail(url=self.get_user_avatar(user))

        confirm_view = ConfirmBanView(user, ctx.author, reason, ctx.guild.name)
        confirm_msg  = await ctx.send(embed=confirm_embed, view=confirm_view)
        confirm_view.message = confirm_msg

        await confirm_view.wait()

        # ── After confirm: send BanView (Unban + Delete buttons) ─────────────
        if confirm_view.confirmed:
            btn_view = BanView(user=user, author=ctx.author)
            message  = await ctx.send(view=btn_view)
            btn_view.message = message


async def setup(bot):
    await bot.add_cog(Ban(bot))
