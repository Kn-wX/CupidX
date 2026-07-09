import discord
from discord.ext import commands
from discord.ui import Modal, TextInput
import asyncio

OWNER_ID = 1378341015181856768
BUG_CHANNEL_ID = 1472594631870120179  # Configure this in your config

# ============================================================
# V2 CARD HELPERS - Black and White Theme
# ============================================================

def create_v2_card(text_content, buttons=None, timeout=None):
    """Create a V2 LayoutView with Container and TextDisplay"""
    view = discord.ui.LayoutView(timeout=timeout)

    # Create container with text display
    container_items = [discord.ui.TextDisplay(text_content)]

    # Add separator and buttons if provided
    if buttons:
        container_items.append(discord.ui.Separator())
        action_row = discord.ui.ActionRow()
        for button in buttons:
            action_row.add_item(button)
        container_items.append(action_row)

    container = discord.ui.Container(*container_items)
    view.add_item(container)
    return view


# ============================================================
# REJECT MODAL - For Bug Not Fixed
# ============================================================
class RejectModal(Modal, title="Bug Not Fixed - Reason"):
    reason = TextInput(
        label="Reason why bug cannot be fixed",
        style=discord.TextStyle.paragraph,
        placeholder="Enter detailed reason...",
        required=True,
        max_length=1000
    )

    def __init__(self, user, owner, original_message, view_to_update):
        super().__init__()
        self.user = user
        self.owner = owner
        self.original_message = original_message
        self.view_to_update = view_to_update

    async def on_submit(self, interaction: discord.Interaction):
        # Send detailed DM to user
        dm_text = (
            "## Bug Report Status: Not Fixed\n\n"
            f"Your bug report has been reviewed by {self.owner.mention} ({self.owner.id}).\n\n"
            "**Status:** Cannot Be Fixed\n"
            f"**Reason:** {self.reason.value}\n\n"
            "If you have any questions, please contact the support team."
        )

        try:
            dm_view = create_v2_card(dm_text)
            await self.user.send(view=dm_view)
        except:
            pass

        # Update the original message to show completed status
        completed_text = (
            "## Bug Report Processed\n\n"
            f"**Reported By:** {self.user.mention}\n"
            f"**Claimed By:** {self.owner.mention}\n"
            f"**Status:** Not Fixed\n"
            f"**Reason:** {self.reason.value}\n\n"
            "-# This report has been closed."
        )

        completed_view = create_v2_card(completed_text)
        await self.original_message.edit(view=completed_view)

        await interaction.response.send_message(
            view=create_v2_card("Report marked as Not Fixed. User has been notified."),
            ephemeral=True
        )


# ============================================================
# CLAIMED VIEW - Shows after claim (Bug Fixed + Bug Not Fixed buttons)
# ============================================================
class ClaimedView(discord.ui.LayoutView):
    def __init__(self, user, owner, original_message, bug_info):
        super().__init__(timeout=None)  # Persistent view
        self.user = user
        self.owner = owner
        self.original_message = original_message
        self.bug_info = bug_info
        self._build_view()

    def _build_view(self):
        self.clear_items()

        # Create text display
        text = (
            "## Bug Report Claimed\n\n"
            f"**Reported By:** {self.user.mention}\n"
            f"**Claimed By:** {self.owner.mention}\n\n"
            "Select an action below:"
        )

        # Bug Fixed button - Black (Primary)
        btn_fixed = discord.ui.Button(
            label="Bug Fixed",
            style=discord.ButtonStyle.primary,  # Black/Dark in V2
            custom_id=f"bug_fixed_{self.user.id}_{self.original_message.id}"
        )
        btn_fixed.callback = self._bug_fixed_callback

        # Bug Not Fixed button - White/Gray (Secondary)
        btn_not_fixed = discord.ui.Button(
            label="Bug Not Fixed",
            style=discord.ButtonStyle.secondary,  # White/Gray in V2
            custom_id=f"bug_not_fixed_{self.user.id}_{self.original_message.id}"
        )
        btn_not_fixed.callback = self._bug_not_fixed_callback

        # Build container
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            discord.ui.Separator(),
            discord.ui.ActionRow(btn_fixed, btn_not_fixed)
        )
        self.add_item(container)

    async def _bug_fixed_callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                view=create_v2_card("Only the bot owner can use this button."),
                ephemeral=True
            )

        # Send detailed DM to user
        dm_text = (
            "## Bug Report Status: Fixed\n\n"
            f"Your bug report has been claimed by {self.owner.mention} ({self.owner.id}).\n"
            "Work has been completed on your code.\n\n"
            f"**Bug Details:** {self.bug_info}\n"
            "**Status:** Successfully Fixed\n\n"
            "Thank you for your report!"
        )

        try:
            dm_view = create_v2_card(dm_text)
            await self.user.send(view=dm_view)
        except:
            pass

        # Update original message
        completed_text = (
            "## Bug Report Processed\n\n"
            f"**Reported By:** {self.user.mention}\n"
            f"**Claimed By:** {self.owner.mention}\n"
            "**Status:** Fixed\n\n"
            "-# This report has been closed."
        )

        completed_view = create_v2_card(completed_text)
        await self.original_message.edit(view=completed_view)

        await interaction.response.send_message(
            view=create_v2_card("Bug marked as Fixed. User has been notified."),
            ephemeral=True
        )

    async def _bug_not_fixed_callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                view=create_v2_card("Only the bot owner can use this button."),
                ephemeral=True
            )

        await interaction.response.send_modal(
            RejectModal(self.user, interaction.user, self.original_message, self)
        )


# ============================================================
# REPORT VIEW - Initial view with Claim and Cancel buttons
# ============================================================
class ReportView(discord.ui.LayoutView):
    def __init__(self, user, issue, guild_name, channel_name):
        super().__init__(timeout=None)  # Persistent view
        self.user = user
        self.issue = issue
        self.guild_name = guild_name
        self.channel_name = channel_name
        self._build_view()

    def _build_view(self):
        self.clear_items()

        # Create text display with bug info
        text = (
            "## New Bug Report\n\n"
            f"**Issue:** {self.issue[:500]}\n\n"
            f"**Reported By:** {self.user.mention}\n"
            f"**Server:** {self.guild_name}\n"
            f"**Channel:** {self.channel_name}"
        )

        # Claim button - Black (Primary)
        btn_claim = discord.ui.Button(
            label="Claim",
            style=discord.ButtonStyle.primary,  # Black/Dark in V2
            custom_id=f"claim_{self.user.id}_{hash(self.issue)}"
        )
        btn_claim.callback = self._claim_callback

        # Cancel button - White/Gray (Secondary)
        btn_cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,  # White/Gray in V2
            custom_id=f"cancel_{self.user.id}_{hash(self.issue)}"
        )
        btn_cancel.callback = self._cancel_callback

        # Build container
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            discord.ui.Separator(),
            discord.ui.ActionRow(btn_claim, btn_cancel)
        )
        self.add_item(container)

    async def _claim_callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                view=create_v2_card("Only the bot owner can use this button."),
                ephemeral=True
            )

        # Send detailed DM to user
        dm_text = (
            "## Bug Report Claimed\n\n"
            f"Your bug report has been claimed by {interaction.user.mention} ({interaction.user.id}).\n"
            "Work is now being done on your code.\n\n"
            f"**Bug Details:** {self.issue}\n"
            f"**Claimed By:** {interaction.user.display_name}\n"
            f"**Owner ID:** {interaction.user.id}\n\n"
            "You will receive another notification once the bug is fixed or if it cannot be fixed."
        )

        try:
            dm_view = create_v2_card(dm_text)
            await self.user.send(view=dm_view)
        except:
            pass

        # Update view to show claimed state with new buttons
        claimed_view = ClaimedView(
            self.user, 
            interaction.user, 
            interaction.message, 
            self.issue
        )

        await interaction.message.edit(view=claimed_view)

        await interaction.response.send_message(
            view=create_v2_card("Report claimed successfully. User has been notified."),
            ephemeral=True
        )

    async def _cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                view=create_v2_card("Only the bot owner can use this button."),
                ephemeral=True
            )

        # Send cancellation DM to user
        dm_text = (
            "## Bug Report Cancelled\n\n"
            f"Your bug report has been cancelled by {interaction.user.mention} ({interaction.user.id}).\n\n"
            f"**Bug Details:** {self.issue}\n\n"
            "If you believe this was a mistake, please submit a new report."
        )

        try:
            dm_view = create_v2_card(dm_text)
            await self.user.send(view=dm_view)
        except:
            pass

        # Update original message
        cancelled_text = (
            "## Bug Report Cancelled\n\n"
            f"**Reported By:** {self.user.mention}\n"
            f"**Cancelled By:** {interaction.user.mention}\n\n"
            "-# This report has been cancelled."
        )

        cancelled_view = create_v2_card(cancelled_text)
        await interaction.message.edit(view=cancelled_view)

        await interaction.response.send_message(
            view=create_v2_card("Report cancelled. User has been notified."),
            ephemeral=True
        )


# ============================================================
# CONFIRMATION VIEW - For user submitting bug report
# ============================================================
class ConfirmBugView(discord.ui.LayoutView):
    def __init__(self, ctx, issue):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.issue = issue
        self._build_view()

    def _build_view(self):
        self.clear_items()

        warning_text = (
            "## Confirm Bug Report\n\n"
            "**IMPORTANT NOTICE**\n\n"
            "This command is NOT for fun.\n"
            "This report will be sent directly to the support server.\n"
            "Only submit if this is a real bug.\n\n"
            "Fake or spam reports may result in blacklist.\n\n"
            f"**Your Bug Report:**\n```\n{self.issue[:1000]}\n```"
        )

        # Confirm button - Black (Primary)
        btn_confirm = discord.ui.Button(
            label="Confirm and Send",
            style=discord.ButtonStyle.primary,
            custom_id="confirm_bug"
        )
        btn_confirm.callback = self._confirm_callback

        # Cancel button - White/Gray (Secondary)
        btn_cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_bug"
        )
        btn_cancel.callback = self._cancel_callback

        container = discord.ui.Container(
            discord.ui.TextDisplay(warning_text),
            discord.ui.Separator(),
            discord.ui.ActionRow(btn_confirm, btn_cancel)
        )
        self.add_item(container)

    async def _confirm_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                view=create_v2_card("This is not your interaction."),
                ephemeral=True
            )

        channel = interaction.client.get_channel(BUG_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message(
                view=create_v2_card("Bug channel not found. Please contact support."),
                ephemeral=True
            )

        # Send to bug channel with persistent view
        report_view = ReportView(
            self.ctx.author,
            self.issue,
            self.ctx.guild.name if self.ctx.guild else "DM",
            self.ctx.channel.name if hasattr(self.ctx.channel, 'name') else "DM"
        )

        await channel.send(view=report_view)

        # Update confirmation message
        success_text = (
            "## Bug Report Sent\n\n"
            "Your bug report has been sent to the support system.\n"
            "You will receive a DM when a developer claims your report."
        )

        success_view = create_v2_card(success_text)
        await interaction.message.edit(view=success_view)

        await interaction.response.send_message(
            view=create_v2_card("Bug report submitted successfully!"),
            ephemeral=True
        )

    async def _cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                view=create_v2_card("This is not your interaction."),
                ephemeral=True
            )

        cancelled_text = (
            "## Bug Report Cancelled\n\n"
            "Your bug report has been cancelled."
        )

        cancelled_view = create_v2_card(cancelled_text)
        await interaction.message.edit(view=cancelled_view)

        await interaction.response.send_message(
            view=create_v2_card("Bug report cancelled."),
            ephemeral=True
        )

    async def on_timeout(self):
        pass


# ============================================================
# BUG SYSTEM COG
# ============================================================
class BugSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views on startup
        # This ensures views work after bot restart
        pass  # Views are registered when messages are sent

    @commands.hybrid_command(name="report", aliases=["bug"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def report(self, ctx, *, issue: str):
        """Report a bug to the developers"""
        view = ConfirmBugView(ctx, issue)
        await ctx.reply(view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(BugSystem(bot))
