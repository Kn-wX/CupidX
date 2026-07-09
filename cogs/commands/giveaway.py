from discord.ext import commands, tasks
import datetime, pytz, time as t
from discord.ui import Button, Select, View
import aiosqlite, random, typing
import sqlite3
import asyncio
import discord, logging
from discord.utils import get
from utils.Tools import *
import os
import aiohttp
from utils.detectfile import *

# ══════════════════════════════════════════════════════════════════════════════
#  EMOJIS
# ══════════════════════════════════════════════════════════════════════════════
E = {
    "gift":     EMOJI_GIFT2,
    "cross":    EMOJI_CROSS,
    "tick":     EMOJI_TICK,
    "warning":  EMOJI_SIGN,
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "loading":  EMOJI_LOADING,
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "timer":    EMOJI_TIMER2,
    "trophy":   EMOJI_STAR,
    "host":     EMOJI_USER,
    "react":    EMOJI_GIFT2,
}

BOT_COLOR   = 0x2b2d31   # dark embed color
GIFT_THUMB  = GIVEAWAY_GIFT_THUMB
ENDED_THUMB = GIVEAWAY_ENDED_THUMB

# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE SETUP
# ══════════════════════════════════════════════════════════════════════════════
db_folder = 'db'
db_file   = 'giveaways.db'
db_path   = os.path.join(db_folder, db_file)
os.makedirs(db_folder, exist_ok=True)

connection = sqlite3.connect(db_path)
cursor     = connection.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS Giveaway (
                    guild_id   INTEGER,
                    host_id    INTEGER,
                    start_time TIMESTAMP,
                    ends_at    REAL,
                    prize      TEXT,
                    winners    INTEGER,
                    message_id INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, message_id)
                )''')
connection.commit()
connection.close()


# ══════════════════════════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════════════════════════
class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.connection = await aiosqlite.connect(db_path)
        self.cursor     = await self.connection.cursor()
        await self.check_for_ended_giveaways()
        self.GiveawayEnd.start()

    async def cog_unload(self) -> None:
        try:
            self.GiveawayEnd.cancel()
        except Exception:
            pass
        await self.connection.close()

    # ── helpers ───────────────────────────────────────────────────────────────
    def convert(self, time: str) -> int:
        pos       = ["s", "m", "h", "d"]
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit      = time[-1]
        if unit not in pos:
            return -1
        try:
            val = int(time[:-1])
        except ValueError:
            return -2
        return val * time_dict[unit]

    def _err_embed(self, title: str, desc: str) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=desc,
            color=0xFF4444,
        )

    # ── giveaway ended embed ──────────────────────────────────────────────────
    def _ended_embed(self, prize: str, host_id: int, winner: str, ended_ts: int) -> discord.Embed:
        em = discord.Embed(
            title=f"{E['trophy']}  {prize}",
            description=(
                f"{E['dot']} **Winner(s):** {winner}\n"
                f"{E['dot']} **Hosted by:** <@{host_id}>\n"
                f"{E['dot']} **Ended:** <t:{ended_ts}:R>"
            ),
            color=0x2b2d31,
            timestamp=discord.utils.utcnow(),
        )
        em.set_thumbnail(url=ENDED_THUMB)
        em.set_footer(text="Giveaway Ended")
        return em

    # ── check on startup ──────────────────────────────────────────────────────
    async def check_for_ended_giveaways(self):
        await self.cursor.execute(
            "SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id "
            "FROM Giveaway WHERE ends_at <= ?",
            (datetime.datetime.now().timestamp(),)
        )
        for giveaway in await self.cursor.fetchall():
            await self.end_giveaway(giveaway)

    # ── core end logic ────────────────────────────────────────────────────────
    async def end_giveaway(self, giveaway):
        try:
            current_ts = int(datetime.datetime.now().timestamp())
            guild      = self.bot.get_guild(int(giveaway[1]))
            if guild is None:
                await self.cursor.execute(
                    "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                    (giveaway[2], giveaway[1])
                )
                await self.connection.commit()
                return

            channel = self.bot.get_channel(int(giveaway[6]))
            if channel is None:
                return

            # fetch message with retry
            message = None
            for attempt in range(3):
                try:
                    message = await channel.fetch_message(int(giveaway[2]))
                    break
                except discord.NotFound:
                    await self.cursor.execute(
                        "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                        (giveaway[2], giveaway[1])
                    )
                    await self.connection.commit()
                    return
                except aiohttp.ClientResponseError as e:
                    if e.status == 503 and attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise

            if message is None:
                return

            # collect participants
            users = [i.id async for i in message.reactions[0].users()]
            if self.bot.user.id in users:
                users.remove(self.bot.user.id)

            prize      = giveaway[5]
            host_id    = int(giveaway[3])
            win_count  = min(len(users), int(giveaway[4]))

            if len(users) < 1:
                em = discord.Embed(
                    title=f"{E['gift']}  Giveaway Ended — No Winners",
                    description=(
                        f"{E['dot']} **Prize:** {prize}\n"
                        f"{E['dot']} **Reason:** Not enough participants."
                    ),
                    color=0xFF4444,
                    timestamp=discord.utils.utcnow(),
                )
                em.set_footer(text="Giveaway Ended")
                await message.edit(
                    content=f"{E['gift']}  **GIVEAWAY ENDED**  {E['gift']}",
                    embed=em
                )
                await message.reply(
                    f"{E['cross']}  No one won **{prize}** — not enough participants."
                )
                await self.cursor.execute(
                    "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                    (message.id, message.guild.id)
                )
                await self.connection.commit()
                return

            winner = ', '.join(f'<@{i}>' for i in random.sample(users, k=win_count))
            em     = self._ended_embed(prize, host_id, winner, current_ts)

            await message.edit(
                content=f"{E['gift']}  **GIVEAWAY ENDED**  {E['gift']}",
                embed=em
            )
            await message.reply(
                f"{E['trophy']}  Congrats {winner}! You won **{prize}**!\n"
                f"{E['host']}  Hosted by <@{host_id}>"
            )
            await self.cursor.execute(
                "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                (message.id, message.guild.id)
            )
            await self.connection.commit()

        except IndexError:
            logging.error(f"Giveaway data corrupted: {giveaway}")
            await self.cursor.execute(
                "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                (giveaway[2], giveaway[1])
            )
            await self.connection.commit()
        except (discord.HTTPException, aiohttp.ClientResponseError) as e:
            logging.error(f"Error ending giveaway: {e}")

    # ── periodic loop ─────────────────────────────────────────────────────────
    @tasks.loop(seconds=5)
    async def GiveawayEnd(self):
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id "
                "FROM Giveaway WHERE ends_at <= ?",
                (datetime.datetime.now().timestamp(),)
            )
            rows = await cursor.fetchall()
            await cursor.close()

        for row in rows:
            try:
                await self.end_giveaway(row)
            except Exception as e:
                logging.error(f"Error processing giveaway {row}: {e}")

    @GiveawayEnd.before_loop
    async def before_giveaway_loop(self):
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════════════════════════════════
    #  COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    # ── gstart ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="gstart", description="Starts a new giveaway.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def gstart(
        self, ctx,
        time:    str = commands.parameter(description="Duration e.g. 10m, 1h, 2d"),
        winners: int = commands.parameter(description="Number of winners (max 15)"),
        *,
        prize:   str = commands.parameter(description="Prize for the giveaway"),
    ):
        # ── validations ───────────────────────────────────────────────────────
        if winners >= 15:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['warning']}  Too Many Winners",
                "Winners cannot exceed **15**."
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return

        await self.cursor.execute(
            "SELECT message_id FROM Giveaway WHERE guild_id = ?", (ctx.guild.id,)
        )
        if len(await self.cursor.fetchall()) >= 5:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['warning']}  Limit Reached",
                "You can only host up to **5** giveaways per server."
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return

        converted = self.convert(time)
        if converted / 60 >= 50400:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['warning']}  Time Too Long",
                "Time cannot exceed **35 days**."
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return
        if converted == -1:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['cross']}  Invalid Time",
                "Use a valid unit: `s`, `m`, `h`, `d`\nExample: `10m`, `1h`, `2d`"
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return
        if converted == -2:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['cross']}  Invalid Format",
                "Time must start with a number.\nExample: `30m`, `2h`"
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return

        # ── build giveaway embed ──────────────────────────────────────────────
        ends_ts  = datetime.datetime.now().timestamp() + converted
        ends_utc = datetime.datetime.utcnow() + datetime.timedelta(seconds=converted)
        ends_utc = ends_utc.replace(tzinfo=datetime.timezone.utc)

        em = discord.Embed(
            title=f"{E['gift']}  {prize}",
            description=(
                f"{E['dot']} **Winners:** `{winners}`\n"
                f"{E['dot']} **Ends:** <t:{round(ends_ts)}:R>  (<t:{round(ends_ts)}:f>)\n"
                f"{E['dot']} **Hosted by:** {ctx.author.mention}\n\n"
                f"React with {E['react']} to enter!"
            ),
            color=BOT_COLOR,
            timestamp=ends_utc,
        )
        try:
            em.set_thumbnail(url=GIFT_THUMB)
            em.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            em.set_footer(
                text="Ends at",
                icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
            )
        except Exception:
            pass

        # ── send & react ──────────────────────────────────────────────────────
        message = await ctx.send(
            f"{E['gift']}  **GIVEAWAY**  {E['gift']}",
            embed=em
        )
        try:
            await ctx.message.delete()
        except Exception:
            pass

        await self.cursor.execute(
            "INSERT INTO Giveaway(guild_id, host_id, start_time, ends_at, prize, winners, message_id, channel_id) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, ctx.author.id, datetime.datetime.now().timestamp(),
             ends_ts, prize, winners, message.id, ctx.channel.id)
        )
        await message.add_reaction(E["react"])
        await self.connection.commit()

    # ── gend ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="gend", description="Ends a giveaway before its time.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def gend(
        self, ctx,
        message_id: str = commands.parameter(description="Message ID of the giveaway", default=None)
    ):
        current_ts = datetime.datetime.now().timestamp()

        # ── by message_id ─────────────────────────────────────────────────────
        if message_id is not None:
            try:
                message_id = int(message_id)
            except ValueError:
                msg = await ctx.send(embed=self._err_embed(
                    f"{E['warning']}  Invalid ID",
                    "Please provide a valid message ID."
                ))
                await asyncio.sleep(5)
                await msg.delete()
                return

            await self.cursor.execute(
                'SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id '
                'FROM Giveaway WHERE message_id = ?', (message_id,)
            )
            re = await self.cursor.fetchone()
            if re is None:
                msg = await ctx.send(embed=self._err_embed(
                    f"{E['cross']}  Not Found",
                    "Giveaway not found. Make sure the ID is correct."
                ))
                await asyncio.sleep(5)
                await msg.delete()
                return

            ch      = self.bot.get_channel(int(re[6]))
            message = await ch.fetch_message(int(message_id))

        # ── by reply ──────────────────────────────────────────────────────────
        elif ctx.message.reference:
            await self.cursor.execute(
                'SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id '
                'FROM Giveaway WHERE message_id = ?',
                (ctx.message.reference.resolved.id,)
            )
            re = await self.cursor.fetchone()
            if re is None:
                return await ctx.send("Giveaway not found.")

            message = await ctx.fetch_message(ctx.message.reference.message_id)

        else:
            await ctx.send("Reply to the giveaway message or provide the giveaway message ID.")
            return

        # ── end it ────────────────────────────────────────────────────────────
        users = [i.id async for i in message.reactions[0].users()]
        try:
            users.remove(self.bot.user.id)
        except Exception:
            pass

        prize   = re[5]
        host_id = int(re[3])

        if len(users) < 1:
            em = discord.Embed(
                title=f"{E['gift']}  Giveaway Ended — No Winners",
                description=(
                    f"{E['dot']} **Prize:** {prize}\n"
                    f"{E['dot']} **Reason:** Not enough participants."
                ),
                color=0xFF4444,
                timestamp=discord.utils.utcnow(),
            )
            em.set_footer(text="Giveaway Ended")
            await message.edit(content=f"{E['gift']}  **GIVEAWAY ENDED**  {E['gift']}", embed=em)
            await message.reply(f"{E['cross']}  No one won **{prize}** — not enough participants.")
            await self.cursor.execute(
                "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
                (message.id, message.guild.id)
            )
            await self.connection.commit()
            return

        win_count = min(len(users), int(re[4]))
        winner    = ', '.join(f'<@{i}>' for i in random.sample(users, k=win_count))
        em        = self._ended_embed(prize, host_id, winner, int(current_ts))

        await message.edit(content=f"{E['gift']}  **GIVEAWAY ENDED**  {E['gift']}", embed=em)

        if ctx.channel.id != int(re[6]):
            await ctx.send(
                embed=discord.Embed(
                    description=f"{E['tick']}  Ended giveaway in <#{int(re[6])}>",
                    color=0x2ECC71
                )
            )

        await message.reply(
            f"{E['trophy']}  Congrats {winner}! You won **{prize}**!\n"
            f"{E['host']}  Hosted by <@{host_id}>"
        )
        await self.cursor.execute(
            "DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?",
            (message.id, message.guild.id)
        )
        await self.connection.commit()

    # ── greroll ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="greroll", description="Rerolls a ended giveaway.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def greroll(
        self, ctx,
        message_id: typing.Optional[int] = commands.parameter(
            description="Message ID of the ended giveaway", default=None
        )
    ):
        if not ctx.message.reference and message_id is None:
            msg = await ctx.reply("Reply to the ended giveaway message or provide its ID.")
            await asyncio.sleep(5)
            await msg.delete()
            return

        if ctx.message.reference and message_id is None:
            message_id = ctx.message.reference.resolved.id

        message = await ctx.fetch_message(message_id)

        if ctx.message.reference and ctx.message.reference.resolved.author.id != self.bot.user.id:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['warning']}  Not a Giveaway",
                "The replied message is not a bot giveaway."
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return

        await self.cursor.execute(
            "SELECT message_id FROM Giveaway WHERE message_id = ?", (message.id,)
        )
        if await self.cursor.fetchone() is not None:
            msg = await ctx.send(embed=self._err_embed(
                f"{E['warning']}  Still Running",
                "This giveaway is still active. Use `gend` to end it first."
            ))
            await asyncio.sleep(5)
            await msg.delete()
            return

        users = [i.id async for i in message.reactions[0].users()]
        try:
            users.remove(self.bot.user.id)
        except Exception:
            pass

        if len(users) < 1:
            await message.reply(f"{E['cross']}  No one participated — can't reroll.")
            return

        new_winner = random.choice(users)
        await message.reply(
            f"{E['trophy']}  New winner: <@{new_winner}>  — Congratulations!"
        )
        await self.connection.commit()

    # ── glist ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="glist", description="Lists all ongoing giveaways.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_guild_permissions(manage_guild=True)
    async def glist(self, ctx):
        await self.cursor.execute(
            "SELECT prize, ends_at, winners, message_id, channel_id FROM Giveaway WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        giveaways = await self.cursor.fetchall()

        if not giveaways:
            em = discord.Embed(
                description=f"{E['dot']}  No ongoing giveaways in this server.",
                color=BOT_COLOR
            )
            await ctx.send(embed=em)
            return

        em = discord.Embed(
            title=f"{E['gift']}  Ongoing Giveaways",
            color=BOT_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        em.set_footer(text=f"{len(giveaways)}/5 slots used")

        for prize, ends_at, winners, message_id, channel_id in giveaways:
            em.add_field(
                name=f"{E['dot']}  {prize}",
                value=(
                    f"{E['timer']} Ends: <t:{int(ends_at)}:R>  (<t:{int(ends_at)}:f>)\n"
                    f"{E['crown']} Winners: **{winners}**\n"
                    f"{E['arrow']} [Jump to Giveaway](https://discord.com/channels/{ctx.guild.id}/{channel_id}/{message_id})"
                ),
                inline=False,
            )

        await ctx.send(embed=em)

    # ── on_message_delete ─────────────────────────────────────────────────────
    @commands.Cog.listener("on_message_delete")
    async def GiveawayMessageDelete(self, message):
        if message.guild is None or message.author != self.bot.user:
            return
        await self.cursor.execute(
            "SELECT message_id FROM Giveaway WHERE guild_id = ?", (message.guild.id,)
        )
        re = await self.cursor.fetchone()
        if re is not None and message.id == int(re[0]):
            await self.cursor.execute(
                "DELETE FROM Giveaway WHERE channel_id = ? AND message_id = ? AND guild_id = ?",
                (message.channel.id, message.id, message.guild.id)
            )
            await self.connection.commit()


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
