import discord
from utils.detectfile import *
from discord.ext import commands
from datetime import datetime

# ====== CHANNEL IDS ======
JOIN_LOG_CHANNEL = 1472594599926042850  # <-- JOIN log channel ID
LEAVE_LOG_CHANNEL = 1472594577729785896  # <-- LEAVE log channel ID

# CUPIDX_BANNER imported from utils.detectfile


class GuildGlobalLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_invite(self, guild):
        """Creates an invite from the server's first available text channel"""
        try:
            # Pehle system channel try karo
            if guild.system_channel and guild.system_channel.permissions_for(guild.me).create_instant_invite:
                invite = await guild.system_channel.create_invite(max_age=0, max_uses=0, unique=False)
                return invite.url

            # Phir koi bhi text channel dhundo jisme invite ban sake
            for channel in guild.text_channels:
                perms = channel.permissions_for(guild.me)
                if perms.create_instant_invite:
                    invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
                    return invite.url

        except discord.Forbidden:
            return "❌ Doesn't have permission for creating invite link"
        except discord.HTTPException:
            return "❌ Can't create invite link"

        return "❌ Doesn't have channel"

    def get_banner(self, guild):
        return guild.banner.url if guild.banner else CUPIDX_BANNER

    # ================= JOIN =================

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        channel = self.bot.get_channel(JOIN_LOG_CHANNEL)
        if not channel:
            return

        # Invite link generate karo
        invite = await self.create_invite(guild)

        embed = discord.Embed(
            title="<:CupidXtick1:1474369967271968949> Joined New Server",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        embed.add_field(name="Server Name", value=guild.name, inline=False)
        embed.add_field(name="Server ID", value=guild.id, inline=False)
        embed.add_field(name="Owner", value=f"{guild.owner} ({guild.owner_id})", inline=False)

        embed.add_field(
            name="Members",
            value=f"Total: {guild.member_count}\n"
                  f"Humans: {len([m for m in guild.members if not m.bot])}\n"
                  f"Bots: {len([m for m in guild.members if m.bot])}",
            inline=False
        )

        embed.add_field(
            name="Channels",
            value=f"Total: {len(guild.channels)}\n"
                  f"Text: {len(guild.text_channels)}\n"
                  f"Voice: {len(guild.voice_channels)}",
            inline=False
        )

        # Invite link hamesha show hoga ab
        embed.add_field(name="🔗 Invite Link", value=invite, inline=False)

        embed.set_image(url=self.get_banner(guild))

        embed.set_footer(
            text=f"CupidX • Server Count: {len(self.bot.guilds)}",
            icon_url=self.bot.user.display_avatar.url
        )

        await channel.send(embed=embed)

    # ================= LEAVE =================

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):

        channel = self.bot.get_channel(LEAVE_LOG_CHANNEL)
        if not channel:
            return

        banner = guild.banner.url if guild.banner else CUPIDX_BANNER
        icon = guild.icon.url if guild.icon else None

        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])

        embed = discord.Embed(
            title=f"🔴 Left: {guild.name}",
            color=0xff2b2b,
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=icon)

        embed.add_field(
            name="Server Info",
            value=f"Name: {guild.name}\n"
                  f"ID: {guild.id}\n"
                  f"Owner: {guild.owner} ({guild.owner_id})\n"
                  f"Created: <t:{int(guild.created_at.timestamp())}:R>",
            inline=False
        )

        embed.add_field(
            name="Members",
            value=f"Total: {guild.member_count}\n"
                  f"Humans: {humans}\n"
                  f"Bots: {bots}",
            inline=False
        )

        embed.add_field(
            name="Channels",
            value=f"Total: {len(guild.channels)}\n"
                  f"Text: {len(guild.text_channels)}\n"
                  f"Voice: {len(guild.voice_channels)}",
            inline=False
        )

        embed.set_image(url=banner)

        embed.set_footer(
            text=f"CupidX • Server Count: {len(self.bot.guilds)}",
            icon_url=self.bot.user.display_avatar.url
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuildGlobalLogs(bot))
)
