import discord
from discord.ext import commands
import aiosqlite
import psutil
import time
import os
import platform
import datetime
from utils.Tools import *
from utils.detectfile import *
from discord.ui import LayoutView, Container, TextDisplay, Separator

STATS_DB = "db/stats.db"

# ========================= V2 CARD HELPER =========================

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    c.add_item(Separator())
    view.add_item(c)
    return view


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0
        self.bot.loop.create_task(self.setup_database())

    # ------------------------------- DATABASE -------------------------------

    async def setup_database(self) -> None:
        os.makedirs("db", exist_ok=True)
        async with aiosqlite.connect(STATS_DB) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)"
            )
            await db.commit()

            async with db.execute(
                "SELECT value FROM stats WHERE key = 'total_songs_played'"
            ) as cursor:
                row = await cursor.fetchone()

            self.total_songs_played = row[0] if row else 0

            if row is None:
                await db.execute(
                    "INSERT INTO stats (key, value) VALUES ('total_songs_played', 0)"
                )
                await db.commit()

    async def update_total_songs_played(self) -> None:
        async with aiosqlite.connect(STATS_DB) as db:
            await db.execute(
                "INSERT OR REPLACE INTO stats (key, value) VALUES ('total_songs_played', ?)",
                (self.total_songs_played,),
            )
            await db.commit()

    #@commands.Cog.listener()
    #async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        #self.total_songs_played += 1
        #await self.update_total_songs_played()

    # ------------------------------- CODE STATS -------------------------------

    def count_code_stats(self, file_path: str) -> tuple[int, int]:
        total_lines = 0
        total_words = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith(("#", '"""', "'''")):
                        total_lines += 1
                        total_words += len(stripped.split())
        except Exception:
            pass
        return total_lines, total_words

    def gather_file_stats(self, directory: str) -> tuple[int, int, int]:
        total_files = 0
        total_lines = 0
        total_words = 0
        for root, _, files in os.walk(directory):
            if ".local" in root:
                continue
            for file in files:
                if not file.endswith(".py"):
                    continue
                total_files += 1
                fp = os.path.join(root, file)
                lines, words = self.count_code_stats(fp)
                total_lines += lines
                total_words += words
        return total_files, total_lines, total_words

    # ------------------------------- MAIN COMMAND -------------------------------

    @commands.hybrid_command(
        name="stats",
        aliases=["botinfo", "bi", "st", "statistics"],
        help="Shows CupidX's premium live statistics.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def stats(self, ctx: commands.Context):
        # Collecting all data from your screenshots
        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count or 0 for g in self.bot.guilds)
        bot_count = sum(sum(1 for m in g.members if m.bot) for g in self.bot.guilds)
        human_count = user_count - bot_count
        channel_count = len(set(self.bot.get_all_channels()))
        total_commands = len(list(self.bot.walk_commands()))
        uptime = str(datetime.timedelta(seconds=int(time.time() - self.start_time)))

        # Latency calculations
        try:
            shard = self.bot.get_shard(ctx.guild.shard_id) if hasattr(self.bot, "get_shard") else None
            latency = shard.latency if shard else self.bot.latency
        except:
            latency = self.bot.latency
        wsping = round(self.bot.latency * 1000, 2)
        try:
            async with aiosqlite.connect(STATS_DB) as db:
                start = time.perf_counter()
                await db.execute("SELECT 1")
                db_latency = round((time.perf_counter() - start) * 1000, 2)
        except:
            db_latency = "N/A"

        # Codebase & System stats
        total_files, total_lines, total_words = self.gather_file_stats(".")
        # Fetching Owner Mentions from config
        from utils.config import OWNER_IDS
        # This format creates a clickable profile link without sending a notification
        owner_display = ", ".join([f"<@{uid}>" for uid in OWNER_IDS])

        # English Embed Configuration
        embed = discord.Embed(
            title="🌸 CupidX Statistics Dashboard",
            description=(
                f"**Owners:** {owner_display}\n\n"
                f"Greetings! I am **{self.bot.user.name}**, currently protecting "
                f"**{guild_count}** servers with elite security features! ✨"
            ),
            color=0x134E5E
        )


        # Overview Section - Exact match to SS
        embed.add_field(
            name="📊 **Overview**",
            value=(
                f"> 🏰 **Guilds:** `{guild_count}`\n"
                f"> 📺 **Channels:** `{channel_count}`\n"
                f"> 👤 **Users:** `{human_count}` humans • `{bot_count}` bots\n"
                f"> ⌨️ **Commands Loaded:** `{total_commands}`\n"
                f"> ⏳ **Uptime:** `{uptime}`\n"
                f"> 🎵 **Songs Played:** `{self.total_songs_played}`"
            ),
            inline=False
        )

        # Latency Section - Exact match to SS
        embed.add_field(
            name="⚡ **Latency**",
            value=(
                f"> 🤖 **Bot:** `{round(latency * 1000)}ms`\n"
                f"> 🗄️ **Database:** `{db_latency}ms`\n"
                f"> 📡 **WebSocket:** `{wsping}ms`"
            ),
            inline=True
        )

        # System & Codebase - Exact match to SS
        embed.add_field(
            name="🚀 **System & Codebase**",
            value=(
                f"> 🐍 **Python Files:** `{total_files}`\n"
                f"> 📝 **Total Lines:** `{total_lines}`\n"
                f"> 📖 **Total Words:** `{total_words}`\n"
                f"> 🧠 **RAM:** `{psutil.virtual_memory().percent}%` used"
            ),
            inline=True
        )

        # Aesthetics
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_image(url=BANNER_URL)
        
        # Footer - Only Created by mr.x
        embed.set_footer(text="Created by mr.x ❤️", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
