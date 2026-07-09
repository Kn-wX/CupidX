from discord.ext import commands, tasks
from discord import *
import discord
import aiosqlite
from typing import Optional
from datetime import datetime, timedelta
from discord.ui import View, Button, Select
from utils.config import OWNER_IDS, SUPPORT_SERVER
from utils.detectfile import *
from utils import Paginator, DescriptionEmbedPaginator


NP_GUILD_ID  = 1341267203940679732
NP_ROLE_ID   = 1472594546796921057
LOG_CHANNEL  = 1477619571732123700
PING_CHANNEL = 1463576455920484352
# BOT_ICON imported from utils.detectfile

# ── Emojis ─────────────────────────────────────────────────────────────────────
PREMIUM  = "<:16218booster:1486976482118205553>"
TIMER    = "<a:CupidXtimer:1475327919558496370>"
ARROW    = "<:CupidXarrow:1474383919725150362>"
WARNING  = "<:CupidXWarning:1474348304186867784>"
TICK     = "<:CupidXtick1:1474369967271968949>"
INFO     = "<:CupidXfun:1472259051868917842>"
UADMIN   = "<:CupidXautomod:1474356609122697382>"
WARN_ANI = "<:CupidXWarning:1474348304186867784>"
# ──────────────────────────────────────────────────────────────────────────────

DURATION_MAP = {
    "10m":      timedelta(minutes=10),
    "1w":       timedelta(weeks=1),
    "3w":       timedelta(weeks=3),
    "1m":       timedelta(days=30),
    "3m":       timedelta(days=90),
    "6m":       timedelta(days=180),
    "1y":       timedelta(days=365),
    "3y":       timedelta(days=365 * 3),
    "lifetime": None,
}

DURATION_LABELS = {
    "10m":      "10 Minutes  •  Trial",
    "1w":       "1 Week",
    "3w":       "3 Weeks",
    "1m":       "1 Month",
    "3m":       "3 Months",
    "6m":       "6 Months",
    "1y":       "1 Year",
    "3y":       "3 Years",
    "lifetime": "Lifetime  •  Permanent",
}


def load_owner_ids():
    return OWNER_IDS


async def is_staff(user, staff_ids):
    return user.id in staff_ids


async def is_owner_or_staff(ctx):
    return await is_staff(ctx.author, ctx.cog.staff) or ctx.author.id in OWNER_IDS


# ══════════════════════════════════════════════════════════════════════════════
#  Duration Select Menu
# ══════════════════════════════════════════════════════════════════════════════
class TimeSelect(Select):
    def __init__(self, user, db_path, author):
        super().__init__(
            placeholder="⏳  Select No-Prefix Duration…",
            min_values=1,
            max_values=1,
        )
        self.user    = user
        self.db_path = db_path
        self.author  = author

        self.options = [
            SelectOption(label="⚡  10 Minutes",  description="Trial — expires in 10 minutes",    value="10m",      emoji="⚡"),
            SelectOption(label="📅  1 Week",       description="No Prefix active for 1 week",       value="1w",       emoji="📅"),
            SelectOption(label="📅  3 Weeks",      description="No Prefix active for 3 weeks",      value="3w",       emoji="📅"),
            SelectOption(label="🗓️  1 Month",      description="No Prefix active for 1 month",      value="1m",       emoji="🗓️"),
            SelectOption(label="🗓️  3 Months",     description="No Prefix active for 3 months",     value="3m",       emoji="🗓️"),
            SelectOption(label="🗓️  6 Months",     description="No Prefix active for 6 months",     value="6m",       emoji="🗓️"),
            SelectOption(label="🌟  1 Year",        description="No Prefix active for 1 full year",  value="1y",       emoji="🌟"),
            SelectOption(label="💎  3 Years",       description="No Prefix active for 3 years",      value="3y",       emoji="💎"),
            SelectOption(label="♾️  Lifetime",      description="No Prefix — never expires",         value="lifetime", emoji="♾️"),
        ]

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message(
                f"{WARNING} This menu is not for you.", ephemeral=True
            )

        sel         = self.values[0]
        is_lifetime = (sel == "lifetime")
        expiry_time = None if is_lifetime else datetime.utcnow() + DURATION_MAP[sel]
        expiry_str  = None if is_lifetime else expiry_time.isoformat()
        tier_label  = DURATION_LABELS.get(sel, sel.upper())

        # ── Save to DB ─────────────────────────────────────────────────────────
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO np (id, expiry_time) VALUES (?, ?)",
                (self.user.id, expiry_str),
            )
            await db.commit()

        # ── Formatted expiry strings ───────────────────────────────────────────
        if is_lifetime:
            expiry_display = "♾️  **Never**  *(Lifetime)*"
            expiry_stamp   = "♾️ Permanent"
            expiry_rel     = ""
        else:
            ts             = int(expiry_time.timestamp())
            expiry_display = f"<t:{ts}:F>"
            expiry_stamp   = f"<t:{ts}:F>"
            expiry_rel     = f"  *(expires <t:{ts}:R>)*"

        # ── Grant role ─────────────────────────────────────────────────────────
        guild = interaction.client.get_guild(NP_GUILD_ID)
        if guild:
            member = guild.get_member(self.user.id)
            if member:
                role = guild.get_role(NP_ROLE_ID)
                if role:
                    await member.add_roles(role, reason="No Prefix granted by staff")

        # ── Log Embed ──────────────────────────────────────────────────────────
        log_channel = interaction.client.get_channel(LOG_CHANNEL)
        if log_channel:
            log_em = discord.Embed(
                title=f"{PREMIUM}  No Prefix Granted",
                color=0x000000,
                timestamp=datetime.utcnow(),
            )
            log_em.set_thumbnail(url=self.user.display_avatar.url)
            log_em.add_field(
                name=f"{UADMIN}  User",
                value=(
                    f"[**{self.user}**](https://discord.com/users/{self.user.id})\n"
                    f"{self.user.mention}\n"
                    f"`{self.user.id}`"
                ),
                inline=True,
            )
            log_em.add_field(
                name=f"<:crown:1486975202125680753>  Granted By",
                value=(
                    f"[**{self.author.display_name}**](https://discord.com/users/{self.author.id})\n"
                    f"{self.author.mention}"
                ),
                inline=True,
            )
            log_em.add_field(name="\u200b", value="\u200b", inline=True)
            log_em.add_field(name=f"{TIMER}  Tier",    value=f"`{tier_label}`",             inline=True)
            log_em.add_field(name=f"📅  Expires",      value=f"{expiry_stamp}{expiry_rel}",  inline=True)
            log_em.set_footer(text="CupidX  •  No Prefix Log", icon_url=BOT_ICON)
            await log_channel.send(f"<#{PING_CHANNEL}>", embed=log_em)

        # ── Response Embed ─────────────────────────────────────────────────────
        resp_em = discord.Embed(
            title=f"{PREMIUM}  Global No Prefix Granted",
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        resp_em.set_thumbnail(url=self.user.display_avatar.url)
        resp_em.add_field(
            name=f"{UADMIN}  Recipient",
            value=(
                f"[**{self.user}**](https://discord.com/users/{self.user.id})\n"
                f"{self.user.mention}\n"
                f"`{self.user.id}`"
            ),
            inline=True,
        )
        resp_em.add_field(
            name=f"<:crown:1486975202125680753>  Granted By",
            value=f"[**{self.author.display_name}**](https://discord.com/users/{self.author.id})",
            inline=True,
        )
        resp_em.add_field(name="\u200b", value="\u200b", inline=True)
        resp_em.add_field(name=f"{TIMER}  Duration", value=f"`{tier_label}`",            inline=True)
        resp_em.add_field(name=f"📅  Expires",       value=f"{expiry_display}{expiry_rel}", inline=True)
        resp_em.set_author(name="No Prefix Added", icon_url=BOT_ICON)
        resp_em.set_footer(
            text="CupidX  •  A DM will be sent to the user when No Prefix expires.",
            icon_url=BOT_ICON,
        )
        await interaction.response.edit_message(embed=resp_em, view=None)


class TimeSelectView(View):
    def __init__(self, user, db_path, author):
        super().__init__(timeout=60)
        self.user    = user
        self.db_path = db_path
        self.author  = author
        self.add_item(TimeSelect(user, db_path, author))


# ══════════════════════════════════════════════════════════════════════════════
#  NoPrefix Cog
# ══════════════════════════════════════════════════════════════════════════════
class NoPrefix(commands.Cog):
    def __init__(self, client):
        self.client  = client
        self.staff   = set()
        self.db_path = "db/np.db"
        self.client.loop.create_task(self.load_staff())
        self.client.loop.create_task(self.setup_database())
        self.expiry_check.start()

    # ── Database Setup ─────────────────────────────────────────────────────────
    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS np (
                    id INTEGER PRIMARY KEY
                )
            """)
            async with db.execute("PRAGMA table_info(np);") as cursor:
                columns = [info[1] for info in await cursor.fetchall()]
            if "expiry_time" not in columns:
                await db.execute("ALTER TABLE np ADD COLUMN expiry_time TEXT NULL;")
            await db.execute("UPDATE np SET expiry_time = NULL WHERE expiry_time IS NULL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS autonp (
                    guild_id INTEGER PRIMARY KEY
                )
            """)
            await db.commit()

    async def load_staff(self):
        await self.client.wait_until_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM staff") as cursor:
                self.staff = {row[0] for row in await cursor.fetchall()}

    # ── Expiry Task ────────────────────────────────────────────────────────────
    @tasks.loop(minutes=10)
    async def expiry_check(self):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow().isoformat()
            async with db.execute(
                "SELECT id FROM np WHERE expiry_time IS NOT NULL AND expiry_time <= ?", (now,)
            ) as cursor:
                expired_users = [row[0] for row in await cursor.fetchall()]

            if expired_users:
                async with db.execute(
                    "DELETE FROM np WHERE id IN ({})".format(",".join("?" * len(expired_users))),
                    expired_users,
                ):
                    await db.commit()

                for user_id in expired_users:
                    user = self.client.get_user(user_id)
                    if not user:
                        continue

                    # ── Remove role ────────────────────────────────────────────
                    guild = self.client.get_guild(NP_GUILD_ID)
                    if guild:
                        member = guild.get_member(user.id)
                        if member:
                            role = guild.get_role(NP_ROLE_ID)
                            if role and role in member.roles:
                                await member.remove_roles(role, reason="No Prefix expired")

                    # ── Log embed ──────────────────────────────────────────────
                    log_channel = self.client.get_channel(LOG_CHANNEL)
                    if log_channel:
                        log_em = discord.Embed(
                            title=f"{WARNING}  No Prefix Expired",
                            color=0x000000,
                            timestamp=datetime.utcnow(),
                        )
                        log_em.set_thumbnail(url=user.display_avatar.url)
                        log_em.add_field(
                            name=f"{UADMIN}  User",
                            value=(
                                f"[**{user}**](https://discord.com/users/{user.id})\n"
                                f"{user.mention}\n"
                                f"`{user.id}`"
                            ),
                            inline=True,
                        )
                        log_em.add_field(
                            name="🛡️  Removed By",
                            value="CupidX Auto-Expiry System",
                            inline=True,
                        )
                        log_em.set_footer(text="CupidX  •  No Prefix Expiry Log", icon_url=BOT_ICON)
                        await log_channel.send(f"<#{LOG_CHANNEL}>", embed=log_em)

                    # ── DM user ────────────────────────────────────────────────
                    dm_em = discord.Embed(
                        title=f"{WARN_ANI}  No Prefix Expired",
                        description=(
                            f"Hey {user.mention}, your **Global No Prefix** has expired!\n\n"
                            f"You will now need a **prefix** to use my commands.\n"
                            f"If you think this is a mistake, reach out to our [Support Server]({SUPPORT_SERVER})."
                        ),
                        color=0x000000,
                        timestamp=datetime.utcnow(),
                    )
                    dm_em.set_author(name="CupidX  —  No Prefix", icon_url=BOT_ICON)
                    dm_em.set_thumbnail(url=user.display_avatar.url)
                    dm_em.set_footer(text="CupidX  •  Join support to regain access.")
                    support_btn = Button(label="Support Server", style=discord.ButtonStyle.link, url=SUPPORT_SERVER, emoji="💬")
                    view        = View()
                    view.add_item(support_btn)
                    try:
                        await user.send(embed=dm_em, view=view)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

    @expiry_check.before_loop
    async def before_expiry_check(self):
        await self.client.wait_until_ready()

    # ══════════════════════════════════════════════════════════════════════════
    #  np (base group)
    # ══════════════════════════════════════════════════════════════════════════
    @commands.group(name="np", help="Manage Global No Prefix users.")
    @commands.check(is_owner_or_staff)
    async def _np(self, ctx):
        if ctx.invoked_subcommand is None:
            em = discord.Embed(
                title=f"{PREMIUM}  Global No Prefix  —  Control Panel",
                description="Manage users who can use the bot **without a prefix**.",
                color=0x000000,
            )
            em.set_author(name="CupidX  •  No Prefix", icon_url=BOT_ICON)
            em.set_thumbnail(url=self.client.user.display_avatar.url)
            em.add_field(
                name="📋  Available Commands",
                value=(
                    f"{ARROW} `{ctx.prefix}np add <user>` — Grant No Prefix\n"
                    f"{ARROW} `{ctx.prefix}np remove <user>` — Revoke No Prefix\n"
                    f"{ARROW} `{ctx.prefix}np status <user>` — Check user's status\n"
                    f"{ARROW} `{ctx.prefix}np list` — View all No Prefix users\n"
                    f"{ARROW} `{ctx.prefix}np reset` — ⚠️ Wipe entire list"
                ),
                inline=False,
            )
            em.set_footer(text="CupidX  •  Staff Only", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em, mention_author=False)

    # ── np list ────────────────────────────────────────────────────────────────
    @_np.command(name="list", help="List all no-prefix users with expiry info.")
    @commands.check(is_owner_or_staff)
    async def np_list(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, expiry_time FROM np ORDER BY expiry_time ASC"
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            em = discord.Embed(
                title=f"{INFO}  No Prefix List",
                description="No users currently have No Prefix.",
                color=0x000000,
            )
            return await ctx.reply(embed=em, mention_author=False)

        entries = []
        for i, (uid, expiry) in enumerate(rows, start=1):
            if expiry:
                try:
                    exp_dt  = datetime.fromisoformat(expiry)
                    ts      = int(exp_dt.timestamp())
                    exp_str = f"<t:{ts}:R>"
                    badge   = "⏳"
                except Exception:
                    exp_str = "`Unknown`"
                    badge   = "❓"
            else:
                exp_str = "♾️ **Lifetime**"
                badge   = "<a:CupidXdot:1473986328126558209>"

            entries.append(
                f"`#{i:02}`  {badge}  "
                f"[**View Profile**](https://discord.com/users/{uid})  •  "
                f"`{uid}`\n"
                f"> {TIMER} Expires: {exp_str}"
            )

        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"{PREMIUM}  No Prefix Users  [{len(rows)}]",
                description=f"{INFO}  Showing all active No Prefix holders.\n\u200b",
                per_page=8,
                color=0x000000,
            ),
            ctx=ctx,
        )
        await paginator.paginate()

    # ── np add ─────────────────────────────────────────────────────────────────
    @_np.command(name="add", help="Add a user to the No Prefix list.")
    @commands.check(is_owner_or_staff)
    async def np_add(self, ctx, user: discord.User):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM np WHERE id = ?", (user.id,)) as cursor:
                result = await cursor.fetchone()

        if result:
            em = discord.Embed(
                title=f"{WARNING}  Already Has No Prefix",
                description=(
                    f"{user.mention} (`{user.id}`) already has **No Prefix** active.\n\n"
                    f"{INFO}  Use `{ctx.prefix}np status {user.id}` to check their expiry."
                ),
                color=0x000000,
            )
            em.set_thumbnail(url=user.display_avatar.url)
            em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.reply(embed=em, mention_author=False)

        em = discord.Embed(
            title=f"{PREMIUM}  Grant No Prefix",
            description=(
                f"**Recipient:** {user.mention}  —  [**{user}**](https://discord.com/users/{user.id})\n"
                f"**User ID:** `{user.id}`\n\n"
                f"{ARROW}  Select the **duration** from the menu below."
            ),
            color=0x000000,
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.set_author(name="No Prefix  —  Duration Select", icon_url=BOT_ICON)
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        view = TimeSelectView(user, self.db_path, ctx.author)
        await ctx.reply(embed=em, view=view, mention_author=False)

    # ── np remove ─────────────────────────────────────────────────────────────
    @_np.command(name="remove", help="Remove a user from the No Prefix list.")
    @commands.check(is_owner_or_staff)
    async def np_remove(self, ctx, user: discord.User):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id, expiry_time FROM np WHERE id = ?", (user.id,)) as cursor:
                result = await cursor.fetchone()

            if not result:
                em = discord.Embed(
                    title=f"{WARNING}  Not in No Prefix List",
                    description=(
                        f"{user.mention} (`{user.id}`) does **not** have No Prefix.\n\n"
                        f"{UADMIN}  Requested by [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})"
                    ),
                    color=0x000000,
                )
                em.set_thumbnail(url=user.display_avatar.url)
                em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
                return await ctx.reply(embed=em, mention_author=False)

            await db.execute("DELETE FROM np WHERE id = ?", (user.id,))
            await db.commit()

        # ── Remove role ────────────────────────────────────────────────────────
        guild = ctx.bot.get_guild(NP_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                role = guild.get_role(NP_ROLE_ID)
                if role and role in member.roles:
                    await member.remove_roles(role, reason=f"No Prefix removed by {ctx.author}")

        # ── Response Embed ─────────────────────────────────────────────────────
        em = discord.Embed(
            title=f"{TICK}  No Prefix Removed",
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.add_field(
            name=f"{UADMIN}  User",
            value=(
                f"[**{user}**](https://discord.com/users/{user.id})\n"
                f"{user.mention}\n"
                f"`{user.id}`"
            ),
            inline=True,
        )
        em.add_field(
            name="🛡️  Removed By",
            value=(
                f"[**{ctx.author.display_name}**](https://discord.com/users/{ctx.author.id})\n"
                f"{ctx.author.mention}"
            ),
            inline=True,
        )
        em.set_author(name="No Prefix Revoked", icon_url=BOT_ICON)
        em.set_footer(text="CupidX  •  No Prefix Management", icon_url=BOT_ICON)
        await ctx.reply(embed=em, mention_author=False)

        # ── Log Embed ──────────────────────────────────────────────────────────
        log_channel = ctx.bot.get_channel(LOG_CHANNEL)
        if log_channel:
            log_em = discord.Embed(
                title=f"{WARNING}  No Prefix Removed",
                color=0x000000,
                timestamp=datetime.utcnow(),
            )
            log_em.set_thumbnail(url=user.display_avatar.url)
            log_em.add_field(
                name=f"{UADMIN}  User",
                value=(
                    f"[**{user}**](https://discord.com/users/{user.id})\n"
                    f"{user.mention}  •  `{user.id}`"
                ),
                inline=True,
            )
            log_em.add_field(
                name="🛡️  Removed By",
                value=(
                    f"[**{ctx.author.display_name}**](https://discord.com/users/{ctx.author.id})\n"
                    f"{ctx.author.mention}"
                ),
                inline=True,
            )
            log_em.set_footer(text="CupidX  •  No Prefix Removal Log", icon_url=BOT_ICON)
            await log_channel.send(f"<#{PING_CHANNEL}>", embed=log_em)

    # ── np status ─────────────────────────────────────────────────────────────
    @_np.command(name="status", help="Check a user's No Prefix status and expiry.")
    @commands.check(is_owner_or_staff)
    async def np_status(self, ctx, user: discord.User):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, expiry_time FROM np WHERE id = ?", (user.id,)
            ) as cursor:
                result = await cursor.fetchone()

        if not result:
            em = discord.Embed(
                title=f"{INFO}  No Prefix Status",
                description=(
                    f"{WARNING}  **{user}** does **not** have No Prefix.\n\n"
                    f"{UADMIN}  Requested by [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})"
                ),
                color=0x000000,
            )
            em.set_thumbnail(url=user.display_avatar.url)
            em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.reply(embed=em, mention_author=False)

        _, expires = result

        if expires and expires.lower() != "null":
            exp_dt      = datetime.fromisoformat(expires)
            ts          = int(exp_dt.timestamp())
            exp_display = f"<t:{ts}:F>"
            exp_rel     = f"<t:{ts}:R>"
            badge       = "⏳"
        else:
            exp_display = "♾️  **Lifetime** — Never expires"
            exp_rel     = "♾️ Permanent"
            badge       = "♾️"

        em = discord.Embed(
            title=f"{PREMIUM}  No Prefix Status",
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.add_field(
            name=f"{UADMIN}  User",
            value=(
                f"[**{user}**](https://discord.com/users/{user.id})\n"
                f"{user.mention}\n"
                f"`{user.id}`"
            ),
            inline=True,
        )
        em.add_field(
            name=f"{badge}  Status",
            value=f"✅  **Active**",
            inline=True,
        )
        em.add_field(name="\u200b", value="\u200b", inline=True)
        em.add_field(
            name=f"{TIMER}  Expires",
            value=f"{exp_display}\n{exp_rel}",
            inline=True,
        )
        em.set_author(name="No Prefix  —  User Status", icon_url=BOT_ICON)
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, mention_author=False)

    # ── np reset ──────────────────────────────────────────────────────────────
    @_np.command(name="reset", help="Wipe all users from the No Prefix list.")
    @commands.is_owner()
    async def np_reset(self, ctx):
        em = discord.Embed(
            title=f"{WARNING}  Confirm Full Reset",
            description=(
                "⚠️  This will **permanently remove ALL users** from the No Prefix list.\n"
                "All **No Prefix roles** will also be revoked.\n\n"
                "This action **cannot be undone**. Are you sure?"
            ),
            color=0x000000,
        )
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        yes_btn = Button(label="✅  Confirm Reset", style=discord.ButtonStyle.danger)
        no_btn  = Button(label="❌  Cancel",        style=discord.ButtonStyle.secondary)
        view    = View(timeout=30)
        view.add_item(yes_btn)
        view.add_item(no_btn)

        async def yes_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message(
                    f"{WARNING} This is not your interaction.", ephemeral=True
                )
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM np") as cursor:
                    count = (await cursor.fetchone())[0]
                await db.execute("DELETE FROM np")
                await db.commit()

            guild = self.client.get_guild(NP_GUILD_ID)
            if guild:
                role = guild.get_role(NP_ROLE_ID)
                if role:
                    for member in [m for m in guild.members if role in m.roles]:
                        try:
                            await member.remove_roles(role, reason="Global No Prefix reset")
                        except discord.HTTPException:
                            pass

            done_em = discord.Embed(
                title=f"{TICK}  No Prefix List Reset",
                description=(
                    f"Successfully removed **{count} user(s)** from the No Prefix list.\n"
                    f"All No Prefix roles have been revoked."
                ),
                color=0x000000,
                timestamp=datetime.utcnow(),
            )
            done_em.set_footer(text=f"Reset by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            await interaction.response.edit_message(embed=done_em, view=None)

            log_channel = self.client.get_channel(LOG_CHANNEL)
            if log_channel:
                log_em = discord.Embed(
                    title=f"{WARNING}  No Prefix List Wiped",
                    description=(
                        f"🛡️  **Reset By:** [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})\n"
                        f"{INFO}  **Users Removed:** `{count}`"
                    ),
                    color=0x000000,
                    timestamp=datetime.utcnow(),
                )
                log_em.set_footer(text="CupidX  •  No Prefix Reset Log", icon_url=BOT_ICON)
                await log_channel.send(f"<#{LOG_CHANNEL}>", embed=log_em)

        async def no_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message(
                    f"{WARNING} This is not your interaction.", ephemeral=True
                )
            cancel_em = discord.Embed(
                title="❌  Reset Cancelled",
                description="No changes were made to the No Prefix list.",
                color=0x000000,
            )
            await interaction.response.edit_message(embed=cancel_em, view=None)

        yes_btn.callback = yes_callback
        no_btn.callback  = no_callback
        await ctx.reply(embed=em, view=view, mention_author=False)

    # ══════════════════════════════════════════════════════════════════════════
    #  autonp group
    # ══════════════════════════════════════════════════════════════════════════
    @commands.group(name="autonp", help="Manage auto No Prefix for partner guilds.")
    @commands.is_owner()
    async def autonp(self, ctx):
        if ctx.invoked_subcommand is None:
            em = discord.Embed(
                title=f"{PREMIUM}  Auto No Prefix  —  Partner Guilds",
                description="Automatically grant No Prefix to **server boosters** of partner guilds.",
                color=0x000000,
            )
            em.set_author(name="CupidX  •  Auto No Prefix", icon_url=BOT_ICON)
            em.set_thumbnail(url=self.client.user.display_avatar.url)
            em.add_field(
                name="📋  Subcommands",
                value=(
                    f"{ARROW} `{ctx.prefix}autonp guild add <id>` — Add a partner guild\n"
                    f"{ARROW} `{ctx.prefix}autonp guild remove <id>` — Remove a partner guild\n"
                    f"{ARROW} `{ctx.prefix}autonp guild list` — View all partner guilds"
                ),
                inline=False,
            )
            em.set_footer(text="CupidX  •  Owner Only", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em, mention_author=False)

    @autonp.group(name="guild", help="Manage partner guilds for auto No Prefix.")
    async def autonp_guild(self, ctx):
        if ctx.invoked_subcommand is None:
            em = discord.Embed(
                title=f"🏢  Auto No Prefix  —  Guild Manager",
                description="Guilds listed here will **automatically grant No Prefix** to their boosters.",
                color=0x000000,
            )
            em.set_author(name="CupidX  •  Partner Guilds", icon_url=BOT_ICON)
            em.add_field(
                name="📋  Subcommands",
                value=(
                    f"{ARROW} `{ctx.prefix}autonp guild add <id>` — Add a partner guild\n"
                    f"{ARROW} `{ctx.prefix}autonp guild remove <id>` — Remove a partner guild\n"
                    f"{ARROW} `{ctx.prefix}autonp guild list` — View all partner guilds"
                ),
                inline=False,
            )
            em.set_footer(text="CupidX  •  Owner Only", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em, mention_author=False)

    @autonp_guild.command(name="add", help="Add a guild to auto No Prefix.")
    async def add_guild(self, ctx, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (guild_id,)) as cursor:
                if await cursor.fetchone():
                    em = discord.Embed(
                        title=f"{WARNING}  Already Added",
                        description=f"Guild `{guild_id}` is already in the auto No Prefix list.",
                        color=0x000000,
                    )
                    return await ctx.reply(embed=em, mention_author=False)
            await db.execute("INSERT INTO autonp (guild_id) VALUES (?)", (guild_id,))
            await db.commit()

        em = discord.Embed(
            title=f"{TICK}  Partner Guild Added",
            description=f"Guild `{guild_id}` will now **auto-grant No Prefix** to its boosters.",
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        em.set_footer(text=f"Added by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, mention_author=False)

    @autonp_guild.command(name="remove", help="Remove a guild from auto No Prefix.")
    async def remove_guild(self, ctx, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (guild_id,)) as cursor:
                if not await cursor.fetchone():
                    em = discord.Embed(
                        title=f"{WARNING}  Not Found",
                        description=f"Guild `{guild_id}` is not in the auto No Prefix list.",
                        color=0x000000,
                    )
                    return await ctx.reply(embed=em, mention_author=False)
            await db.execute("DELETE FROM autonp WHERE guild_id = ?", (guild_id,))
            await db.commit()

        em = discord.Embed(
            title=f"{TICK}  Partner Guild Removed",
            description=f"Guild `{guild_id}` has been removed from auto No Prefix.",
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        em.set_footer(text=f"Removed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, mention_author=False)

    @autonp_guild.command(name="list", help="List all partner guilds with auto No Prefix.")
    @commands.check(is_owner_or_staff)
    async def list_guilds(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id FROM autonp") as cursor:
                guilds = [row[0] for row in await cursor.fetchall()]

        if not guilds:
            em = discord.Embed(
                title=f"{INFO}  Partner Guilds",
                description="No guilds are currently in the auto No Prefix list.",
                color=0x000000,
            )
            return await ctx.reply(embed=em, mention_author=False)

        lines = "\n".join(
            f"`#{i:02}`  {ARROW}  `{gid}`" for i, gid in enumerate(guilds, 1)
        )
        em = discord.Embed(
            title=f"🏢  Auto No Prefix  —  Partner Guilds  [{len(guilds)}]",
            description=lines,
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        em.set_author(name="CupidX  •  Partner Guilds", icon_url=BOT_ICON)
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=em, mention_author=False)

    # ══════════════════════════════════════════════════════════════════════════
    #  Helper Methods
    # ══════════════════════════════════════════════════════════════════════════
    async def is_user_in_np(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM np WHERE id = ?", (user_id,)) as cursor:
                return await cursor.fetchone() is not None

    async def add_np(self, user, duration: timedelta):
        expiry_time = datetime.utcnow() + duration
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO np (id, expiry_time) VALUES (?, ?)",
                (user.id, expiry_time.isoformat()),
            )
            await db.commit()

        ts    = int(expiry_time.timestamp())
        dm_em = discord.Embed(
            title=f"{PREMIUM}  Congratulations!  —  2 Months No Prefix",
            description=(
                f"Hey {user.mention}! 🎉\n\n"
                f"You've been credited **2 months of Global No Prefix** for **boosting** our Partnered Server!\n\n"
                f"{ARROW}  You can now use my commands **without any prefix**.\n"
                f"{TIMER}  Expires: <t:{ts}:F>  *(expires <t:{ts}:R>)*\n\n"
                f"To remove it, contact our [Support Server]({SUPPORT_SERVER})."
            ),
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        dm_em.set_author(name="CupidX  •  No Prefix Reward", icon_url=BOT_ICON)
        dm_em.set_thumbnail(url=user.display_avatar.url)
        dm_em.set_footer(text="CupidX  •  Thank you for boosting!")
        try:
            await user.send(embed=dm_em)
        except (discord.Forbidden, discord.HTTPException):
            pass

        guild = self.client.get_guild(NP_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                role = guild.get_role(NP_ROLE_ID)
                if role:
                    await member.add_roles(role, reason="Auto No Prefix — booster reward")

    async def remove_np(self, user):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT expiry_time FROM np WHERE id = ?", (user.id,)) as cursor:
                row = await cursor.fetchone()
            if row is None or row[0] is None:
                return
            await db.execute("DELETE FROM np WHERE id = ?", (user.id,))
            await db.commit()

        dm_em = discord.Embed(
            title=f"{WARN_ANI}  No Prefix Removed",
            description=(
                f"Hey {user.mention}, your **Global No Prefix** has been **removed**.\n\n"
                f"**Reason:** You stopped boosting our partnered server.\n\n"
                f"If you think this is a mistake, reach out to our [Support Server]({SUPPORT_SERVER})."
            ),
            color=0x000000,
            timestamp=datetime.utcnow(),
        )
        dm_em.set_author(name="CupidX  •  No Prefix", icon_url=BOT_ICON)
        dm_em.set_thumbnail(url=user.display_avatar.url)
        dm_em.set_footer(text="CupidX  •  Contact support if this is a mistake.")
        support_btn = Button(label="Support Server", style=discord.ButtonStyle.link, url=SUPPORT_SERVER, emoji="💬")
        view = View()
        view.add_item(support_btn)
        try:
            await user.send(embed=dm_em, view=view)
        except (discord.Forbidden, discord.HTTPException):
            pass

        guild = self.client.get_guild(NP_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                role = guild.get_role(NP_ROLE_ID)
                if role and role in member.roles:
                    await member.remove_roles(role, reason="Auto NP removed — unboost")

    # ══════════════════════════════════════════════════════════════════════════
    #  Events
    # ══════════════════════════════════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # ── User boosted ───────────────────────────────────────────────────────
        if before.premium_since is None and after.premium_since is not None:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM autonp WHERE guild_id = ?", (after.guild.id,)
                ) as cursor:
                    if not await cursor.fetchone():
                        return
            if not await self.is_user_in_np(after.id):
                await self.add_np(after, timedelta(days=60))
                log_channel = self.client.get_channel(LOG_CHANNEL)
                if log_channel:
                    em = discord.Embed(
                        title=f"{PREMIUM}  Auto No Prefix Granted  —  Booster",
                        description=(
                            f"{UADMIN}  **User:** [{after}](https://discord.com/users/{after.id})  •  `{after.id}`\n"
                            f"🏢  **Server:** {after.guild.name}  (`{after.guild.id}`)\n\n"
                            f"{TIMER}  **Duration:** 60 Days"
                        ),
                        color=0x000000,
                        timestamp=datetime.utcnow(),
                    )
                    em.set_thumbnail(url=after.display_avatar.url)
                    em.set_footer(text="CupidX  •  Auto No Prefix  —  Booster Reward", icon_url=BOT_ICON)
                    message = await log_channel.send(f"<#{LOG_CHANNEL}>", embed=em)
                    await message.publish()

        # ── User unboosted ─────────────────────────────────────────────────────
        elif before.premium_since is not None and after.premium_since is None:
            await self.handle_boost_removal(after)

    async def handle_boost_removal(self, user):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM autonp WHERE guild_id = ?", (user.guild.id,)
            ) as cursor:
                if not await cursor.fetchone():
                    return

        if await self.is_user_in_np(user.id):
            await self.remove_np(user)
            log_channel = self.client.get_channel(LOG_CHANNEL)
            if log_channel:
                em = discord.Embed(
                    title=f"{WARNING}  Auto No Prefix Removed  —  Unboost",
                    description=(
                        f"{UADMIN}  **User:** [{user}](https://discord.com/users/{user.id})  •  `{user.id}`\n"
                        f"🏢  **Server:** {user.guild.name}  (`{user.guild.id}`)"
                    ),
                    color=0x000000,
                    timestamp=datetime.utcnow(),
                )
                em.set_thumbnail(url=user.display_avatar.url)
                em.set_footer(text="CupidX  •  Auto No Prefix  —  Unboost", icon_url=BOT_ICON)
                message = await log_channel.send(f"<#{LOG_CHANNEL}>", embed=em)
                await message.publish()


async def setup(client):
    await client.add_cog(NoPrefix(client))
