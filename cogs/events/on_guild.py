import discord
from discord.ext import commands
from discord.ui import View, Button
import logging
from utils.config import WEBSITE, SUPPORT_SERVER, BOT_INVITE

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)


class Guild(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==============================
    # GUILD JOIN EVENT (WELCOME)
    # ==============================

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:

            log_channel_id = 1472594599926042822
            log_channel = self.bot.get_channel(log_channel_id)

            if log_channel:
                log_embed = discord.Embed(
                    title="Guild Joined",
                    color=0xFCD005,
                    timestamp=discord.utils.utcnow()
                )

                log_embed.add_field(
                    name="Server Info",
                    value=(
                        f"**Name:** {guild.name}\n"
                        f"**ID:** {guild.id}\n"
                        f"**Owner:** {guild.owner} ({guild.owner_id})\n"
                        f"**Members:** {guild.member_count}"
                    ),
                    inline=False
                )

                if guild.icon:
                    log_embed.set_thumbnail(url=guild.icon.url)

                await log_channel.send(embed=log_embed)

            embed = discord.Embed(
                description=(
                    "<:CupidXarrow:1474383919725150362> **Current prefix:**  `$`\n"
                    "<:CupidXarrow:1474383919725150362> **Get started with:** `$help`\n"
                    "<:CupidXarrow:1474383919725150362> For guides & support, join our **Support Server**"
                ),
                color=discord.Color.red()
            )

            embed.set_author(
                name="Thanks for adding me!",
                icon_url=guild.me.display_avatar.url
            )

            embed.set_footer(text="Powered by CupidX Development™")

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            view = View()

            view.add_item(Button(
                label="Support",
                style=discord.ButtonStyle.link,
                url=SUPPORT_SERVER
            ))

            view.add_item(Button(
                label="Web",
                style=discord.ButtonStyle.link,
                url=WEBSITE
            ))

            channel = guild.system_channel

            if not channel:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break

            if not channel:
                logging.error(f"No sendable channel found in {guild.name}")
                return

            await channel.send(embed=embed, view=view)

        except Exception as e:
            logging.error(f"Error in on_guild_join: {e}")

    # ==============================
    # GUILD REMOVE EVENT
    # ==============================

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            log_channel_id = 1472594599926042822
            log_channel = self.bot.get_channel(log_channel_id)

            if log_channel:
                embed = discord.Embed(
                    title="Guild Removed",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )

                embed.add_field(
                    name="Server Info",
                    value=(
                        f"**Name:** {guild.name}\n"
                        f"**ID:** {guild.id}\n"
                        f"**Owner:** {guild.owner} ({guild.owner_id})\n"
                        f"**Members:** {guild.member_count}"
                    ),
                    inline=False
                )

                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)

                await log_channel.send(embed=embed)

            # =========================
            # OWNER DM WHEN BOT REMOVED
            # =========================
            try:
                owner = guild.owner
                if owner:

                    leave_embed = discord.Embed(
                        title="⚠️ CupidX Removed From Your Server",
                        description=(
                            f"Hey **{owner.name}**, CupidX has been removed from your server\n\n"
                            f"**Server:** {guild.name}\n"
                            f"**Server ID:** {guild.id}\n\n"
                            "If this action was not intended,\n"
                            "you can re-invite CupidX anytime to restore\n"
                            "your server’s protection system."
                        ),
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )

                    leave_embed.set_footer(
                        text="CupidX Advanced Security • We keep your community safe"
                    )

                    leave_view = View()

                    leave_view.add_item(Button(
                        label="Re-Invite",
                        style=discord.ButtonStyle.link,
                        url=BOT_INVITE
                    ))

                    leave_view.add_item(Button(
                        label="Support",
                        style=discord.ButtonStyle.link,
                        url=SUPPORT_SERVER
                    ))

                    leave_view.add_item(Button(
                        label="Web",
                        style=discord.ButtonStyle.link,
                        url=WEBSITE
                    ))

                    await owner.send(embed=leave_embed, view=leave_view)

            except Exception as dm_err:
                logging.error(f"[Leave DM Error] {dm_err}")

        except Exception as e:
            logging.error(f"Error in on_guild_remove: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Guild(bot))bot))