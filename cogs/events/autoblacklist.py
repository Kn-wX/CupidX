from __future__ import annotations

import discord
from core import cupidx, Cog
from discord.ext import commands
import aiosqlite
from datetime import datetime, timedelta

from utils.config import SUPPORT_SERVER
from cogs.commands.guildvip import is_guild_vip


class AutoBlacklist(Cog):
    def __init__(self, client: cupidx):
        self.client = client
        self.spam_cd_mapping      = commands.CooldownMapping.from_cooldown(5, 5, commands.BucketType.member)
        self.spam_command_mapping = commands.CooldownMapping.from_cooldown(6, 10, commands.BucketType.member)
        self.last_spam            = {}
        self.spam_threshold       = 5
        self.spam_window          = timedelta(minutes=10)
        self.db_path              = "db/block.db"
        self.bot_user_id          = self.client.user.id if self.client.user else None
        self.guild_command_tracking: dict[int, list[datetime]] = {}

    # ── DB write ─────────────────────────────────────────────────

    async def add_to_blacklist(
        self,
        user_id:  int | None = None,
        guild_id: int | None = None,
        channel:  discord.TextChannel | None = None
    ) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                timestamp = datetime.utcnow()
                if guild_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO guild_blacklist (guild_id, timestamp) VALUES (?, ?)",
                        (guild_id, timestamp)
                    )
                    if channel:
                        embed = discord.Embed(
                            title="<:warning:1422425521379217438> Guild Blacklisted",
                            description=(
                                "This guild has been blacklisted due to spamming or automation. "
                                f"If you believe this is a mistake, please contact our "
                                f"[Support Server]({SUPPORT_SERVER}) with any proof if possible."
                            ),
                            color=0xFCD005
                        )
                        await channel.send(embed=embed)
                elif user_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO user_blacklist (user_id, timestamp) VALUES (?, ?)",
                        (user_id, timestamp)
                    )
                await db.commit()
        except aiosqlite.Error as e:
            print(f"[AutoBlacklist] Database error: {e}")

    # ── Guild blacklist via user-spam threshold ───────────────────

    async def check_and_blacklist_guild(self, guild_id: int) -> None:
        # VIP guilds are exempt from auto-blacklist
        if await is_guild_vip(guild_id):
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT COUNT(DISTINCT user_id) FROM user_blacklist
                WHERE timestamp >= ?
                """,
                (datetime.utcnow() - self.spam_window,)
            ) as cursor:
                count = await cursor.fetchone()
                if count[0] >= self.spam_threshold:
                    async with db.execute(
                        "SELECT channel_id FROM guild_settings WHERE guild_id = ?",
                        (guild_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            channel = self.client.get_channel(row[0])
                            if channel:
                                await self.add_to_blacklist(guild_id=guild_id, channel=channel)

    # ── on_message ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        guild_id = message.guild.id if message.guild else None

        # -- Guild-level message spam detection --
        if guild_id:
            if guild_id not in self.guild_command_tracking:
                self.guild_command_tracking[guild_id] = []

            now = datetime.utcnow()
            self.guild_command_tracking[guild_id].append(now)

            # Keep only timestamps within the last 2 seconds
            self.guild_command_tracking[guild_id] = [
                ts for ts in self.guild_command_tracking[guild_id]
                if ts >= now - timedelta(seconds=2)
            ]

            if len(self.guild_command_tracking[guild_id]) > 8:
                # VIP guilds bypass auto-blacklist
                if await is_guild_vip(guild_id):
                    return

                await self.add_to_blacklist(guild_id=guild_id, channel=message.channel)
                embed = discord.Embed(
                    title="<:warning:1422425521379217438> Guild Blacklisted",
                    description=(
                        "This guild has been blacklisted for excessive message activity. "
                        f"If you believe this is a mistake, please contact our "
                        f"[Support Server]({SUPPORT_SERVER})."
                    ),
                    color=0xFCD005
                )
                await message.channel.send(embed=embed)
                return

        # -- Per-user mention/spam rate limit --
        bucket = self.spam_cd_mapping.get_bucket(message)
        retry  = bucket.update_rate_limit()

        if retry:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT user_id FROM user_blacklist WHERE user_id = ?",
                    (message.author.id,)
                ) as cursor:
                    if await cursor.fetchone():
                        return  # already blacklisted

                # Bot mention spam
                if message.content in (
                    f"<@{self.bot_user_id}>",
                    f"<@!{self.bot_user_id}>"
                ):
                    await self.add_to_blacklist(user_id=message.author.id)
                    embed = discord.Embed(
                        title="<:warning:1422425521379217438> User Blacklisted",
                        description=(
                            f"**{message.author.mention} has been blacklisted for repeatedly "
                            f"mentioning me. If you believe this is a mistake, please contact "
                            f"our [Support Server]({SUPPORT_SERVER}) with any proof if possible.**"
                        ),
                        color=0xFCD005
                    )
                    await message.channel.send(embed=embed)
                    return

                # Track user spam for guild-level threshold
                if message.guild:
                    if message.author.id not in self.last_spam:
                        self.last_spam[message.author.id] = []
                    self.last_spam[message.author.id].append(datetime.utcnow())

                    recent = [
                        ts for ts in self.last_spam.get(message.author.id, [])
                        if ts >= datetime.utcnow() - self.spam_window
                    ]
                    self.last_spam[message.author.id] = recent

                    if len(recent) >= self.spam_threshold:
                        await self.check_and_blacklist_guild(message.guild.id)

    # ── on_command ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        if ctx.author.bot:
            return

        bucket = self.spam_command_mapping.get_bucket(ctx.message)
        retry  = bucket.update_rate_limit()

        if retry:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT user_id FROM user_blacklist WHERE user_id = ?",
                    (ctx.author.id,)
                ) as cursor:
                    if await cursor.fetchone():
                        return  # already blacklisted

                await self.add_to_blacklist(user_id=ctx.author.id)
                embed = discord.Embed(
                    title="<:warning:1422425521379217438> User Blacklisted",
                    description=(
                        f"**{ctx.author.mention} has been blacklisted for spamming commands. "
                        f"If you believe this is a mistake, please contact our "
                        f"[Support Server]({SUPPORT_SERVER}) with any proof if possible.**"
                    ),
                    color=0xFCD005
                )
                await ctx.reply(embed=embed)


async def setup(client: cupidx):
    await client.add_cog(AutoBlacklist(client))
