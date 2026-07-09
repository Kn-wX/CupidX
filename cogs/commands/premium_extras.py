import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import datetime
import re
from core import Cog
from utils.config import OWNER_IDS
from utils.detectfile import *

# ============================================================
#  DB PATH
# ============================================================
PREMIUM_DB = "db/premium.db"
SHADOW_DB  = "db/shadowban.db"
REMIND_DB  = "db/reminders.db"

BOT_COLOR  = 0x000000

# ============================================================
#  EMOJIS  (same as rest of bot)
# ============================================================
E = {
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "premium":  EMOJI_DIAMOND,
    "tick":     EMOJI_TICK,
    "cross":    EMOJI_CROSS,
    "shield":   EMOJI_SHIELD,
    "settings": "<:cog:1487152125069889677>",
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "fire":     EMOJI_FIRE,
    "timer":    EMOJI_TIMER2,
    "warning":  "<:icons_warning:1327829522573430864>",
    "loading":  EMOJI_LOADING,
    "lock":     EMOJI_KEY,
    "trash":    EMOJI_TRASH,
}

# ============================================================
#  PREMIUM CHECK HELPERS
# ============================================================
async def is_guild_premium(guild_id: int) -> bool:
    async with aiosqlite.connect(PREMIUM_DB) as db:
        async with db.execute(
            "SELECT guild_id FROM premium_guilds WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


def premium_embed(ctx) -> discord.Embed:
    return discord.Embed(
        description=(
            f"{E['warning']} This is a **Premium Only** command.\n"
            f"Use `{ctx.prefix}premium redeem <code>` or contact the bot owner."
        ),
        color=0xFCD005,
    )


def no_perm_embed(perm: str) -> discord.Embed:
    return discord.Embed(
        description=f"{E['cross']} You need **{perm}** permission to use this.",
        color=0xFF0000,
    )


def owner_only_embed() -> discord.Embed:
    return discord.Embed(
        description=f"{E['cross']} This command can only be used by the **Server Owner** or **Bot Owners**.",
        color=0xFF0000,
    )


def is_owner_or_guild_owner(ctx) -> bool:
    return ctx.author.id in OWNER_IDS or ctx.author.id == ctx.guild.owner_id


# ============================================================
#  DURATION PARSER  (e.g. 10m, 2h, 1d)
# ============================================================
def parse_time(duration: str) -> int | None:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.fullmatch(r"(\d+)([smhd])", duration.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    return amount * units[unit]


# ============================================================
#  COG CLASS
# ============================================================
class PremiumExtras(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.raid_mode_guilds: set[int] = set()
        self.shadow_bans: dict[int, set[int]] = {}
        bot.loop.create_task(self._init_db())
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # ----------------------------------------------------------
    #  DATABASE SETUP
    # ----------------------------------------------------------
    async def _init_db(self):
        async with aiosqlite.connect(SHADOW_DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS shadowbans (
                    guild_id INTEGER,
                    user_id  INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

        async with aiosqlite.connect(REMIND_DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    channel_id INTEGER,
                    guild_id   INTEGER,
                    remind_at  TEXT,
                    message    TEXT
                )
            """)
            await db.commit()

        async with aiosqlite.connect(SHADOW_DB) as db:
            async with db.execute("SELECT guild_id, user_id FROM shadowbans") as cur:
                async for row in cur:
                    gid, uid = row
                    self.shadow_bans.setdefault(gid, set()).add(uid)

    # ============================================================
    #  1. ANTIRAID
    #  Usage: .antiraid on/off
    #  Access: Server Owner + Bot Owners only
    # ============================================================
    @commands.hybrid_command(
        name="antiraid",
        description="🛡️ Auto-lockdown the server when a raid is detected (Premium)"
    )
    async def antiraid(self, ctx, action: str = None):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        if action is None:
            status = "🟢 **ON**" if ctx.guild.id in self.raid_mode_guilds else "🔴 **OFF**"
            embed = discord.Embed(
                title=f"{E['shield']}  Anti-Raid Status",
                description=(
                    f"Current Status: {status}\n\n"
                    f"{E['dot']} `{ctx.prefix}antiraid on` — Enable anti-raid\n"
                    f"{E['dot']} `{ctx.prefix}antiraid off` — Disable anti-raid\n\n"
                    f"-# When a raid is detected, the bot will automatically restrict channel permissions for everyone."
                ),
                color=BOT_COLOR,
            )
            return await ctx.reply(embed=embed)

        action = action.lower()
        if action == "on":
            self.raid_mode_guilds.add(ctx.guild.id)
            embed = discord.Embed(
                description=f"{E['tick']} **Anti-Raid enabled!**\nIf 10 or more users join within a minute, the server will be auto-locked.",
                color=0x00FF77,
            )
        elif action == "off":
            self.raid_mode_guilds.discard(ctx.guild.id)
            embed = discord.Embed(
                description=f"{E['tick']} **Anti-Raid disabled.**",
                color=0x00FF77,
            )
        else:
            embed = discord.Embed(
                description=f"{E['cross']} Invalid option. Use `on` or `off`.",
                color=0xFF0000,
            )
        await ctx.reply(embed=embed)

    # Raid Detector — member join event
    join_tracker: dict[int, list] = {}

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if guild.id not in self.raid_mode_guilds:
            return

        now = datetime.datetime.utcnow().timestamp()
        tracker = self.join_tracker.setdefault(guild.id, [])
        tracker.append(now)
        self.join_tracker[guild.id] = [t for t in tracker if now - t <= 60]

        if len(self.join_tracker[guild.id]) >= 10:
            self.join_tracker[guild.id] = []
            await self._lockdown_server(guild)

    async def _lockdown_server(self, guild: discord.Guild):
        everyone = guild.default_role
        locked = 0
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(everyone)
                overwrite.send_messages = False
                await channel.set_permissions(everyone, overwrite=overwrite, reason="Anti-Raid: Auto Lockdown")
                locked += 1
            except Exception:
                pass

        log_ch = discord.utils.get(guild.text_channels, name="mod-logs") or \
                 discord.utils.get(guild.text_channels, name="logs") or \
                 guild.system_channel
        if log_ch:
            embed = discord.Embed(
                title="🚨 RAID DETECTED — SERVER LOCKED",
                description=(
                    f"{E['shield']} Anti-Raid has locked **{locked} channels**.\n"
                    f"To unlock manually, use `{guild.me.mention}` or `$antiraid off`."
                ),
                color=0xFF0000,
                timestamp=datetime.datetime.utcnow(),
            )
            await log_ch.send(embed=embed)

    # ============================================================
    #  2. SERVERLOCK
    #  Usage: .serverlock [reason]
    #         .serverunlock [reason]
    #  Access: Server Owner + Bot Owners only
    # ============================================================
    @commands.command(
        name="serverlock",
        description="🔒 Lock the entire server with a single command (Premium)"
    )
    async def serverlock(self, ctx, *, reason: str = "No reason provided"):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        await ctx.defer()
        everyone = ctx.guild.default_role
        locked = 0
        failed = 0

        for channel in ctx.guild.text_channels:
            try:
                ow = channel.overwrites_for(everyone)
                ow.send_messages = False
                await channel.set_permissions(everyone, overwrite=ow, reason=f"ServerLock by {ctx.author}: {reason}")
                locked += 1
            except Exception:
                failed += 1

        embed = discord.Embed(
            title=f"{E['lock']}  Server Locked",
            description=(
                f"{E['dot']} **Locked Channels:** `{locked}`\n"
                f"{E['dot']} **Failed:** `{failed}`\n"
                f"{E['dot']} **Reason:** {reason}\n"
                f"{E['dot']} **By:** {ctx.author.mention}\n\n"
                f"-# To unlock, use `{ctx.prefix}serverunlock`."
            ),
            color=0xFF4444,
            timestamp=datetime.datetime.utcnow(),
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="serverunlock",
        description="🔓 Unlock the server (Premium)"
    )
    async def serverunlock(self, ctx, *, reason: str = "No reason provided"):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        await ctx.defer()
        everyone = ctx.guild.default_role
        unlocked = 0
        failed = 0

        for channel in ctx.guild.text_channels:
            try:
                ow = channel.overwrites_for(everyone)
                ow.send_messages = None
                await channel.set_permissions(everyone, overwrite=ow, reason=f"ServerUnlock by {ctx.author}: {reason}")
                unlocked += 1
            except Exception:
                failed += 1

        embed = discord.Embed(
            title=f"{E['tick']}  Server Unlocked",
            description=(
                f"{E['dot']} **Unlocked Channels:** `{unlocked}`\n"
                f"{E['dot']} **Failed:** `{failed}`\n"
                f"{E['dot']} **Reason:** {reason}\n"
                f"{E['dot']} **By:** {ctx.author.mention}"
            ),
            color=0x00FF77,
            timestamp=datetime.datetime.utcnow(),
        )
        await ctx.reply(embed=embed)

    # ============================================================
    #  3. FAKEPERMIT
    #  Usage: .fakepermit @user <permission name>
    #  Access: Server Owner + Bot Owners only
    # ============================================================
    @commands.hybrid_command(
        name="fakepermit",
        description="🎭 Send a fake permission granted embed to someone (Prank) (Premium)"
    )
    async def fakepermit(self, ctx, member: discord.Member, *, permission: str = "Administrator"):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        embed = discord.Embed(
            title="✅  Permission Granted",
            description=(
                f"**User:** {member.mention}\n"
                f"**Permission:** `{permission}`\n"
                f"**Server:** {ctx.guild.name}\n"
                f"**Granted by:** {ctx.author.mention}\n\n"
                f"-# This permission has been successfully applied to the user."
            ),
            color=0x00FF77,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{ctx.guild.name} • Permission System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.channel.send(embed=embed)

    # ============================================================
    #  4. EMBEDBUILDER
    #  Usage: .embedbuilder [#channel]
    #  Access: Server Owner + Bot Owners only
    # ============================================================
    @commands.command(
        name="embedbuilder",
        description="🎨 Interactive embed builder — create embeds without any coding (Premium)"
    )
    async def embedbuilder(self, ctx, channel: discord.TextChannel = None):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        target = channel or ctx.channel

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        async def ask(question: str) -> str | None:
            prompt = discord.Embed(description=question, color=BOT_COLOR)
            prompt.set_footer(text="Type 'skip' to leave blank • 60s timeout")
            await ctx.channel.send(embed=prompt)
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                return None if msg.content.lower() == "skip" else msg.content
            except asyncio.TimeoutError:
                return None

        await ctx.reply(embed=discord.Embed(
            description=f"{E['loading']} **Embed Builder is starting!**\nType a value for each step or type `skip` to leave it blank.",
            color=BOT_COLOR,
        ))

        title       = await ask(f"{E['dot']} **Step 1/5** — What should the **Title** be?")
        description = await ask(f"{E['dot']} **Step 2/5** — What should the **Description** be?")
        color_str   = await ask(f"{E['dot']} **Step 3/5** — **Color** (hex code, e.g. `#FF0000`) or skip?")
        image_url   = await ask(f"{E['dot']} **Step 4/5** — Enter an **Image URL** or skip?")
        footer_text = await ask(f"{E['dot']} **Step 5/5** — What should the **Footer text** say?")

        color = BOT_COLOR
        if color_str:
            try:
                color = int(color_str.strip("#"), 16)
            except ValueError:
                pass

        final = discord.Embed(color=color, timestamp=datetime.datetime.utcnow())
        if title:       final.title       = title
        if description: final.description = description
        if footer_text: final.set_footer(text=footer_text)
        if image_url:
            try:
                final.set_image(url=image_url)
            except Exception:
                pass

        preview_msg = await ctx.channel.send(
            content=f"{E['star']} **Preview** (channel: {target.mention}):",
            embed=final
        )

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False

            @discord.ui.button(label="Send ✅", style=discord.ButtonStyle.success)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ This menu is not yours!", ephemeral=True)
                self.confirmed = True
                self.stop()
                await interaction.response.defer()

            @discord.ui.button(label="Cancel ✖️", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ This menu is not yours!", ephemeral=True)
                self.stop()
                await interaction.response.defer()

        view = ConfirmView()
        confirm_msg = await ctx.channel.send(
            embed=discord.Embed(description=f"{E['arrow']} Should I send this embed to **{target.mention}**?", color=BOT_COLOR),
            view=view
        )
        await view.wait()

        if view.confirmed:
            await target.send(embed=final)
            await confirm_msg.edit(
                embed=discord.Embed(description=f"{E['tick']} Embed sent to {target.mention}!", color=0x00FF77),
                view=None
            )
        else:
            await confirm_msg.edit(
                embed=discord.Embed(description=f"{E['cross']} Embed builder cancelled.", color=0xFF0000),
                view=None
            )

    # ============================================================
    #  5. REMINDER
    #  Usage: .reminder <time> <message>
    #  Access: Server Owner + Bot Owners only
    # ============================================================
    @commands.command(
        name="reminder",
        description="⏰ The bot will DM you a reminder after the specified time (Premium)"
    )
    async def reminder(self, ctx, time: str, *, message: str):
        if not await is_guild_premium(ctx.guild.id):
            return await ctx.reply(embed=premium_embed(ctx))
        if not is_owner_or_guild_owner(ctx):
            return await ctx.reply(embed=owner_only_embed())

        seconds = parse_time(time)
        if not seconds:
            return await ctx.reply(embed=discord.Embed(
                description=f"{E['cross']} Invalid time format! Use: `10m`, `2h`, `1d`",
                color=0xFF0000,
            ))

        if seconds > 86400 * 7:
            return await ctx.reply(embed=discord.Embed(
                description=f"{E['cross']} Maximum reminder time is **7 days**!",
                color=0xFF0000,
            ))

        remind_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)).isoformat()

        async with aiosqlite.connect(REMIND_DB) as db:
            await db.execute(
                "INSERT INTO reminders (user_id, channel_id, guild_id, remind_at, message) VALUES (?,?,?,?,?)",
                (ctx.author.id, ctx.channel.id, ctx.guild.id, remind_at, message)
            )
            await db.commit()

        if seconds < 3600:
            readable = f"{seconds // 60} minutes"
        elif seconds < 86400:
            readable = f"{seconds // 3600} hours"
        else:
            readable = f"{seconds // 86400} days"

        ts = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        embed = discord.Embed(
            title=f"{E['timer']}  Reminder Set!",
            description=(
                f"{E['dot']} **Message:** {message}\n"
                f"{E['dot']} **Time:** In {readable} (<t:{ts}:R>)\n"
                f"{E['dot']} **Alert:** The bot will DM you ⏰"
            ),
            color=BOT_COLOR,
        )
        await ctx.reply(embed=embed)

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.utcnow().isoformat()

        async with aiosqlite.connect(REMIND_DB) as db:
            async with db.execute(
                "SELECT id, user_id, channel_id, message FROM reminders WHERE remind_at <= ?", (now,)
            ) as cur:
                due = await cur.fetchall()

            for row in due:
                rid, user_id, channel_id, message = row
                await db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
                await db.commit()

                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except Exception:
                        continue

                embed = discord.Embed(
                    title="⏰  Reminder!",
                    description=f"{E['dot']} **Your reminder:**\n{message}",
                    color=BOT_COLOR,
                    timestamp=datetime.datetime.utcnow(),
                )
                try:
                    await user.send(embed=embed)
                except discord.Forbidden:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(f"{user.mention}", embed=embed)


# ============================================================
#  SETUP
# ============================================================
async def setup(bot):
    await bot.add_cog(PremiumExtras(bot))
