import discord
from discord.ext import commands
import aiosqlite
import os
import time
from datetime import datetime
from typing import List, Union, Optional
from utils import Paginator, DescriptionEmbedPaginator

# ─────────────────────────────────────────────
#              CupidX Branding
# ─────────────────────────────────────────────
color_primary   = 0x000000
color_danger    = 0x000000
color_success   = 0x000000
color_warning   = 0x000000
# ─────────────────────────────────────────────
#              ALL EMOJIS  (top)
# ─────────────────────────────────────────────
emojitick       = "<:CupidXtick1:1474369967271968949>"
emojicross      = "<:CupidXCross:1473996646873436336>"
emojiwarn       = "<:CupidXWarning:1474348304186867784>"
emojiblacklist  = "🚫"
emojiuser       = "👤"
emojiguild      = "🏛️"
emojiid         = "🆔"
emojiowner      = "👑"
emojimembers    = "👥"
emojireason     = "📝"
emojitime       = "🕐"
emojiby         = "🛡️"
emojistats      = "📊"
emojiverified   = "✅"
emojiinfo       = "ℹ️"
emojicalendar   = "📅"

db_path = "db/block.db"

# ─────────────────────────────────────────────
#              Embed Helper
# ─────────────────────────────────────────────
def cupidx_embed(title: str, description: str = None, color: int = color_primary):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name="CupidX Help Center")
    embed.set_footer(text="CupidX")
    return embed

# ─────────────────────────────────────────────
#              Timestamp Helper
# ─────────────────────────────────────────────
def fmt_time(ts) -> str:
    """Convert UNIX timestamp (int or str) → readable date string."""
    try:
        if not ts:
            return "Unknown"
        return datetime.utcfromtimestamp(int(ts)).strftime("%d %b %Y  %H:%M UTC")
    except (ValueError, TypeError, OSError):
        return "Unknown"


class Block(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_db())

    # ──────────────────────────────────────────
    #  DB INIT  — upgraded schema
    # ──────────────────────────────────────────
    async def initialize_db(self) -> None:
        """Initialize blacklist database with full info columns."""
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        async with aiosqlite.connect(db_path) as db:

            # USER blacklist
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_blacklist (
                    user_id         INTEGER PRIMARY KEY,
                    username        TEXT    DEFAULT "Unknown",
                    display_name    TEXT    DEFAULT "Unknown",
                    reason          TEXT    DEFAULT "No reason provided",
                    blacklisted_by  INTEGER DEFAULT NULL,
                    timestamp       INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # GUILD blacklist  — full info stored
            await db.execute('''
                CREATE TABLE IF NOT EXISTS guild_blacklist (
                    guild_id        INTEGER PRIMARY KEY,
                    guild_name      TEXT    DEFAULT "Unknown",
                    owner_id        INTEGER DEFAULT NULL,
                    member_count    INTEGER DEFAULT 0,
                    reason          TEXT    DEFAULT "No reason provided",
                    blacklisted_by  INTEGER DEFAULT NULL,
                    timestamp       INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # Run migrations for existing DBs (add new cols if missing)
            for col, definition in [
                ("username",       "TEXT DEFAULT 'Unknown'"),
                ("display_name",   "TEXT DEFAULT 'Unknown'"),
                ("reason",         "TEXT DEFAULT 'No reason provided'"),
                ("blacklisted_by", "INTEGER DEFAULT NULL"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE user_blacklist ADD COLUMN {col} {definition}")
                except Exception:
                    pass

            for col, definition in [
                ("guild_name",     "TEXT DEFAULT 'Unknown'"),
                ("owner_id",       "INTEGER DEFAULT NULL"),
                ("member_count",   "INTEGER DEFAULT 0"),
                ("reason",         "TEXT DEFAULT 'No reason provided'"),
                ("blacklisted_by", "INTEGER DEFAULT NULL"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE guild_blacklist ADD COLUMN {col} {definition}")
                except Exception:
                    pass

            await db.commit()

    # ══════════════════════════════════════════
    #  ROOT:  .bl / .blacklist
    # ══════════════════════════════════════════
    @commands.group(name="blacklist", aliases=["bl"], invoke_without_command=True)
    @commands.is_owner()
    async def blacklist(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = cupidx_embed(
                f"{emojiblacklist} Blacklist Management",
                f"Manage global user and guild blacklists for **CupidX**."
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)

            async with aiosqlite.connect(db_path) as db:
                uc = await (await db.execute("SELECT COUNT(*) FROM user_blacklist")).fetchone()
                gc = await (await db.execute("SELECT COUNT(*) FROM guild_blacklist")).fetchone()

            embed.add_field(
                name=f"{emojistats} Statistics",
                value=(
                    f"{emojiuser} Blacklisted Users  : **{uc[0]}**\n"
                    f"{emojiguild} Blacklisted Guilds : **{gc[0]}**"
                ),
                inline=False
            )
            embed.add_field(
                name=f"{emojiinfo} Subcommands",
                value=(
                    f"`{ctx.prefix}bl user add/remove/show` — Manage user blacklist\n"
                    f"`{ctx.prefix}bl guild add/remove/show` — Manage guild blacklist"
                ),
                inline=False
            )
            embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    # ══════════════════════════════════════════
    #  USER GROUP
    # ══════════════════════════════════════════
    @blacklist.group(name="user", invoke_without_command=True)
    @commands.is_owner()
    async def user(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = cupidx_embed(
                f"{emojiuser} User Blacklist",
                "Manage the global user blacklist."
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            embed.add_field(
                name=f"{emojiinfo} Subcommands",
                value=(
                    f"`{ctx.prefix}bl user add <@user> [reason]` — Add user\n"
                    f"`{ctx.prefix}bl user remove <@user>` — Remove user\n"
                    f"`{ctx.prefix}bl user show` — List all blacklisted users"
                ),
                inline=False
            )
            embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    # ── user add ──────────────────────────────
    @user.command(name="add")
    @commands.is_owner()
    async def add_user(self, ctx: commands.Context, user: discord.User, *, reason: str = "No reason provided"):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT 1 FROM user_blacklist WHERE user_id = ?', (user.id,))
            if await cursor.fetchone():
                embed = cupidx_embed(
                    f"{emojiwarn} User Already Blacklisted",
                    f"{user.mention} (`{user.id}`) is already on the blacklist.",
                    color=color_warning
                )
                await ctx.reply(embed=embed)
                return

            await db.execute(
                '''INSERT INTO user_blacklist
                   (user_id, username, display_name, reason, blacklisted_by)
                   VALUES (?, ?, ?, ?, ?)''',
                (user.id, str(user), user.display_name, reason, ctx.author.id)
            )
            await db.commit()

        embed = cupidx_embed(
            f"{emojitick} User Blacklisted",
            f"{user.mention} has been added to the global blacklist.",
            color=color_danger
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name=f"{emojiuser} Username",      value=f"`{user}`",           inline=True)
        embed.add_field(name=f"{emojiid}   User ID",       value=f"`{user.id}`",         inline=True)
        embed.add_field(name=f"{emojireason} Reason",      value=reason,                 inline=False)
        embed.add_field(name=f"{emojiby} Blacklisted By",  value=ctx.author.mention,     inline=True)
        embed.add_field(name=f"{emojicalendar} Date",      value=fmt_time(int(time.time())), inline=True)
        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ── user remove ───────────────────────────
    @user.command(name="remove")
    @commands.is_owner()
    async def remove_user(self, ctx: commands.Context, user: discord.User):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT 1 FROM user_blacklist WHERE user_id = ?', (user.id,))
            if not await cursor.fetchone():
                embed = cupidx_embed(
                    f"{emojicross} User Not Blacklisted",
                    f"{user.mention} (`{user.id}`) is not in the blacklist.",
                    color=color_danger
                )
                await ctx.reply(embed=embed)
                return

            await db.execute('DELETE FROM user_blacklist WHERE user_id = ?', (user.id,))
            await db.commit()

        embed = cupidx_embed(
            f"{emojitick} User Unblacklisted",
            f"{user.mention} has been removed from the blacklist.",
            color=color_success
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name=f"{emojiuser} Username", value=f"`{user}`",   inline=True)
        embed.add_field(name=f"{emojiid}   User ID",  value=f"`{user.id}`", inline=True)
        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ── user show ─────────────────────────────
    @user.command(name="show", aliases=["list"])
    @commands.is_owner()
    async def show_users(self, ctx: commands.Context):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                'SELECT user_id, username, reason, blacklisted_by, timestamp FROM user_blacklist ORDER BY timestamp DESC'
            )
            rows = await cursor.fetchall()

        if not rows:
            embed = cupidx_embed(
                f"{emojicross} No Blacklisted Users",
                "The user blacklist is currently empty.",
                color=color_warning
            )
            await ctx.reply(embed=embed)
            return

        user_list = []
        for uid, uname, reason, by, ts in rows:
            by_str  = f"<@{by}>" if by else "Unknown"
            dt_str  = fmt_time(ts) if ts else "Unknown"
            user_list.append(
                f"[{uname or 'Unknown'}](https://discord.com/users/{uid})  `{uid}`\n"
                f"{emojireason} {reason}  •  {emojiby} {by_str}  •  {emojicalendar} {dt_str}"
            )

        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=user_list,
            title=f"{emojiuser} Blacklisted Users [{len(user_list)}]",
            description="",
            per_page=5,
            color=color_primary),
            ctx=ctx)
        await paginator.paginate()

    # ══════════════════════════════════════════
    #  GUILD GROUP
    # ══════════════════════════════════════════
    @blacklist.group(name="guild", invoke_without_command=True)
    @commands.is_owner()
    async def guild_group(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = cupidx_embed(
                f"{emojiguild} Guild Blacklist",
                "Manage the global guild blacklist."
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            embed.add_field(
                name=f"{emojiinfo} Subcommands",
                value=(
                    f"`{ctx.prefix}bl guild add <guild_id> [reason]` — Add guild\n"
                    f"`{ctx.prefix}bl guild remove <guild_id>` — Remove guild\n"
                    f"`{ctx.prefix}bl guild show` — List all blacklisted guilds\n"
                    f"`{ctx.prefix}bl guild info <guild_id>` — Full info of a blacklisted guild"
                ),
                inline=False
            )
            embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    # ── guild add ─────────────────────────────
    @guild_group.command(name="add")
    @commands.is_owner()
    async def add_guild(self, ctx: commands.Context, guild_id: int, *, reason: str = "No reason provided"):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT 1 FROM guild_blacklist WHERE guild_id = ?', (guild_id,))
            if await cursor.fetchone():
                embed = cupidx_embed(
                    f"{emojiwarn} Guild Already Blacklisted",
                    f"Guild `{guild_id}` is already on the blacklist.",
                    color=color_warning
                )
                await ctx.reply(embed=embed)
                return

            # fetch_guild = direct Discord API, cache pe depend nahi
            try:
                g = await self.bot.fetch_guild(guild_id)
                guild_name   = g.name
                owner_id     = g.owner_id
                member_count = g.approximate_member_count or 0
            except Exception:
                g            = None
                guild_name   = "Unknown (Bot not in guild)"
                owner_id     = None
                member_count = 0

            await db.execute(
                '''INSERT INTO guild_blacklist
                   (guild_id, guild_name, owner_id, member_count, reason, blacklisted_by)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (guild_id, guild_name, owner_id, member_count, reason, ctx.author.id)
            )
            await db.commit()

        embed = cupidx_embed(
            f"{emojitick} Guild Blacklisted",
            f"Guild **{guild_name}** has been added to the global blacklist.",
            color=color_danger
        )
        if g and g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name=f"{emojiguild} Guild Name",    value=f"`{guild_name}`",                     inline=True)
        embed.add_field(name=f"{emojiid}   Guild ID",       value=f"`{guild_id}`",                       inline=True)
        embed.add_field(name=f"{emojiowner} Owner",         value=f"<@{owner_id}>" if owner_id else "Unknown", inline=True)
        embed.add_field(name=f"{emojimembers} Members",     value=f"`{member_count}`",                   inline=True)
        embed.add_field(name=f"{emojireason} Reason",       value=reason,                                inline=False)
        embed.add_field(name=f"{emojiby} Blacklisted By",   value=ctx.author.mention,                    inline=True)
        embed.add_field(name=f"{emojicalendar} Date",       value=fmt_time(int(time.time())),             inline=True)
        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ── guild remove ──────────────────────────
    @guild_group.command(name="remove")
    @commands.is_owner()
    async def remove_guild(self, ctx: commands.Context, guild_id: int):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                'SELECT guild_name FROM guild_blacklist WHERE guild_id = ?', (guild_id,)
            )
            row = await cursor.fetchone()
            if not row:
                embed = cupidx_embed(
                    f"{emojicross} Guild Not Blacklisted",
                    f"Guild `{guild_id}` is not in the blacklist.",
                    color=color_danger
                )
                await ctx.reply(embed=embed)
                return

            guild_name = row[0] or "Unknown"
            await db.execute('DELETE FROM guild_blacklist WHERE guild_id = ?', (guild_id,))
            await db.commit()

        embed = cupidx_embed(
            f"{emojitick} Guild Unblacklisted",
            f"Guild **{guild_name}** (`{guild_id}`) has been removed from the blacklist.",
            color=color_success
        )
        embed.add_field(name=f"{emojiguild} Guild Name", value=f"`{guild_name}`", inline=True)
        embed.add_field(name=f"{emojiid}   Guild ID",    value=f"`{guild_id}`",   inline=True)
        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ── guild show ────────────────────────────
    @guild_group.command(name="show", aliases=["list"])
    @commands.is_owner()
    async def show_guilds(self, ctx: commands.Context):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                '''SELECT guild_id, guild_name, owner_id, member_count,
                          reason, blacklisted_by, timestamp
                   FROM guild_blacklist ORDER BY timestamp DESC'''
            )
            rows = await cursor.fetchall()

        if not rows:
            embed = cupidx_embed(
                f"{emojicross} No Blacklisted Guilds",
                "The guild blacklist is currently empty.",
                color=color_warning
            )
            await ctx.reply(embed=embed)
            return

        guild_list = []
        async with aiosqlite.connect(db_path) as db2:
            for gid, gname, owner_id, members, reason, by, ts in rows:
                # fetch_guild = direct Discord API call, cache pe depend nahi karta
                try:
                    g = await self.bot.fetch_guild(int(gid))
                    real_name    = g.name
                    real_owner   = g.owner_id
                    real_members = g.approximate_member_count or members or 0
                    # DB mein permanently save karo
                    await db2.execute(
                        "UPDATE guild_blacklist SET guild_name=?, owner_id=?, member_count=? WHERE guild_id=?",
                        (real_name, real_owner, real_members, gid)
                    )
                    await db2.commit()
                except Exception:
                    # Bot guild mein nahi ya API error
                    real_name    = gname    or "Unknown"
                    real_owner   = owner_id
                    real_members = members  or 0

                by_str  = f"<@{by}>"          if by          else "Unknown"
                own_str = f"<@{real_owner}>"   if real_owner  else "Unknown"
                dt_str  = fmt_time(ts)          if ts          else "Unknown"
                guild_list.append(
                    f"**{real_name}**  `{gid}`\n"
                    f"{emojiowner} Owner: {own_str}  {emojimembers} Members: `{real_members}`\n"
                    f"{emojireason} {reason or 'No reason provided'}  •  {emojiby} {by_str}  •  {emojicalendar} {dt_str}"
                )

        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=guild_list,
            title=f"{emojiguild} Blacklisted Guilds [{len(guild_list)}]",
            description="",
            per_page=4,
            color=color_primary),
            ctx=ctx)
        await paginator.paginate()

    # ── guild update (refresh DB from live cache) ─
    @guild_group.command(name="update")
    @commands.is_owner()
    async def update_guild(self, ctx: commands.Context, guild_id: int):
        """Purani Unknown entry ko live data se refresh karo."""
        try:
            g = await self.bot.fetch_guild(guild_id)
        except Exception:
            embed = cupidx_embed(
                f"{emojiwarn} Fetch Failed",
                f"Guild `{guild_id}` ka data fetch nahi ho saka. Bot is guild mein nahi hai ya invalid ID hai.",
                color=color_warning
            )
            await ctx.reply(embed=embed)
            return

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT 1 FROM guild_blacklist WHERE guild_id = ?', (guild_id,))
            if not await cursor.fetchone():
                embed = cupidx_embed(
                    f"{emojicross} Guild Not Found",
                    f"Guild `{guild_id}` blacklist mein nahi hai.",
                    color=color_danger
                )
                await ctx.reply(embed=embed)
                return

            await db.execute(
                "UPDATE guild_blacklist SET guild_name=?, owner_id=?, member_count=? WHERE guild_id=?",
                (g.name, g.owner_id, g.member_count, guild_id)
            )
            await db.commit()

        embed = cupidx_embed(
            f"{emojitick} Guild Info Updated",
            f"Guild **{g.name}** ka data refresh ho gaya.",
            color=color_success
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name=f"{emojiguild} Guild Name",  value=f"`{g.name}`",        inline=True)
        embed.add_field(name=f"{emojiid}   Guild ID",     value=f"`{guild_id}`",       inline=True)
        embed.add_field(name=f"{emojiowner} Owner",       value=f"<@{g.owner_id}>",   inline=True)
        embed.add_field(name=f"{emojimembers} Members",   value=f"`{g.member_count}`", inline=True)
        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ── guild info ────────────────────────────
    @guild_group.command(name="info")
    @commands.is_owner()
    async def guild_info(self, ctx: commands.Context, guild_id: int):
        """Show full detailed info of a single blacklisted guild."""
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                '''SELECT guild_id, guild_name, owner_id, member_count,
                          reason, blacklisted_by, timestamp
                   FROM guild_blacklist WHERE guild_id = ?''',
                (guild_id,)
            )
            row = await cursor.fetchone()

        if not row:
            embed = cupidx_embed(
                f"{emojicross} Guild Not Found",
                f"Guild `{guild_id}` is not in the blacklist.",
                color=color_danger
            )
            await ctx.reply(embed=embed)
            return

        gid, gname, owner_id, members, reason, by, ts = row

        # Try to enrich with live data if bot is in that guild
        g: Optional[discord.Guild] = self.bot.get_guild(gid)
        live_name    = g.name           if g else gname or "Unknown"
        live_owner   = g.owner_id       if g else owner_id
        live_members = g.member_count   if g else members
        live_icon    = g.icon.url       if g and g.icon else None
        live_desc    = g.description    if g and g.description else "No description"
        created_at   = discord.utils.snowflake_time(gid).strftime("%d %b %Y") if gid else "Unknown"
        in_cache     = f"{emojiverified} Bot is in this guild" if g else "❌ Bot is NOT in this guild"

        embed = cupidx_embed(
            f"{emojiguild} Guild Blacklist Info",
            f"{in_cache}",
            color=color_danger
        )
        if live_icon:
            embed.set_thumbnail(url=live_icon)

        embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)

        embed.add_field(name=f"{emojiguild} Guild Name",     value=f"`{live_name}`",                           inline=True)
        embed.add_field(name=f"{emojiid}   Guild ID",        value=f"`{gid}`",                                 inline=True)
        embed.add_field(name=f"{emojicalendar} Created",     value=f"`{created_at}`",                          inline=True)
        embed.add_field(name=f"{emojiowner} Owner",          value=f"<@{live_owner}>" if live_owner else "Unknown", inline=True)
        embed.add_field(name=f"{emojimembers} Members",      value=f"`{live_members}`",                        inline=True)
        embed.add_field(name=f"{emojiinfo} Description",     value=live_desc,                                  inline=False)
        embed.add_field(name=f"{emojireason} Reason",        value=reason or "No reason provided",             inline=False)
        embed.add_field(name=f"{emojiby} Blacklisted By",    value=f"<@{by}>" if by else "Unknown",            inline=True)
        embed.add_field(name=f"{emojicalendar} Blacklisted", value=fmt_time(ts),                               inline=True)

        embed.set_footer(text="CupidX Devlopment", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Block(bot))

# CupidX HQ
