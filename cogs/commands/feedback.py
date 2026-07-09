import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from utils.config import OWNER_IDS

FEEDBACK_CHANNEL_ID = 1478669568171049033


# ================= EDIT MODAL =================

class FeedbackEditModal(Modal):

    def __init__(self, view):
        super().__init__(title="Edit your feedback")
        self.view_ref = view

        self.feedback = TextInput(
            label="Update your feedback",
            style=discord.TextStyle.paragraph,
            default=view.feedback_text,
            max_length=1000
        )

        self.add_item(self.feedback)

    async def on_submit(self, interaction: discord.Interaction):

        self.view_ref.feedback_text = self.feedback.value

        embed = self.view_ref.build_embed()

        await interaction.response.edit_message(
            embed=embed,
            view=self.view_ref
        )


# ================= BUTTON VIEW =================

class FeedbackConfirmView(View):

    def __init__(self, ctx, feedback):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.feedback_text = feedback

    def build_embed(self):

        embed = discord.Embed(
            title="💬 Feedback Preview",
            description=(
                "Please review your feedback before submitting.\n\n"
                "Press **Confirm** to submit it.\n"
                "You can also **Edit** or **Cancel**."
            ),
            color=0x5865F2
        )

        embed.add_field(
            name="💬 Your Feedback",
            value=self.feedback_text,
            inline=False
        )

        embed.set_footer(
            text=f"User: {self.ctx.author} • Server: {self.ctx.guild.name}"
        )

        return embed


# ================= CONFIRM BUTTON =================

    @discord.ui.button(label="Confirm", emoji="✅", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):

        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This feedback isn't yours.",
                ephemeral=True
            )

        channel = interaction.client.get_channel(FEEDBACK_CHANNEL_ID)

        # ===== FEEDBACK CHANNEL EMBED =====

        embed = discord.Embed(
            title="💌 New Community Feedback",
            description="A member has submitted feedback for the community.",
            color=0x00ff9c
        )

        embed.add_field(
            name="👤 Submitted By",
            value=f"{self.ctx.author.mention}\n`{self.ctx.author.id}`",
            inline=True
        )

        embed.add_field(
            name="🌍 Server",
            value=self.ctx.guild.name,
            inline=True
        )

        embed.add_field(
            name="📍 Channel",
            value=self.ctx.channel.mention,
            inline=True
        )

        embed.add_field(
            name="💬 Feedback Message",
            value=self.feedback_text,
            inline=False
        )

        embed.set_thumbnail(url=self.ctx.author.display_avatar.url)

        embed.set_footer(
            text=f"Feedback System • {self.ctx.guild.name}",
            icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None
        )

        await channel.send(embed=embed)

        # ===== THANK YOU DM =====

        dm_embed = discord.Embed(
            title="💖 Thank You for Your Feedback!",
            description=(
                "We truly appreciate you taking the time to share your thoughts.\n\n"
                "Your feedback helps us improve and grow the community.\n\n"
                "✨ **Your voice matters to us!**"
            ),
            color=0xff66c4
        )

        dm_embed.add_field(
            name="💬 Your Feedback",
            value=self.feedback_text,
            inline=False
        )

        dm_embed.set_footer(text="Thanks for supporting our community 💜")

        try:
            await self.ctx.author.send(embed=dm_embed)
        except:
            pass

        await interaction.response.edit_message(
            content="✅ Feedback submitted successfully!",
            embed=None,
            view=None
        )


# ================= EDIT BUTTON =================

    @discord.ui.button(label="Edit", emoji="✏", style=discord.ButtonStyle.blurple)
    async def edit(self, interaction: discord.Interaction, button: Button):

        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This feedback isn't yours.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            FeedbackEditModal(self)
        )


# ================= CANCEL BUTTON =================

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):

        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This feedback isn't yours.",
                ephemeral=True
            )

        await interaction.response.edit_message(
            content="❌ Feedback cancelled.",
            embed=None,
            view=None
        )


# ================= COMMAND =================

class Feedback(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="feedback", aliases=["vouch"])
    async def feedback(self, ctx, *, feedback: str):

        view = FeedbackConfirmView(ctx, feedback)

        embed = view.build_embed()

        await ctx.reply(
            embed=embed,
            view=view
        )

# ================= BOT RULES COMMAND =================

    @commands.hybrid_command(name="botrules", description="CupidX Rules and Terms of Use")
    async def botrules(self, ctx):

        # OWNER CHECK (config.py se)
        if ctx.author.id not in OWNER_IDS:
            return await ctx.reply(
                "❌ Only the bot owner can use this command.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="<a:emojisetting:1476854070412316713> CupidX Rules & Terms of Use",
            description="By using this bot, you **agree to follow all the rules mentioned below**.",
            color=0x2f3136
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 1 • **Proper Usage**",
            value="<a:CupidXdot:1473986328126558209> This bot must only be used for **server management, moderation, and entertainment purposes**.\n<a:CupidXdot:1473986328126558209> Any form of **misuse, spam, or abuse of commands** is not allowed.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 2 • **No Abuse or Exploits**",
            value="<a:CupidXdot:1473986328126558209> Users must **not exploit bugs, glitches, or loopholes** in the bot.\n<a:CupidXdot:1473986328126558209> If you find any bug, please **report it to the support server**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 3 • **Follow Discord Rules**",
            value="<a:CupidXdot:1473986328126558209> All users must follow **Discord Terms of Service and Community Guidelines**.\n<a:CupidXdot:1473986328126558209> Violating Discord rules may result in **restricted access to the bot**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 4 • **Data Storage**",
            value="<a:CupidXdot:1473986328126558209> The bot may store: **User IDs, Server IDs, Settings, and Command usage data**.\n<a:CupidXdot:1473986328126558209> This data is only used for **bot functionality and improving the service**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 5 • **Administrator Responsibility**",
            value="<a:CupidXdot:1473986328126558209> Server administrators are responsible for **how the bot is used in their server**.\n<a:CupidXdot:1473986328126558209> Misuse of moderation or management commands can cause **server issues**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 6 • **Premium Features**",
            value="<a:CupidXdot:1473986328126558209> Some features of the bot may be **premium only**.\n<a:CupidXdot:1473986328126558209> Attempting to **bypass or abuse premium features** may result in **premium removal or blacklist**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 7 • **Service Availability**",
            value="<a:CupidXdot:1473986328126558209> The bot aims to run **24/7**, but downtime may occur due to: **Maintenance, Updates, or Technical issues**.",
            inline=False
        )

        embed.add_field(
            name="<:CupidXarrow:1474383919725150362> 8 • **Rule Changes**",
            value="<a:CupidXdot:1473986328126558209> The bot owner reserves the right to **update or change these rules at any time** without prior notice.",
            inline=False
        )

        embed.add_field(
            name="<a:CupidXping:1474771697289924721> **Violations**",
            value="<a:CupidXdot:1473986328126558209> Breaking these rules may result in: **Command restriction, User/Server blacklist, or Removal of premium access**.",
            inline=False
        )

        embed.set_footer(
            text=f"CupidX • {ctx.guild.name}", 
            icon_url=self.bot.user.display_avatar.url
        )

        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Feedback(bot))
