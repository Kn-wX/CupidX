import discord
from discord.ext import commands
from discord.ui import View, Button
import logging
from utils.config import WEBSITE, SUPPORT_SERVER, BOT_INVITE

class Autorole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ======================================
    # PROFESSIONAL BOT ADD DETECTION SYSTEM
    # ======================================

    async def get_adder(self, guild):
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target.id == self.bot.user.id:
                    return entry.user
        except:
            pass
        return guild.owner

    # ======================================
    # ON JOIN EVENT
    # ======================================

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        await self.bot.wait_until_ready()
        user = await self.get_adder(guild)

        try:

            embed = discord.Embed(
                title="CupidX Deployment Successful",
                description=(
                    f"Hello {user.mention},\n\n"
                    f"**CupidX Security Core** has been successfully deployed in\n"
                    f"`{guild.name}`.\n\n"
                    "Your infrastructure is now protected by\n"
                    "**Real-Time Anti-Nuke & Automated Threat Detection System**"
                ),
                color=0x23272A
            )

            embed.add_field(
                name="Deployment Summary",
                value=(
                    f"Server ID: `{guild.id}`\n"
                    f"Members  : `{guild.member_count}`\n"
                    f"Region   : `{str(guild.preferred_locale).upper()}`"
                ),
                inline=False
            )

            embed.add_field(
                name="Security Modules",
                value=(
                    "• Unauthorized Bot Guard\n"
                    "• Channel Integrity Monitor\n"
                    "• Role Escalation Shield\n"
                    "• Webhook Breach Protection\n"
                    "• Ban/Kick Abuse Detection\n"
                    "• Anti Mass-Mention System"
                ),
                inline=False
            )

            embed.add_field(
                name="Getting Started",
                value=(
                    "Run `$help` to view all modules\n"
                    "Configure security using `$setup`\n"
                    "Enable logs using `$log enable`"
                ),
                inline=False
            )

            embed.set_thumbnail(
                url=guild.icon.url if guild.icon else self.bot.user.display_avatar.url
            )

            embed.set_footer(
                text="CupidX Security Interface",
                icon_url=self.bot.user.display_avatar.url
            )

            embed.timestamp = discord.utils.utcnow()

            view = View()

            view.add_item(Button(
                label="Dashboard",
                style=discord.ButtonStyle.link,
                url=WEBSITE
            ))

            view.add_item(Button(
                label="Support Center",
                style=discord.ButtonStyle.link,
                url=SUPPORT_SERVER
            ))

            view.add_item(Button(
                label="Re-Invite CupidX",
                style=discord.ButtonStyle.link,
                url=BOT_INVITE
            ))

            await user.send(embed=embed, view=view)

        except Exception as e:
            logging.error(f"CupidX Onboarding DM Error: {e}")

async def setup(bot):
    await bot.add_cog(Autorole(bot))
        