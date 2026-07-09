import discord
import asyncio
import aiosqlite
import sqlite3
import os
from discord.ext import commands
from datetime import datetime, timezone, timedelta

# ══════════════════════════════════════════════════════
#   DATABASE PATHS
# ══════════════════════════════════════════════════════

INVITE_DB  = "db/invite_tracker.db"
MSG_DB     = "db/message_stats.db"

# ══════════════════════════════════════════════════════
#   COLORS
# ══════════════════════════════════════════════════════

YELLOW = 0xFEE75C
RED    = 0xFF4444
GREEN  = 0x2ECC71
BLUE   = 0x5865F2

# ══════════════════════════════════════════════════════
#   EMBED BUILDERS — INVITE
# ══════════════════════════════════════════════════════

def _invite_embed(
    member: discord.Member,
    total: int,
    joins: int,
    leaves: int,
    fake: int,
    rejoins: int,
    bonus: int,
    requester: discord.Member
) -> discord.Embed:
    desc = (
        f"**{member.display_name}** currently has **{total}** invites.\n\n"
        f"**Total :** `{total}` | **Joins :** `{joins}` | "
        f"**Left :** `{leaves}` | **Bonus :** `{bonus}`\n"
        f"**Fake :** `{fake}` | **Rejoins :** `{rejoins}`"
    )
    embed = discord.Embed(
        title=f"{member.display_name}'s Invite Stats",
        description=desc,
        color=YELLOW
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(
        text=f"Requested by {requester.display_name}",
        icon_url=requester.display_avatar.url
    )
    return embed


def _invite_leaderboard_embed(rows: list, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title=f"{guild.name} — Invite Leaderboard",
        color=YELLOW
    )
    if not rows:
        embed.description = "No invite data yet for this server."
        return embed

    lines = []
    for i, (user_id, inv_count) in enumerate(rows, start=1):
        user = guild.get_member(int(user_id))
        name = user.display_name if user else f"<@{user_id}>"
        rank = f"#{i}"
        lines.append(f"`{rank}` **{name}** — `{inv_count}` invites")

    embed.description = "\n".join(lines)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


# ══════════════════════════════════════════════════════
#   EMBED BUILDERS — MESSAGES
# ══════════════════════════════════════════════════════

def _msg_embed(
    member: discord.Member,
    alltime: int,
    weekly: int,
    today: int
) -> discord.Embed:
    desc = (
        f"**All time** | `{alltime:,}` messages in this server\n"
        f"**Weekly**   | `{weekly:,}` messages in this server\n"
        f"**Today**    | `{today:,}` messages in this server\n\n"
        f"-# Messages are being updated in real-time"
    )
    embed = discord.Embed(
        title=f"{member.display_name}'s Messages",
        description=desc,
        color=YELLOW
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def _msg_leaderboard_embed(rows: list, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title=f"{guild.name} — Message Leaderboard",
        color=YELLOW
    )
    if not rows:
        embed.description = "No message data yet for this server."
        return embed

    lines = []
    for i, (user_id, count) in enumerate(rows, start=1):
        user = guild.get_member(int(user_id))
        name = user.display_name if user else f"<@{user_id}>"
        rank = f"#{i}"
        lines.append(f"`{rank}` **{name}** — `{count:,}` messages")

    embed.description = "\n".join(lines)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


# ══════════════════════════════════════════════════════
#   COG — COMBINED
# ══════════════════════════════════════════════════════

class InviteTracker(commands.Cog):
    """
    Combined cog: Invite Tracker + Message Stats.
    Both features run from a single cog with separate databases.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_invites: dict[int, list] = {}
        self.bot.loop.create_task(self._startup())

    # ── help_custom (for your help cog) ───────────────

    def help_custom(self):
        emoji  = "<:invite:1426801992747188224>"
        label  = "Invite Tracker + Message Stats"
        description = "Track who invited whom and count messages per user."
        return emoji, label, description

    # ══════════════════════════════════════════════════
    #   STARTUP — DB INIT + INVITE SNAPSHOT
    # ══════════════════════════════════════════════════

    async def _startup(self):
        await self.bot.wait_until_ready()
        os.makedirs("db", exist_ok=True)
        await self._init_invite_db()
        await self._init_msg_db()
        await self._snapshot_all_guilds()

    async def _init_invite_db(self):
        with sqlite3.connect(INVITE_DB) as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS invites (
                guild_id    TEXT,
                inviter_id  TEXT,
                invite_code TEXT,
                uses        INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, invite_code)
            );

            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id  TEXT,
                user_id   TEXT,
                invites   INTEGER DEFAULT 0,
                fake      INTEGER DEFAULT 0,
                leaves    INTEGER DEFAULT 0,
                rejoins   INTEGER DEFAULT 0,
                bonus     INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS invite_settings (
                guild_id TEXT PRIMARY KEY,
                enabled  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS join_log (
                guild_id   TEXT,
                member_id  TEXT,
                inviter_id TEXT,
                PRIMARY KEY (guild_id, member_id)
            );
            """)
            conn.commit()

    async def _init_msg_db(self):
        async with aiosqlite.connect(MSG_DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    user_id  INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    date     TEXT    NOT NULL,
                    count    INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, date)
                )
            """)
            await db.commit()

    async def _snapshot_all_guilds(self):
        """Load invite cache for all guilds on startup with rate-limit protection."""
        for guild in self.bot.guilds:
            await asyncio.sleep(1)
            try:
                self.guild_invites[guild.id] = await guild.invites()
            except discord.Forbidden:
                self.guild_invites[guild.id] = []
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = getattr(e, "retry_after", 5) or 5
                    await asyncio.sleep(retry_after)
                    try:
                        self.guild_invites[guild.id] = await guild.invites()
                    except Exception:
                        self.guild_invites[guild.id] = []
                else:
                    self.guild_invites[guild.id] = []

    # ══════════════════════════════════════════════════
    #   INVITE HELPERS
    # ══════════════════════════════════════════════════

    async def is_enabled(self, guild_id: int) -> bool:
        with sqlite3.connect(INVITE_DB) as conn:
            cur = conn.execute(
                "SELECT enabled FROM invite_settings WHERE guild_id = ?",
                (str(guild_id),)
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False

    async def set_enabled(self, guild_id: int, enabled: bool):
        with sqlite3.connect(INVITE_DB) as conn:
            conn.execute("""
                INSERT INTO invite_settings (guild_id, enabled)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET enabled = excluded.enabled
            """, (str(guild_id), int(enabled)))
            conn.commit()

    async def get_invite_stats(self, guild_id: int, user_id: int):
        """Returns (invites, fake, leaves, rejoins, bonus)"""
        with sqlite3.connect(INVITE_DB) as conn:
            cur = conn.execute("""
                SELECT invites, fake, leaves, rejoins, COALESCE(bonus, 0)
                FROM invite_stats
                WHERE guild_id = ? AND user_id = ?
            """, (str(guild_id), str(user_id)))
            row = cur.fetchone()
        return row if row else (0, 0, 0, 0, 0)

    # ══════════════════════════════════════════════════
    #   MESSAGE HELPERS
    # ══════════════════════════════════════════════════

    async def _msg_increment(self, user_id: int, guild_id: int):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with aiosqlite.connect(MSG_DB) as db:
            await db.execute("""
                INSERT INTO messages (user_id, guild_id, date, count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, guild_id, date)
                DO UPDATE SET count = count + 1
            """, (user_id, guild_id, today))
            await db.commit()

    async def _fetch_msg_stats(self, user_id: int, guild_id: int):
        today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_start = (datetime.now(timezone.utc) - timedelta(days=6)).strftime("%Y-%m-%d")
        async with aiosqlite.connect(MSG_DB) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(count), 0) FROM messages WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            ) as cur:
                (alltime,) = await cur.fetchone()
            async with db.execute(
                "SELECT COALESCE(SUM(count), 0) FROM messages WHERE user_id=? AND guild_id=? AND date>=?",
                (user_id, guild_id, week_start)
            ) as cur:
                (weekly,) = await cur.fetchone()
            async with db.execute(
                "SELECT COALESCE(SUM(count), 0) FROM messages WHERE user_id=? AND guild_id=? AND date=?",
                (user_id, guild_id, today)
            ) as cur:
                (today_count,) = await cur.fetchone()
        return alltime, weekly, today_count

    async def _fetch_msg_leaderboard(self, guild_id: int, limit: int = 10):
        async with aiosqlite.connect(MSG_DB) as db:
            async with db.execute("""
                SELECT user_id, SUM(count) AS total
                FROM messages
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT ?
            """, (guild_id, limit)) as cur:
                return await cur.fetchall()

    # ══════════════════════════════════════════════════
    #   EVENTS
    # ══════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await self._msg_increment(message.author.id, message.guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.guild_invites[guild.id] = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            self.guild_invites[guild.id] = []

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        invites = self.guild_invites.get(invite.guild.id, [])
        invites.append(invite)
        self.guild_invites[invite.guild.id] = invites

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        invites = self.guild_invites.get(invite.guild.id, [])
        self.guild_invites[invite.guild.id] = [
            i for i in invites if i.code != invite.code
        ]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self.is_enabled(member.guild.id):
            return

        guild         = member.guild
        before_invites = self.guild_invites.get(guild.id, [])

        try:
            after_invites = await guild.invites()
            self.guild_invites[guild.id] = after_invites
        except discord.HTTPException as e:
            if e.status == 429:
                after_invites = before_invites  # fallback to cache
            else:
                return
        except discord.Forbidden:
            return

        used_invite = None
        for before in before_invites:
            after = discord.utils.get(after_invites, code=before.code)
            if after and after.uses > before.uses:
                used_invite = after
                break

        if not used_invite or not used_invite.inviter:
            return

        inviter  = used_invite.inviter
        now      = datetime.now(timezone.utc)
        acc_age  = now - member.created_at
        is_fake  = acc_age.total_seconds() < 86400  # account < 1 day old

        with sqlite3.connect(INVITE_DB) as conn:
            # Upsert invite code record
            conn.execute("""
                INSERT OR IGNORE INTO invites (guild_id, inviter_id, invite_code, uses)
                VALUES (?, ?, ?, 0)
            """, (str(guild.id), str(inviter.id), used_invite.code))
            conn.execute("""
                UPDATE invites SET uses = uses + 1
                WHERE guild_id = ? AND invite_code = ?
            """, (str(guild.id), used_invite.code))

            # Ensure inviter row exists
            conn.execute("""
                INSERT OR IGNORE INTO invite_stats (guild_id, user_id)
                VALUES (?, ?)
            """, (str(guild.id), str(inviter.id)))

            if is_fake:
                conn.execute("""
                    UPDATE invite_stats SET fake = fake + 1
                    WHERE guild_id = ? AND user_id = ?
                """, (str(guild.id), str(inviter.id)))
            else:
                conn.execute("""
                    UPDATE invite_stats SET invites = invites + 1
                    WHERE guild_id = ? AND user_id = ?
                """, (str(guild.id), str(inviter.id)))

            # Log who invited this member so leave tracking is accurate
            conn.execute("""
                INSERT OR REPLACE INTO join_log (guild_id, member_id, inviter_id)
                VALUES (?, ?, ?)
            """, (str(guild.id), str(member.id), str(inviter.id)))

            conn.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not await self.is_enabled(member.guild.id):
            return

        # Refresh invite cache
        try:
            self.guild_invites[member.guild.id] = await member.guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Look up who originally invited this member
        with sqlite3.connect(INVITE_DB) as conn:
            cur = conn.execute("""
                SELECT inviter_id FROM join_log
                WHERE guild_id = ? AND member_id = ?
            """, (str(member.guild.id), str(member.id)))
            row = cur.fetchone()

            if row:
                inviter_id = row[0]
                # Decrement the inviter's invite count and increment leaves
                conn.execute("""
                    UPDATE invite_stats
                    SET invites = MAX(invites - 1, 0),
                        leaves  = leaves + 1
                    WHERE guild_id = ? AND user_id = ?
                """, (str(member.guild.id), inviter_id))
                # Remove join log entry
                conn.execute("""
                    DELETE FROM join_log WHERE guild_id = ? AND member_id = ?
                """, (str(member.guild.id), str(member.id)))
            conn.commit()

    # ══════════════════════════════════════════════════
    #   INVITE COMMANDS
    # ══════════════════════════════════════════════════

    @commands.command(
        name="inviteenable",
        aliases=["invenable", "enableinvite"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def inviteenable(self, ctx: commands.Context):
        await self.set_enabled(ctx.guild.id, True)
        embed = discord.Embed(
            description="Invite tracking has been **enabled** for this server.",
            color=GREEN
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="invitedisable",
        aliases=["invdisable", "disableinvite"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def invitedisable(self, ctx: commands.Context):
        await self.set_enabled(ctx.guild.id, False)
        embed = discord.Embed(
            description="Invite tracking has been **disabled** for this server.",
            color=RED
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="invites",
        aliases=["inv", "invstat", "invstats", "checkinvites", "i"],
    )
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def invites(self, ctx: commands.Context, member: discord.Member = None):
        if not await self.is_enabled(ctx.guild.id):
            embed = discord.Embed(
                description="Invite tracking is not enabled. Use `inviteenable` first.",
                color=RED
            )
            return await ctx.reply(embed=embed, mention_author=False)

        member = member or ctx.author
        inv, fake, leaves, rejoins, bonus = await self.get_invite_stats(ctx.guild.id, member.id)
        total  = inv + bonus

        embed = _invite_embed(member, total, inv, leaves, fake, rejoins, bonus, ctx.author)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="inviteleaderboard",
        aliases=["invlb", "invitetop", "invtop", "toplb"],
    )
    @commands.guild_only()
    @commands.cooldown(1, 8, commands.BucketType.guild)
    async def inviteleaderboard(self, ctx: commands.Context):
        if not await self.is_enabled(ctx.guild.id):
            embed = discord.Embed(
                description="Invite tracking is not enabled.",
                color=RED
            )
            return await ctx.reply(embed=embed, mention_author=False)

        with sqlite3.connect(INVITE_DB) as conn:
            cur = conn.execute("""
                SELECT user_id, (invites + COALESCE(bonus, 0)) AS total
                FROM invite_stats
                WHERE guild_id = ?
                ORDER BY total DESC
                LIMIT 10
            """, (str(ctx.guild.id),))
            rows = cur.fetchall()

        embed = _invite_leaderboard_embed(rows, ctx.guild)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="resetinvites",
        aliases=["resetinv", "clearinvites"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def resetinvites(self, ctx: commands.Context, member: discord.Member):
        with sqlite3.connect(INVITE_DB) as conn:
            conn.execute(
                "DELETE FROM invite_stats WHERE guild_id = ? AND user_id = ?",
                (str(ctx.guild.id), str(member.id))
            )
            conn.execute(
                "DELETE FROM join_log WHERE guild_id = ? AND member_id = ?",
                (str(ctx.guild.id), str(member.id))
            )
            conn.commit()
        embed = discord.Embed(
            description=f"Reset invite stats for {member.mention}.",
            color=GREEN
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="resetserverinvites",
        aliases=["resetallinvites", "clearserverinvites"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def resetserverinvites(self, ctx: commands.Context):
        with sqlite3.connect(INVITE_DB) as conn:
            conn.execute("DELETE FROM invite_stats WHERE guild_id = ?", (str(ctx.guild.id),))
            conn.execute("DELETE FROM invites WHERE guild_id = ?", (str(ctx.guild.id),))
            conn.execute("DELETE FROM join_log WHERE guild_id = ?", (str(ctx.guild.id),))
            conn.commit()
        embed = discord.Embed(
            description="Reset all invite stats for this server.",
            color=GREEN
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="addinvites",
        aliases=["addinv", "bonusinvites", "giveinvites"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def addinvites(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            embed = discord.Embed(description="Amount must be a positive number.", color=RED)
            return await ctx.reply(embed=embed, mention_author=False)

        with sqlite3.connect(INVITE_DB) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO invite_stats (guild_id, user_id)
                VALUES (?, ?)
            """, (str(ctx.guild.id), str(member.id)))
            conn.execute("""
                UPDATE invite_stats SET bonus = COALESCE(bonus, 0) + ?
                WHERE guild_id = ? AND user_id = ?
            """, (amount, str(ctx.guild.id), str(member.id)))
            conn.commit()

        embed = discord.Embed(
            description=f"Added **{amount}** bonus invites to {member.mention}.",
            color=GREEN
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="removeinvites",
        aliases=["reminv", "deductinvites", "takeinvites"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def removeinvites(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            embed = discord.Embed(description="Amount must be a positive number.", color=RED)
            return await ctx.reply(embed=embed, mention_author=False)

        with sqlite3.connect(INVITE_DB) as conn:
            conn.execute("""
                UPDATE invite_stats
                SET bonus = MAX(COALESCE(bonus, 0) - ?, 0)
                WHERE guild_id = ? AND user_id = ?
            """, (amount, str(ctx.guild.id), str(member.id)))
            conn.commit()

        embed = discord.Embed(
            description=f"Removed **{amount}** invites from {member.mention}.",
            color=RED
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ══════════════════════════════════════════════════
    #   MESSAGE COMMANDS
    # ══════════════════════════════════════════════════

    @commands.command(
        name="messages",
        aliases=["msgs", "msgstats", "msgcount", "mc2", "chatcount", "m"],
    )
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def messages(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        alltime, weekly, today = await self._fetch_msg_stats(member.id, ctx.guild.id)
        embed = _msg_embed(member, alltime, weekly, today)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="msgleaderboard",
        aliases=["msglb", "msgtop", "chattop", "chatlb", "topmessages"],
    )
    @commands.guild_only()
    @commands.cooldown(1, 8, commands.BucketType.guild)
    async def msgleaderboard(self, ctx: commands.Context):
        rows  = await self._fetch_msg_leaderboard(ctx.guild.id)
        embed = _msg_leaderboard_embed(rows, ctx.guild)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="resetmessages",
        aliases=["resetmsgs", "clearmessages", "resetmsg"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def resetmessages(self, ctx: commands.Context, member: discord.Member):
        async with aiosqlite.connect(MSG_DB) as db:
            await db.execute(
                "DELETE FROM messages WHERE user_id=? AND guild_id=?",
                (member.id, ctx.guild.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"Reset message stats for {member.mention}.",
            color=GREEN
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(
        name="resetservermessages",
        aliases=["resetallmsgs", "clearservermessages"],
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def resetservermessages(self, ctx: commands.Context):
        async with aiosqlite.connect(MSG_DB) as db:
            await db.execute(
                "DELETE FROM messages WHERE guild_id=?",
                (ctx.guild.id,)
            )
            await db.commit()
        embed = discord.Embed(
            description="Reset all message stats for this server.",
            color=RED
        )
        await ctx.reply(embed=embed, mention_author=False)


# ══════════════════════════════════════════════════════
#   SETUP
# ══════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))
