import discord
from discord.ext import commands
import aiosqlite
import time

GLOBAL_BLACKLIST_LOG_CHANNEL = 1477971506213687296  # <-- PASTE YOUR LOG CHANNEL ID HERE


class AutoBlacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = {}

    async def send_global_blacklist_log(self, guild_id: int, reason: str = "Command Spam Detected"):
        try:
            channel = self.bot.get_channel(GLOBAL_BLACKLIST_LOG_CHANNEL)
            if not channel:
                return

            guild = self.bot.get_guild(guild_id)

            guild_name = "Unknown"
            owner_id = "Unknown"
            member_count = "Unknown"
            created_at = "Unknown"

            if guild:
                guild_name = guild.name
                owner_id = guild.owner_id
                member_count = guild.member_count
                created_at = guild.created_at.strftime("%d %B %Y")

            embed = discord.Embed(
                title="🚨 Guild Globally Blacklisted",
                color=0xFF0000,
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(name="Guild Name", value=f"`{guild_name}`", inline=False)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=False)
            embed.add_field(name="Owner ID", value=f"`{owner_id}`", inline=False)
            embed.add_field(name="Member Count", value=f"`{member_count}`", inline=False)
            embed.add_field(name="Server Created", value=f"`{created_at}`", inline=False)
            embed.add_field(name="Reason", value=f"`{reason}`", inline=False)

            embed.set_footer(text="CupidX Global Blacklist System")

            await channel.send(embed=embed)

        except Exception as e:
            print(f"[GLOBAL BLACKLIST LOG ERROR]: {e}")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        guild_id = ctx.guild.id
        current_time = time.time()

        if guild_id not in self.spam_tracker:
            self.spam_tracker[guild_id] = []

        self.spam_tracker[guild_id].append(current_time)
        self.spam_tracker[guild_id] = [
            t for t in self.spam_tracker[guild_id]
            if current_time - t < 10
        ]

        if len(self.spam_tracker[guild_id]) >= 15:
            async with aiosqlite.connect("db/block.db") as db:
                await db.execute(
                    "INSERT OR IGNORE INTO guild_blacklist (guild_id, timestamp) VALUES (?, ?)",
                    (guild_id, int(current_time))
                )
                await db.commit()

            await self.send_global_blacklist_log(guild_id)

            self.spam_tracker[guild_id] = []

def setup(bot):
    bot.add_cog(AutoBlacklist(bot)))