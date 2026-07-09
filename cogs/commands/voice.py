import discord
from discord.ext import commands, tasks
from discord.utils import get
import os
from utils.Tools import *
from typing import Optional, Union
from discord.ext.commands import Context
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from utils import *
import datetime
import aiosqlite
from utils.detectfile import (
    EMOJI_TICK, EMOJI_CROSS, EMOJI_CROSS2 as EMOJI_VOICE,
    EMOJI_WARN, EMOJI_SHIELD, EMOJI_MUTE, EMOJI_USER
)

DB_PATH = "db/vctime.db"


class Voice(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0x000000
        # Live join tracking only (not persisted) — { guild_id: { user_id: joined_at } }
        self.live_joins = {}
        bot.loop.create_task(self._init_db())
        self.auto_reset_old_sessions.start()

    def cog_unload(self):
        self.auto_reset_old_sessions.cancel()

    # ─────────────────────────────────────────────
    #  DATABASE INIT
    # ─────────────────────────────────────────────
    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vc_sessions (
                    guild_id  INTEGER,
                    user_id   INTEGER,
                    date      TEXT,
                    duration  INTEGER,
                    PRIMARY KEY (guild_id, user_id, date)
                )
            """)
            await db.commit()

    # ─────────────────────────────────────────────
    #  AUTO RESET — runs every 1 hour
    #  Deletes sessions older than 7 days
    # ─────────────────────────────────────────────
    @tasks.loop(hours=1)
    async def auto_reset_old_sessions(self):
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%d/%m/%Y")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM vc_sessions WHERE date < ?", (cutoff,)
            )
            await db.commit()

    @auto_reset_old_sessions.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────────
    #  DB HELPERS
    # ─────────────────────────────────────────────
    async def _add_session(self, guild_id, user_id, date_str, duration):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO vc_sessions (guild_id, user_id, date, duration)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, date)
                DO UPDATE SET duration = duration + excluded.duration
            """, (guild_id, user_id, date_str, duration))
            await db.commit()

    async def _get_sessions(self, guild_id, user_id):
        """Return last 7 days sessions for a user."""
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%d/%m/%Y")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT date, duration FROM vc_sessions
                WHERE guild_id = ? AND user_id = ? AND date >= ?
                ORDER BY date DESC
            """, (guild_id, user_id, cutoff)) as cursor:
                return await cursor.fetchall()  # [(date, duration), ...]

    async def _get_all_users(self, guild_id):
        """Return all users with their total time (last 7 days) for a guild."""
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%d/%m/%Y")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT user_id, SUM(duration) as total
                FROM vc_sessions
                WHERE guild_id = ? AND date >= ?
                GROUP BY user_id
                ORDER BY total DESC
            """, (guild_id, cutoff)) as cursor:
                return await cursor.fetchall()  # [(user_id, total), ...]

    async def _get_date_leaderboard(self, guild_id, date_str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT user_id, duration FROM vc_sessions
                WHERE guild_id = ? AND date = ?
                ORDER BY duration DESC
            """, (guild_id, date_str)) as cursor:
                return await cursor.fetchall()

    async def _reset_guild(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM vc_sessions WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def _reset_user(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM vc_sessions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    @commands.group(name="voice", invoke_without_command=True, aliases=['vc'])
    @blacklist_check()
    @ignore_check()
    async def vc(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = discord.Embed(
                title=f"{EMOJI_VOICE} Voice Commands",
                description="Explore all voice management commands available below.",
                color=0x134E5E
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            
            sub_cmds_1 = (
                f"`{ctx.prefix}voice kick` - Kick a member from voice\n"
                f"`{ctx.prefix}voice kickall` - Kick everyone from voice\n"
                f"`{ctx.prefix}voice mute` - Mute a member in voice\n"
                f"`{ctx.prefix}voice unmute` - Unmute a member in voice\n"
                f"`{ctx.prefix}voice muteall` - Mute everyone in voice\n"
                f"`{ctx.prefix}voice unmuteall` - Unmute everyone in voice\n"
                f"`{ctx.prefix}voice deafen` - Deafen a member in voice\n"
                f"`{ctx.prefix}voice undeafen` - Undeafen a member in voice\n"
                f"`{ctx.prefix}voice deafenall` - Deafen everyone in voice\n"
                f"`{ctx.prefix}voice undeafall` - Undeafen everyone in voice\n"
                f"`{ctx.prefix}voice move` - Move a member to a channel\n"
                f"`{ctx.prefix}voice moveall` - Move everyone to a channel\n"
            )
            sub_cmds_2 = (
                f"`{ctx.prefix}voice pull` - Pull a member to your channel\n"
                f"`{ctx.prefix}voice pullall` - Pull everyone to your channel\n"
                f"`{ctx.prefix}voice lock` - Lock the voice channel\n"
                f"`{ctx.prefix}voice unlock` - Unlock the voice channel\n"
                f"`{ctx.prefix}voice private` - Make voice channel private\n"
                f"`{ctx.prefix}voice unprivate` - Make voice channel public\n"
                f"`{ctx.prefix}voice time` - Your voice channel time\n"
                f"`{ctx.prefix}voice time @member` - Check a member's VC time\n"
                f"`{ctx.prefix}voice time all` - Voice time leaderboard\n"
                f"`{ctx.prefix}voice timereset` - Reset your VC time\n"
                f"`{ctx.prefix}voice timereset @member` - Reset a member's VC time\n"
                f"`{ctx.prefix}voice timereset all` - Reset all VC time data"
            )
            embed.add_field(name="Subcommands", value=sub_cmds_1, inline=False)
            embed.add_field(name="\u200b", value=sub_cmds_2, inline=False)
            embed.set_footer(text="cupidx HQ • cupidx", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    @vc.command(name="kick",
                help="Removes a user from the voice channel.",
                usage="voice kick <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _kick(self, ctx, *, member: discord.Member):
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is not connected to any voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        ch = member.voice.channel.mention
        await member.edit(voice_channel=None,
                          reason=f"Disconnected by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been disconnected from {ch}",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="kickall",
                help="Disconnect all members from the voice channel.",
                usage="voice kick all")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(move_members=True)
    
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _kickall(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channels.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            await member.edit(
                voice_channel=None,
                reason=f"Disconnect All Command Executed By: {str(ctx.author)}")
            count += 1
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"Disconnected {count} members from {ch}",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="mute",
                help="mute a member in voice channel .",
                usage="voice mute <member>")
    @commands.has_guild_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _mute(self, ctx, *, member: discord.Member = None):
        if member is None:
            embed = discord.Embed(
                title=f"{EMOJI_CROSS} Error",
                description="You need to mention a member to mute.",
                color=self.color
            )
            embed.set_footer(
                text=f"Requested by: {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            return await ctx.reply(embed=embed)

        if member.voice is None:
            embed = discord.Embed(
                title=f"{EMOJI_CROSS} Error",
                description=f"{str(member)} is not connected to any voice channels.",
                color=self.color
            )
            embed.set_footer(
                text=f"Requested by: {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            return await ctx.reply(embed=embed)

        if member.voice.mute:
            embed = discord.Embed(
                title=f"{EMOJI_CROSS} Error",
                description=f"{str(member)} is already muted in the voice channel.",
                color=self.color
            )
            embed.set_footer(
                text=f"Requested by: {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            return await ctx.reply(embed=embed)

        await member.edit(mute=True)
        embed = discord.Embed(
            title=f"{EMOJI_TICK} Success",
            description=f"{str(member)} has been muted in {member.voice.channel.mention}.",
            color=self.color
        )
        embed.set_footer(
            text=f"Requested by: {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        return await ctx.reply(embed=embed)

    @vc.command(name="unmute",
                help="Unmute a member in the voice channel.",
                usage="voice unmute <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(mute_members=True)
    #@commands.bot_has_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def vcunmute(self, ctx, *, member: discord.Member):
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if member.voice.mute == False:
            embed2 = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is already unmuted in the voice channel.",
                color=self.color)
            embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed2)
        ch = member.voice.channel.mention
        embed3 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been unmuted in {ch}",
            color=self.color)
        embed3.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed3.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        await member.edit(mute=False, reason=f"Unmuted by {str(ctx.author)}")
        return await ctx.reply(embed=embed3)

    @vc.command(name="muteall",
                help="Mute all members in a voice channel.",
                usage="voice muteall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _muteall(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.mute == False:
                await member.edit(
                    mute=True,
                    reason=
                    f"voice muteall Command Executed by {str(ctx.author)}")
                count += 1
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",
                               description=f"Muted {count} members in {ch}",
                               color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="unmuteall",
                help="Unmute all members in a voice channel.",
                usage="voice unmuteall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unmuteall(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.mute == True:
                await member.edit(
                    mute=False,
                    reason=
                    f"Voice unmuteall Command Executed by: {str(ctx.author)}")
                count += 1
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",
                               description=f"Unmuted {count} members in {ch}",
                               color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="deafen",
                help="Deafen a user in a voice channel.",
                usage="voice deafen <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(deafen_members=True)
    #@commands.bot_has_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _deafen(self, ctx, *, member: discord.Member):
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if member.voice.deaf == True:
            embed2 = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is already deafened in the voice channel",
                color=self.color)
            embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed2)
        ch = member.voice.channel.mention
        embed3 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been Deafened in {ch}",
            color=self.color)
        embed3.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed3.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        await member.edit(deafen=True, reason=f"Deafen by {str(ctx.author)}")
        return await ctx.reply(embed=embed3)

    @vc.command(name="undeafen",
                help="Undeafen a User in a voice channel .",
                usage="voice undeafen <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(deafen_members=True)
    #@commands.bot_has_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _undeafen(self, ctx, *, member: discord.Member):
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if member.voice.deaf == False:
            embed2 = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is already undeafened in the voice channel",
                color=self.color)
            embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed2)
        ch = member.voice.channel.mention
        embed3 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been undeafened in {ch}",
            color=self.color)
        embed3.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed3.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        await member.edit(deafen=False,
                          reason=f"Undeafen by {str(ctx.author)}")
        return await ctx.reply(embed=embed3)

    @vc.command(name="deafenall",
                help="Deafen all Ussr in a voice channel.",
                usage="voice deafenall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _deafenall(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.deaf == False:
                await member.edit(
                    deafen=True,
                    reason=
                    f"voice deafenall Command Executed by {str(ctx.author)}")
                count += 1
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",
                               description=f"Deafened {count} members in {ch}",
                               color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                           icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="undeafenall",
                help="undeafen all member in a voice channel .",
                usage="voice undeafenall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _undeafall(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected in any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.deaf == True:
                await member.edit(
                    deafen=False,
                    reason=
                    f"Voice undeafenall Command Executed by: {str(ctx.author)}")
                count += 1
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"Undeafened {count} members in {ch}",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                           icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="moveall",
                help="Move all members from the voice channel to the specified voice channel.",
                usage="voice moveall <voice channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(move_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _moveall(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        try:
            ch = ctx.author.voice.channel.mention
            nch = channel.mention
            count = 0
            for member in ctx.author.voice.channel.members:
                await member.edit(
                    voice_channel=channel,
                    reason=
                    f"voice moveall Command Executed by: {str(ctx.author)}")
                count += 1
            embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

                description=f"{count} Members moved from {ch} to {nch}",
                color=self.color)
            embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            await ctx.reply(embed=embed2)
        except:
            embed3 = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=f"Invalid Voice channel provided",
                color=self.color)
            embed3.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed3.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            await ctx.reply(embed=embed3)

    

    @vc.command(name="pullall",
                help="Move all members of ALL voice channels to a specified voice channel.",
                usage="voice pullall <channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(move_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _pullall(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any of the voice channel",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        count = 0
        for vc in ctx.guild.voice_channels:
            for member in vc.members:
                if member != ctx.author:
                    try:
                        await member.edit(
                            voice_channel=channel,
                            reason=f"Pullall Command Executed by: {str(ctx.author)}")
                        count += 1
                    except:
                        pass
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",
                               description=f"Moved {count} members to {channel.mention}",
                               color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)


    @vc.command(name="move",
                help="Move a member from one voice channel to another.",
                usage="voice move <member> <channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(move_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _move(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS}Error",

                description=
                f"{str(member)} is not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if channel == member.voice.channel:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is already in {channel.mention}.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        await member.edit(voice_channel=channel,
                          reason=f"Moved by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been moved to {channel.mention}",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)
        

    @vc.command(name="pull",
                help="Pull a member from one voice channel to yours.",
                usage="voice pull <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    #@commands.bot_has_permissions(move_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _pull(self, ctx, member: discord.Member):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if member.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        if member.voice.channel == ctx.author.voice.channel:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                f"{str(member)} is already in your voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        await member.edit(voice_channel=ctx.author.voice.channel,
                          reason=f"Pulled by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{str(member)} has been pulled to your voice channel.",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="lock",
                help="Locks the voice channel so no one can join.",
                usage="voice lock")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _lock(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role,
                                                       connect=False,
                                                       reason=f"Locked by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{ch} has been locked.",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="unlock",
                help="Unlocks the voice channel so anyone can join.",
                usage="voice unlock")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unlock(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role,
                                                       connect=True,
                                                       reason=f"Unlocked by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{ch} has been unlocked.",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="private",
                help="Makes the voice channel private.",
                usage="voice private")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _private(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role,
                                                       connect=False,
                                                       view_channel=False,
                                                       reason=f"Made private by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{ch} has been made private.",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    @vc.command(name="unprivate",
                help="Makes the voice channel public.",
                usage="voice unprivate")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unprivate(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title=f"{EMOJI_CROSS} Error",

                description=
                "You are not connected to any voice channel.",
                color=self.color)
            embed.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            return await ctx.reply(embed=embed)
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role,
                                                       connect=True,
                                                       view_channel=True,
                                                       reason=f"Made public by {str(ctx.author)}")
        embed2 = discord.Embed(title=f"{EMOJI_TICK} Success",

            description=f"{ch} has been made public.",
            color=self.color)
        embed2.set_footer(text=f"Requested by: {ctx.author}",
                               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed2.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        return await ctx.reply(embed=embed2)

    # ─────────────────────────────────────────────
    #  VC TIME TRACKER  –  voice state listener
    # ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = member.guild.id
        user_id  = member.id
        now      = datetime.datetime.utcnow()

        # User joined a VC
        if before.channel is None and after.channel is not None:
            self.live_joins.setdefault(guild_id, {})[user_id] = now

        # User left a VC
        elif before.channel is not None and after.channel is None:
            joined_at = self.live_joins.get(guild_id, {}).pop(user_id, None)
            if joined_at:
                duration = int((now - joined_at).total_seconds())
                date_str = now.strftime("%d/%m/%Y")
                await self._add_session(guild_id, user_id, date_str, duration)

    # ─────────────────────────────────────────────
    #  Helper: seconds  →  "Xh Ym Zs"
    # ─────────────────────────────────────────────
    @staticmethod
    def _fmt(seconds: int) -> str:
        h, rem = divmod(seconds, 3600)
        m, s   = divmod(rem, 60)
        parts  = []
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    @vc.command(
        name="time",
        aliases=["voicetime", "vctime"],
        help="Check voice channel time of a member.",
        usage="voice time [all | @member]")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _vctime(self, ctx, *, target: str = None):

        guild_id = ctx.guild.id

        # ── vctime all → full server leaderboard ────────────────────────
        if target and target.lower() == "all":
            all_users = await self._get_all_users(guild_id)
            if not all_users:
                embed = discord.Embed(
                    title=f"{EMOJI_CROSS} Error",
                    description="No voice time data recorded for this server yet.",
                    color=self.color)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                embed.set_footer(text=f"Requested by: {ctx.author}",
                                 icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                return await ctx.reply(embed=embed)

            # Collect all unique dates (last 7 days) across guild
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%d/%m/%Y")
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT DISTINCT date FROM vc_sessions WHERE guild_id = ? AND date >= ? ORDER BY date DESC",
                    (guild_id, cutoff)
                ) as cursor:
                    all_dates = [r[0] for r in await cursor.fetchall()][:5]

            class DateSelectView(discord.ui.View):
                def __init__(self_v, cog, all_users_, all_dates_, ctx_):
                    super().__init__(timeout=120)
                    self_v.cog        = cog
                    self_v.all_users_ = all_users_   # [(user_id, total)]
                    self_v.all_dates_ = all_dates_
                    self_v.ctx_       = ctx_
                    self_v.page       = 0
                    self_v.mode       = "total"
                    self_v._build_buttons()

                def _build_buttons(self_v):
                    self_v.clear_items()
                    prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev", row=0)
                    next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, custom_id="next", row=0)
                    prev_btn.callback = self_v.prev_page
                    next_btn.callback = self_v.next_page
                    self_v.add_item(prev_btn)
                    self_v.add_item(next_btn)
                    all_btn = discord.ui.Button(label="All Time", style=discord.ButtonStyle.success, custom_id="alltime", row=0)
                    async def all_cb(interaction, v=self_v):
                        if interaction.user != v.ctx_.author:
                            return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                        v.mode = "total"
                        v.page = 0
                        await interaction.response.edit_message(embed=await v._build_embed(), view=v)
                    all_btn.callback = all_cb
                    self_v.add_item(all_btn)
                    for date in self_v.all_dates_:
                        btn = discord.ui.Button(label=date, style=discord.ButtonStyle.primary, custom_id=f"d_{date}", row=1)
                        async def date_cb(interaction, d=date, v=self_v):
                            if interaction.user != v.ctx_.author:
                                return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                            v.mode = d
                            v.page = 0
                            await interaction.response.edit_message(embed=await v._build_embed(), view=v)
                        btn.callback = date_cb
                        self_v.add_item(btn)

                async def _get_sorted(self_v):
                    if self_v.mode == "total":
                        return self_v.all_users_   # [(user_id, total)]
                    rows = await self_v.cog._get_date_leaderboard(self_v.ctx_.guild.id, self_v.mode)
                    return rows  # [(user_id, duration)]

                async def _build_embed(self_v):
                    mode_label = "Last 7 Days" if self_v.mode == "total" else self_v.mode
                    embed = discord.Embed(
                        title=f"{EMOJI_VOICE} Voice Time — {mode_label}",
                        color=0x134E5E)
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                    sorted_ = await self_v._get_sorted()
                    if not sorted_:
                        embed.description = "No data available for this date."
                        return embed
                    chunk_ = 10
                    start  = self_v.page * chunk_
                    slice_ = sorted_[start:start + chunk_]
                    lines  = []
                    for rank, (uid, dur) in enumerate(slice_, start=start + 1):
                        live = ""
                        if self_v.mode == "total":
                            joined_at = self_v.cog.live_joins.get(self_v.ctx_.guild.id, {}).get(uid)
                            if joined_at:
                                live_secs = int((datetime.datetime.utcnow() - joined_at).total_seconds())
                                live = f" (Live: +{self_v.cog._fmt(live_secs)})"
                        member_ = self_v.ctx_.guild.get_member(uid)
                        name_   = member_.display_name if member_ else f"User#{uid}"
                        lines.append(f"`#{rank}` **{name_}** — {self_v.cog._fmt(dur)}{live}")
                    total_pages = max(1, (len(sorted_) + chunk_ - 1) // chunk_)
                    embed.description = "\n".join(lines)
                    embed.set_footer(
                        text=f"Page {self_v.page + 1}/{total_pages} • Last 7 days • Requested by: {self_v.ctx_.author}",
                        icon_url=self_v.ctx_.author.avatar.url if self_v.ctx_.author.avatar else self_v.ctx_.author.default_avatar.url)
                    return embed

                async def prev_page(self_v, interaction):
                    if interaction.user != self_v.ctx_.author:
                        return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    sorted_ = await self_v._get_sorted()
                    total_pages = max(1, (len(sorted_) + 9) // 10)
                    self_v.page = (self_v.page - 1) % total_pages
                    await interaction.response.edit_message(embed=await self_v._build_embed(), view=self_v)

                async def next_page(self_v, interaction):
                    if interaction.user != self_v.ctx_.author:
                        return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    sorted_ = await self_v._get_sorted()
                    total_pages = max(1, (len(sorted_) + 9) // 10)
                    self_v.page = (self_v.page + 1) % total_pages
                    await interaction.response.edit_message(embed=await self_v._build_embed(), view=self_v)

            view = DateSelectView(self, all_users, all_dates, ctx)
            return await ctx.reply(embed=await view._build_embed(), view=view)

        # ── vctime @user  OR  vctime (self) ─────────────────────────────
        member = None
        if target:
            try:
                member = await commands.MemberConverter().convert(ctx, target)
            except commands.BadArgument:
                embed = discord.Embed(
                    title=f"{EMOJI_CROSS} Error",
                    description="Member not found. Please mention a valid user.",
                    color=self.color)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                embed.set_footer(text=f"Requested by: {ctx.author}",
                                 icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                return await ctx.reply(embed=embed)
        else:
            member = ctx.author

        sessions  = await self._get_sessions(guild_id, member.id)  # [(date, duration)]
        total     = sum(d for _, d in sessions)
        live_secs = 0
        joined_at = self.live_joins.get(guild_id, {}).get(member.id)
        if joined_at:
            live_secs = int((datetime.datetime.utcnow() - joined_at).total_seconds())

        total_with_live = total + live_secs
        today_str       = datetime.datetime.utcnow().strftime("%d/%m/%Y")
        today_total     = sum(d for dt, d in sessions if dt == today_str) + live_secs

        if member.voice and member.voice.channel:
            status = f"Currently in {member.voice.channel.name} (Live)"
        else:
            status = "Not in a voice channel"

        embed = discord.Embed(
            title=f"{EMOJI_VOICE} Voice Time — {member.display_name}",
            color=0x134E5E)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member",         value=member.mention,             inline=True)
        embed.add_field(name="Total VC Time",  value=self._fmt(total_with_live), inline=True)
        embed.add_field(name="Today",          value=self._fmt(today_total),     inline=True)
        embed.add_field(name="Status",         value=status,                     inline=False)
        embed.add_field(name="Sessions (7d)",  value=str(len(sessions)),         inline=True)

        if sessions:
            sess_lines = "\n".join(f"`{dt}` — {self._fmt(dur)}" for dt, dur in sessions[:5])
            embed.add_field(name="Recent Sessions", value=sess_lines, inline=False)
        else:
            embed.add_field(name="Recent Sessions", value="No sessions recorded yet.", inline=False)

        embed.set_footer(text=f"Data shown for last 7 days • Requested by: {ctx.author}",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        # Date buttons for single user
        class UserDateView(discord.ui.View):
            def __init__(self_v, cog_, member_, sessions_, ctx_):
                super().__init__(timeout=120)
                self_v.cog_      = cog_
                self_v.member_   = member_
                self_v.sessions_ = sessions_
                self_v.ctx_      = ctx_
                unique_dates = list(dict.fromkeys(dt for dt, _ in sessions_))[:5]
                for date in unique_dates:
                    btn = discord.ui.Button(label=date, style=discord.ButtonStyle.primary, custom_id=f"u_{date}")
                    async def cb(interaction, d=date, v=self_v):
                        if interaction.user != v.ctx_.author:
                            return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                        dur = sum(dr for dt, dr in v.sessions_ if dt == d)
                        e2  = discord.Embed(
                            title=f"{EMOJI_VOICE} Voice Time — {v.member_.display_name} | {d}",
                            color=0x134E5E)
                        e2.set_thumbnail(url=v.member_.display_avatar.url)
                        e2.add_field(name="Date",    value=d,                    inline=True)
                        e2.add_field(name="VC Time", value=v.cog_._fmt(dur),     inline=True)
                        e2.set_footer(
                            text=f"Requested by: {v.ctx_.author}",
                            icon_url=v.ctx_.author.avatar.url if v.ctx_.author.avatar else v.ctx_.author.default_avatar.url)
                        await interaction.response.edit_message(embed=e2, view=v)
                    btn.callback = cb
                    self_v.add_item(btn)

        view2 = UserDateView(self, member, sessions, ctx)
        return await ctx.reply(embed=embed, view=view2)

    # ─────────────────────────────────────────────
    #  VC TIME RESET COMMAND
    # ─────────────────────────────────────────────
    @vc.command(
        name="timereset",
        aliases=["vctimereseт", "resettime"],
        help="Reset voice time data.",
        usage="voice timereset [all | @member]")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _vctimereset(self, ctx, *, target: str = None):
        guild_id = ctx.guild.id

        if target and target.lower() == "all":
            await self._reset_guild(guild_id)
            embed = discord.Embed(
                title=f"{EMOJI_TICK} Success",
                description="All voice time data for this server has been reset.",
                color=self.color)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
            embed.set_footer(text=f"Requested by: {ctx.author}",
                             icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        member = None
        if target:
            try:
                member = await commands.MemberConverter().convert(ctx, target)
            except commands.BadArgument:
                embed = discord.Embed(
                    title=f"{EMOJI_CROSS} Error",
                    description="Member not found. Please mention a valid user.",
                    color=self.color)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                embed.set_footer(text=f"Requested by: {ctx.author}",
                                 icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                return await ctx.reply(embed=embed)
        else:
            member = ctx.author

        await self._reset_user(guild_id, member.id)
        embed = discord.Embed(
            title=f"{EMOJI_TICK} Success",
            description=f"Voice time data for {member.mention} has been reset.",
            color=self.color)
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
        embed.set_footer(text=f"Requested by: {ctx.author}",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        return await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Voice(bot))


"""
@Author: Sonu Jana
    + Discord: me.sonu
    + Community: https://discord.gg/odx (Olympus Development)
    + for any queries reach out Community or DM me.
"""