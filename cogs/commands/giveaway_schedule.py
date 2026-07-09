import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import pytz
import re
import aiosqlite
import random
from utils.config import OWNER_IDS

IST = pytz.timezone("Asia/Kolkata")

# --- DATABASE HELPERS ---
async def is_guild_premium(guild_id):
    async with aiosqlite.connect("db/premium.db") as db:
        async with db.execute(
            "SELECT 1 FROM premium_guilds WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

def parse_time_to_seconds(input_str):
    text = input_str.lower().strip()
    d = int(re.findall(r'(\d+)d', text)[0]) if re.findall(r'(\d+)d', text) else 0
    h = int(re.findall(r'(\d+)h', text)[0]) if re.findall(r'(\d+)h', text) else 0
    m = int(re.findall(r'(\d+)m', text)[0]) if re.findall(r'(\d+)m', text) else 0
    return (d * 86400) + (h * 3600) + (m * 60)

active_tasks = {}

class GiveawaySchedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ✅ UPDATED SECURITY SYSTEM
    async def cog_check(self, ctx):

        # Bot Owner
        if ctx.author.id in OWNER_IDS:
            return True

        if ctx.guild:
            # Administrator allowed
            if ctx.author.guild_permissions.administrator:
                return True

            # Premium Server Owner allowed
            if ctx.author.id == ctx.guild.owner_id:
                if await is_guild_premium(ctx.guild.id):
                    return True

        await ctx.reply(
            "❌ You must be a **Bot Owner, Administrator, or Premium Server Owner** to use this command."
        )
        return False

    # =====================================================

    @commands.hybrid_command(name="gschedule", aliases=["gshedule"])
    @app_commands.describe(
        channel="Select the channel where giveaway will be posted",
        after="When to start? (e.g., 2h, 10m)",
        duration="Giveaway length (e.g., 1h, 1d)",
        winners="Number of winners",
        prize="What is the prize?"
    )
    async def gschedule(self, ctx, channel: discord.TextChannel, after: str, duration: str, winners: int, *, prize: str):

        wait_sec = parse_time_to_seconds(after)
        run_sec = parse_time_to_seconds(duration)

        if run_sec <= 0:
            return await ctx.reply("❌ Invalid duration! Use format: 1h, 30m, 1d.")

        start_at = datetime.datetime.now(IST) + datetime.timedelta(seconds=wait_sec)
        ends_at = start_at + datetime.timedelta(seconds=run_sec)
        host = ctx.author

        await ctx.reply(
            f"✅ **Giveaway Scheduled!**\nChannel: {channel.mention}\nStarts: <t:{int(start_at.timestamp())}:R>"
        )

        async def giveaway_process():

            if wait_sec > 0:
                await asyncio.sleep(wait_sec)

            start_embed = discord.Embed(
                title=f"🎁 {prize} 🎁",
                description=(
                    f"React with 🎉 to enter!\n\n"
                    f"🔹 **Hosted by:** {host.mention}\n"
                    f"🔹 **Winners:** {winners}\n"
                    f"🔹 **Ends:** <t:{int(ends_at.timestamp())}:R>"
                ),
                color=0x2f3136
            )
            start_embed.set_footer(
                text=f"Ends at | {ends_at.strftime('%d-%m-%Y %I:%M %p')}"
            )

            try:
                msg = await channel.send(
                    content="🎊 **GIVEAWAY STARTED** 🎊",
                    embed=start_embed
                )
                await msg.add_reaction("🎉")
                active_tasks[msg.id] = True
            except:
                return

            try:
                rem = run_sec
                while rem > 0 and active_tasks.get(msg.id):
                    await asyncio.sleep(min(rem, 5))
                    rem -= 5
            finally:
                if msg.id in active_tasks:
                    del active_tasks[msg.id]

            try:
                msg = await channel.fetch_message(msg.id)
                users = [u async for u in msg.reactions[0].users() if not u.bot]

                if not users:
                    return await msg.edit(
                        content="🎁 **GIVEAWAY ENDED** 🎁",
                        embed=discord.Embed(
                            description="No participants found.",
                            color=0xff0000
                        )
                    )

                winners_list = random.sample(users, min(winners, len(users)))
                win_mentions = ", ".join([w.mention for w in winners_list])

                end_embed = discord.Embed(
                    title=f"🎁 {prize} 🎁",
                    description=(
                        f"🔹 **Hosted by:** {host.mention}\n"
                        f"🔹 **Total participant(s):** {len(users)}\n\n"
                        f"🔹 **Winner(s):**\n{win_mentions}"
                    ),
                    color=0x2b2d31
                )
                end_embed.set_footer(
                    text=f"Ended | {datetime.datetime.now(IST).strftime('%I:%M %p')}"
                )

                await msg.edit(
                    content="🎁 **GIVEAWAY ENDED** 🎁",
                    embed=end_embed
                )

                await channel.send(
                    f"Congrats {win_mentions}, you won **{prize}**, hosted by {host.mention}!"
                )

            except:
                pass

        self.bot.loop.create_task(giveaway_process())

    # =====================================================

    @commands.hybrid_command(name="gsgend")
    async def gsgend(self, ctx, message_id: str):
        mid = int(message_id)
        if mid in active_tasks:
            active_tasks[mid] = False
            await ctx.reply("✅ Ending now...")
        else:
            await ctx.reply("❌ Active giveaway not found.")

    @commands.hybrid_command(name="gsreroll")
    async def gsreroll(self, ctx, message_id: str):
        try:
            msg = await ctx.channel.fetch_message(int(message_id))
            users = [u async for u in msg.reactions[0].users() if not u.bot]
            if not users:
                return await ctx.reply("❌ No participants.")
            await ctx.reply(f"🎊 **Reroll Winner:** {random.choice(users).mention}")
        except:
            await ctx.reply("❌ Message not found.")

async def setup(bot):
    await bot.add_cog(GiveawaySchedule(bot))