import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *

EMOJI_TICK = "<:CupidXtick1:1474369967271968949>"
EMOJI_WARN = "<:icons_warning:1327829522573430864>"


class NotifCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/notify.db"
        self.loop_task = self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL UNIQUE,
                    role_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL
                )
            ''')
            await db.commit()

    # ── GROUP ──

    @commands.group(invoke_without_command=True)
    async def setnotif(self, ctx):
        embed = discord.Embed(
            title="🔔 Notification Manager",
            description="Set up stream notifications for Twitch and YouTube.",
            color=0xFCD005
        )
        embed.add_field(
            name="📋 Subcommands",
            value=(
                f"`{ctx.prefix}setnotif twitch @role #channel` — Set Twitch notifications\n"
                f"`{ctx.prefix}setnotif youtube @role #channel` — Set YouTube notifications\n"
                f"`{ctx.prefix}setnotif list` — View current settings\n"
                f"`{ctx.prefix}setnotif reset` — Remove all notifications"
            ),
            inline=False
        )
        embed.set_footer(text="© CupidX HQ")
        await ctx.send(embed=embed)

    # ── TWITCH ──

    @setnotif.command()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def twitch(self, ctx, role: discord.Role, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM notifications WHERE type = ?', ('twitch',)) as cur:
                row = await cur.fetchone()
                if row:
                    embed = discord.Embed(
                        title=f"{EMOJI_WARN} Already Configured",
                        description="Twitch notification is already set. Use `setnotif reset` to remove it first.",
                        color=0xFCD005
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute(
                'INSERT INTO notifications (type, role_id, channel_id) VALUES (?, ?, ?)',
                ('twitch', role.id, channel.id)
            )
            await db.commit()

        embed = discord.Embed(
            title=f"📺 Twitch Notifications Set",
            description=f"{EMOJI_TICK} Notifications will ping {role.mention} in {channel.mention}.",
            color=0xFCD005
        )
        embed.set_footer(text="© CupidX HQ")
        await ctx.reply(embed=embed)

    # ── YOUTUBE ──

    @setnotif.command()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def youtube(self, ctx, role: discord.Role, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM notifications WHERE type = ?', ('youtube',)) as cur:
                row = await cur.fetchone()
                if row:
                    embed = discord.Embed(
                        title=f"{EMOJI_WARN} Already Configured",
                        description="YouTube notification is already set. Use `setnotif reset` to remove it first.",
                        color=0xFCD005
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute(
                'INSERT INTO notifications (type, role_id, channel_id) VALUES (?, ?, ?)',
                ('youtube', role.id, channel.id)
            )
            await db.commit()

        embed = discord.Embed(
            title=f"▶️ YouTube Notifications Set",
            description=f"{EMOJI_TICK} Notifications will ping {role.mention} in {channel.mention}.",
            color=0xFCD005
        )
        embed.set_footer(text="© CupidX HQ")
        await ctx.reply(embed=embed)

    # ── LIST ──

    @setnotif.command()
    async def list(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM notifications') as cur:
                rows = await cur.fetchall()

        if not rows:
            embed = discord.Embed(
                title="🔕 No Notifications Set",
                description="No Twitch or YouTube notifications are configured.",
                color=0xFCD005
            )
            await ctx.reply(embed=embed)
            return

        embed = discord.Embed(title="🔔 Current Notifications", color=0xFCD005)
        for row in rows:
            notif_type = row[1].capitalize()
            role = ctx.guild.get_role(row[2])
            channel = ctx.guild.get_channel(row[3])
            emoji = "📺" if row[1] == "twitch" else "▶️"
            if role and channel:
                embed.add_field(
                    name=f"{emoji} {notif_type}",
                    value=f"📣 Role: {role.mention}\n📢 Channel: {channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{emoji} {notif_type}",
                    value="⚠️ Role or channel not found.",
                    inline=False
                )
        embed.set_footer(text="© CupidX HQ")
        await ctx.reply(embed=embed)

    # ── RESET ──

    @setnotif.command()
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM notifications WHERE type IN (?, ?)", ('twitch', 'youtube'))
            await db.commit()

        embed = discord.Embed(
            title=f"🗑️ Notifications Reset",
            description=f"{EMOJI_TICK} All Twitch and YouTube notifications have been removed.",
            color=0xFCD005
        )
        embed.set_footer(text="© CupidX HQ")
        await ctx.send(embed=embed)

    # ── LISTENER ──

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        streaming = next(
            (a for a in after.activities if isinstance(a, discord.Streaming)), None
        )
        if not streaming:
            return

        stream_type = (
            "twitch" if "twitch" in streaming.url.lower()
            else "youtube" if "youtube" in streaming.url.lower()
            else None
        )
        if not stream_type:
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT role_id, channel_id FROM notifications WHERE type = ?', (stream_type,)
            ) as cur:
                row = await cur.fetchone()

        if not row:
            return

        role = after.guild.get_role(row[0])
        channel = after.guild.get_channel(row[1])
        if not role or not channel:
            return

        emoji = "📺" if stream_type == "twitch" else "▶️"
        embed = discord.Embed(
            title=f"{emoji} {after.display_name} is now LIVE!",
            description=f"{after.mention} started streaming on **{stream_type.capitalize()}**!",
            color=0x9B59B6 if stream_type == "twitch" else 0xFF0000
        )
        embed.add_field(name="🎮 Stream Title", value=streaming.name or "No title", inline=False)
        embed.add_field(name="🔗 Watch Now", value=streaming.url, inline=False)
        embed.set_footer(text="© CupidX HQ")
        await channel.send(content=role.mention, embed=embed)


async def setup(bot):
    await bot.add_cog(NotifCommands(bot))
