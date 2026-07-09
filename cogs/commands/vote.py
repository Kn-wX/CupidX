import discord

from discord.ext import commands
from utils.config import TOPGG_VOTE_LINK

BOT_INVITE_URL = "https://discord.com/oauth2/authorize?client_id=1409213287211470848&permissions=8&integration_type=0&scope=applications.commands+bot"
SUPPORT_SERVER_URL = "https://discord.gg/TxbpVnEzuF"

OWNER_SEND_MESSAGE = (
    "We have completely revamped our bot. **This bot (CupidX) will be shutting down soon.**\n\n"
    "You can kick this bot from your server and add our new upgraded bot using the invite button or URL below.\n\n"
    "Our new bot has **1300+ unique and upgraded commands** and is also a **verified bot**.\n\n"
    "Add it to your server now! If you have any questions, click the support button or URL below to contact the owner directly."
)


class OwnerSendConfirmView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="✅ Confirm Send", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="📤 **Sending message to all server owners...**",
            embed=None,
            view=None
        )

        success = 0
        failed = 0

        for guild in self.bot.guilds:
            owner = guild.owner
            if owner is None:
                failed += 1
                continue

            try:
                embed = discord.Embed(
                    title="⚠️ Important Notice from CupidX",
                    description=f"{owner.mention}\n\n{OWNER_SEND_MESSAGE}",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="🔗 Bot Invite URL",
                    value=BOT_INVITE_URL,
                    inline=False
                )
                embed.add_field(
                    name="💬 Support Server",
                    value=SUPPORT_SERVER_URL,
                    inline=False
                )
                embed.set_footer(text="CupidX Official Notice")

                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Invite New Bot",
                    url=BOT_INVITE_URL,
                    style=discord.ButtonStyle.link
                ))
                view.add_item(discord.ui.Button(
                    label="Support Server",
                    url=SUPPORT_SERVER_URL,
                    style=discord.ButtonStyle.link
                ))

                # Send in guild (tag server owner)
                # Find a channel bot can send in
                sent_in_guild = False
                for channel in guild.text_channels:
                    perms = channel.permissions_for(guild.me)
                    if perms.send_messages and perms.embed_links:
                        await channel.send(
                            content=f"{owner.mention}",
                            embed=embed,
                            view=view
                        )
                        sent_in_guild = True
                        break

                # Also DM the owner
                try:
                    await owner.send(embed=embed, view=view)
                except discord.Forbidden:
                    pass  # DMs closed, but guild message was sent

                if sent_in_guild:
                    success += 1
                else:
                    failed += 1

            except Exception:
                failed += 1

        result_embed = discord.Embed(
            title="📊 Owner Send — Results",
            color=discord.Color.green() if success > 0 else discord.Color.red()
        )
        result_embed.add_field(name="✅ Sent", value=str(success), inline=True)
        result_embed.add_field(name="❌ Failed", value=str(failed), inline=True)
        result_embed.add_field(name="🌐 Total Servers", value=str(len(self.bot.guilds)), inline=True)

        await interaction.edit_original_response(content=None, embed=result_embed, view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Cancelled. No messages were sent.",
            embed=None,
            view=None
        )


class Vote(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ownersend")
    @commands.is_owner()
    async def ownersend(self, ctx):
        """Send a shutdown notice to all server owners. Bot owner only."""

        embed = discord.Embed(
            title="📢 Owner Send — Confirmation",
            description=(
                "This will send a **shutdown notice** to **every server** the bot is in.\n\n"
                "Each server's owner will be **tagged in their server** and also receive a **DM**.\n\n"
                f"**Total Servers:** `{len(self.bot.guilds)}`\n\n"
                "Are you sure you want to proceed?"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="This action cannot be undone.")

        view = OwnerSendConfirmView(self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="vote")
    async def vote(self, ctx):

        embed = discord.Embed(
            title="🗳️ Support The Bot!",
            description="Click the link below to vote and support development 💜",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="🔗 Vote Link",
            value=f"[Click here to vote]({TOPGG_VOTE_LINK})",
            inline=False
        )

        embed.set_footer(text=f"Requested by {ctx.author.name}")
        embed.set_thumbnail(url="https://top.gg/_next/image?url=%2Fassets%2Flogo.png&w=64&q=75")

        await ctx.send(embed=embed)

    @commands.command(name="privacy")
    async def privacy(self, ctx):

        embed = discord.Embed(
            title="Privacy Policy",
            description=(
                "This application does not store any user data permanently.\n\n"
                "All data processed by the bot is used only temporarily to provide its intended functionality. "
                "No personal data is sold, shared, or distributed to third parties.\n\n"
                "The bot may process message content and user information only for command execution and feature functionality. "
                "This data is not logged or stored beyond what is necessary for immediate operation.\n\n"
                "If you have any concerns, you may contact the developer."
            ),
            color=discord.Color.purple()
        )

        embed.set_footer(text="For a more detailed version, click the button below.")

        view = discord.ui.View()
        button = discord.ui.Button(
            label="Link",
            url="https://www.notion.so/Privacy-Policy-347d4339e1ca803084a3c42d0363e4fc?source=copy_link",
            style=discord.ButtonStyle.link
        )
        view.add_item(button)

        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Vote(bot))
