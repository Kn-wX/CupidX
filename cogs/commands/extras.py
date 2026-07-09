import discord
import aiosqlite
import json
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from utils.Tools import *
from utils.detectfile import (
    EMOJI_TICK, EMOJI_CROSS, EMOJI_WARN, EMOJI_DOT, EMOJI_USER,
    EMOJI_ROLE, EMOJI_CROWN, EMOJI_SHIELD, EMOJI_STAR, EMOJI_GIFT,
    EMOJI_TIMER, EMOJI_TRASH, EMOJI_ADD, EMOJI_ANNOUNCE, EMOJI_CHANNEL,
    EMOJI_PIN, EMOJI_ARROW, EMOJI_INFO, CUPIDX_COLOR,
)
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow

DB_PATH = "db/extras.db"

# ═══════════════════════════════════════════════════════════
#                     V2 CARD HELPERS
# ═══════════════════════════════════════════════════════════

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view


# ═══════════════════════════════════════════════════════════
#               DANGEROUS PERMISSIONS LIST
# ═══════════════════════════════════════════════════════════

DANGEROUS_PERMS = [
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "manage_expressions",
    "mention_everyone",
    "moderate_members",
    "view_audit_log",
    "manage_messages",
    "mute_members",
    "deafen_members",
    "move_members",
    "manage_nicknames",
    "manage_threads",
    "manage_events",
]


def get_dangerous_permissions(member: discord.Member) -> list[str]:
    """Returns list of dangerous perm names a member has via their roles."""
    perms = member.guild_permissions
    return [
        p.replace("_", " ").title()
        for p in DANGEROUS_PERMS
        if getattr(perms, p, False)
    ]


# ═══════════════════════════════════════════════════════════
#                        MAIN COG
# ═══════════════════════════════════════════════════════════

class Extras(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory edit-snipe cache: channel_id → list of dicts (newest first)
        self.edit_snipes: dict[int, list[dict]] = {}
        self.birthday_announce_task.start()

    async def cog_load(self):
        await self._init_db()

    async def cog_unload(self):
        self.birthday_announce_task.cancel()

    # ─── DB SETUP ───────────────────────────────────────────────
    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            # Rejoin Role table — supports multiple roles per guild
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rejoinrole (
                    guild_id    INTEGER NOT NULL,
                    role_id     INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            # Birthday table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    guild_id    INTEGER NOT NULL,
                    user_id     INTEGER NOT NULL,
                    month       INTEGER NOT NULL,
                    day         INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            # Birthday config table (announce channel + optional role)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS birthday_config (
                    guild_id        INTEGER PRIMARY KEY,
                    channel_id      INTEGER,
                    role_id         INTEGER
                )
            """)
            await db.commit()

    # ═══════════════════════════════════════════════════════════
    #                      REJOIN ROLE
    # ═══════════════════════════════════════════════════════════

    # ─── DB Helpers ─────────────────────────────────────────────
    async def _get_rejoin_roles(self, guild_id: int) -> list[int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM rejoinrole WHERE guild_id = ?", (guild_id,)
            ) as cur:
                rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def _add_rejoin_role(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO rejoinrole (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role_id),
            )
            await db.commit()

    async def _remove_rejoin_role(self, guild_id: int, role_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM rejoinrole WHERE guild_id = ? AND role_id = ?",
                (guild_id, role_id),
            )
            await db.commit()

    # ─── Listener: Re-assign roles on rejoin ────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_ids = await self._get_rejoin_roles(member.guild.id)
        if not role_ids:
            return
        roles_to_add = []
        for rid in role_ids:
            role = member.guild.get_role(rid)
            if role and role < member.guild.me.top_role:
                roles_to_add.append(role)
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Rejoin Role — member rejoined")
            except discord.Forbidden:
                pass

    # ─── Commands ───────────────────────────────────────────────
    @commands.group(name="rejoinrole", aliases=["rjr"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def rejoinrole(self, ctx: commands.Context):
        body = (
            f"{EMOJI_DOT} `rejoinrole add <@role>` — Add a role to give on rejoin\n"
            f"{EMOJI_DOT} `rejoinrole remove <@role>` — Remove a role from rejoin list\n"
            f"{EMOJI_DOT} `rejoinrole show` — Show all configured rejoin roles\n"
        )
        await ctx.send(view=v2_card(f"{EMOJI_ROLE} Rejoin Role", body))

    @rejoinrole.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def rejoinrole_add(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Cannot Add Role",
                    "That role is higher than or equal to my top role. Please choose a lower role."
                )
            )
            return
        if role.managed or role.is_default():
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Cannot Add Role",
                    "That role is a managed or default role and cannot be assigned."
                )
            )
            return
        existing = await self._get_rejoin_roles(ctx.guild.id)
        if role.id in existing:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Already Added",
                    f"{role.mention} is already in the rejoin role list."
                )
            )
            return
        await self._add_rejoin_role(ctx.guild.id, role.id)
        await ctx.send(
            view=v2_card(
                f"{EMOJI_TICK} Rejoin Role Added",
                f"{EMOJI_ROLE} Role: {role.mention}\n"
                f"{EMOJI_DOT} Members who rejoin will automatically receive this role."
            )
        )

    @rejoinrole.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def rejoinrole_remove(self, ctx: commands.Context, role: discord.Role):
        existing = await self._get_rejoin_roles(ctx.guild.id)
        if role.id not in existing:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Role Not Found",
                    f"{role.mention} is not in the rejoin role list."
                )
            )
            return
        await self._remove_rejoin_role(ctx.guild.id, role.id)
        await ctx.send(
            view=v2_card(
                f"{EMOJI_TICK} Rejoin Role Removed",
                f"{EMOJI_ROLE} {role.mention} has been removed from the rejoin role list."
            )
        )

    @rejoinrole.command(name="show")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def rejoinrole_show(self, ctx: commands.Context):
        role_ids = await self._get_rejoin_roles(ctx.guild.id)
        if not role_ids:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_INFO} Rejoin Roles",
                    "No rejoin roles are configured for this server."
                )
            )
            return
        lines = []
        for rid in role_ids:
            role = ctx.guild.get_role(rid)
            lines.append(f"{EMOJI_ARROW} {role.mention if role else f'Unknown Role (`{rid}`)'}")
        await ctx.send(
            view=v2_card(
                f"{EMOJI_ROLE} Rejoin Roles — {len(lines)} Configured",
                "\n".join(lines)
            )
        )

    # ═══════════════════════════════════════════════════════════
    #                     DANGER PERMS (dp)
    # ═══════════════════════════════════════════════════════════

    @commands.command(name="dangerperms", aliases=["dp"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def dangerperms(self, ctx: commands.Context):
        """Shows all members who have dangerous permissions."""
        dangerous_members = []

        for member in ctx.guild.members:
            if member.bot:
                continue
            dp = get_dangerous_permissions(member)
            if dp:
                dangerous_members.append((member, dp))

        if not dangerous_members:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_SHIELD} Danger Perms",
                    f"{EMOJI_TICK} No members have dangerous permissions in this server."
                )
            )
            return

        # Build paginated output (max 10 per embed to stay readable)
        lines = []
        for member, dp_list in dangerous_members:
            perm_str = ", ".join(dp_list[:5])
            if len(dp_list) > 5:
                perm_str += f" +{len(dp_list) - 5} more"
            lines.append(
                f"{EMOJI_ARROW} **{member}** (`{member.id}`)\n"
                f"{EMOJI_SHIELD} `{perm_str}`"
            )

        # Split into chunks of 10 members
        chunks = [lines[i:i + 10] for i in range(0, len(lines), 10)]

        if len(chunks) == 1:
            body = "\n\n".join(chunks[0])
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_SHIELD} Danger Perms — {len(dangerous_members)} Members",
                    body
                )
            )
        else:
            # Send first page; note more pages exist
            for idx, chunk in enumerate(chunks):
                body = "\n\n".join(chunk)
                header = (
                    f"{EMOJI_SHIELD} Danger Perms — Page {idx+1}/{len(chunks)} "
                    f"({len(dangerous_members)} Members)"
                )
                await ctx.send(view=v2_card(header, body))

    # ═══════════════════════════════════════════════════════════
    #                      EDIT SNIPE
    # ═══════════════════════════════════════════════════════════

    # ─── Listener: Cache edited messages ────────────────────────
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return  # Only content edits

        channel_id = before.channel.id
        if channel_id not in self.edit_snipes:
            self.edit_snipes[channel_id] = []

        entry = {
            "author_name":   before.author.name,
            "author_avatar": str(before.author.display_avatar.url),
            "author_id":     before.author.id,
            "before":        before.content or "*No text content*",
            "after":         after.content or "*No text content*",
            "edited_at":     int(datetime.now(timezone.utc).timestamp()),
            "jump_url":      after.jump_url,
        }

        # Keep max 30 per channel, newest first
        self.edit_snipes[channel_id].insert(0, entry)
        self.edit_snipes[channel_id] = self.edit_snipes[channel_id][:30]

    # ─── Command ────────────────────────────────────────────────
    @commands.hybrid_command(name="esnipe", aliases=["editsnipe"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def esnipe(self, ctx: commands.Context, index: int = 1):
        """Show the last edited message in this channel. Use index to go further back."""
        snipes = self.edit_snipes.get(ctx.channel.id, [])
        if not snipes:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Edit Snipe",
                    "No edited messages found in this channel."
                )
            )
            return

        index = max(1, min(index, len(snipes)))
        snipe = snipes[index - 1]

        uid        = snipe["author_id"]
        name       = snipe["author_name"]
        avatar_url = snipe["author_avatar"]
        edited_ts  = snipe["edited_at"]

        embed = discord.Embed(color=CUPIDX_COLOR)
        embed.set_author(
            name=f"Edit Snipe {index}/{len(snipes)}",
            icon_url=avatar_url
        )
        embed.description = (
            f"**{EMOJI_USER} Author:** **[{name}](https://discord.com/users/{uid})**\n"
            f"**{EMOJI_DOT} Author ID:** `{uid}`\n"
            f"**{EMOJI_TIMER} Edited:** <t:{edited_ts}:R>\n"
            f"**{EMOJI_ARROW} Jump:** [Click here]({snipe['jump_url']})\n"
        )
        embed.add_field(
            name=f"{EMOJI_CROSS} Before",
            value=snipe["before"][:1024],
            inline=False
        )
        embed.add_field(
            name=f"{EMOJI_TICK} After",
            value=snipe["after"][:1024],
            inline=False
        )
        embed.set_footer(
            text=f"Total Edit Snipes: {len(snipes)} | Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        await ctx.send(embed=embed)

    # ═══════════════════════════════════════════════════════════
    #                     BIRTHDAY SYSTEM
    # ═══════════════════════════════════════════════════════════

    # ─── DB Helpers ─────────────────────────────────────────────
    async def _set_birthday(self, guild_id: int, user_id: int, month: int, day: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO birthdays (guild_id, user_id, month, day)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, user_id, month, day),
            )
            await db.commit()

    async def _get_birthday(self, guild_id: int, user_id: int) -> tuple[int, int] | None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT month, day FROM birthdays WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cur:
                row = await cur.fetchone()
        return (row[0], row[1]) if row else None

    async def _get_all_birthdays(self, guild_id: int) -> list[tuple]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, month, day FROM birthdays WHERE guild_id = ? ORDER BY month, day",
                (guild_id,),
            ) as cur:
                return await cur.fetchall()

    async def _get_todays_birthdays(self, guild_id: int, month: int, day: int) -> list[int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id FROM birthdays WHERE guild_id = ? AND month = ? AND day = ?",
                (guild_id, month, day),
            ) as cur:
                rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def _set_birthday_config(self, guild_id: int, channel_id: int, role_id: int | None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO birthday_config (guild_id, channel_id, role_id)
                VALUES (?, ?, ?)
                """,
                (guild_id, channel_id, role_id),
            )
            await db.commit()

    async def _get_birthday_config(self, guild_id: int) -> tuple | None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT channel_id, role_id FROM birthday_config WHERE guild_id = ?",
                (guild_id,),
            ) as cur:
                return await cur.fetchone()

    # ─── Auto-announce task (runs once per day at midnight UTC) ─
    @tasks.loop(time=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timetz())
    async def birthday_announce_task(self):
        now = datetime.now(timezone.utc)
        month, day = now.month, now.day

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, channel_id, role_id FROM birthday_config") as cur:
                configs = await cur.fetchall()

        for guild_id, channel_id, role_id in configs:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            user_ids = await self._get_todays_birthdays(guild_id, month, day)
            if not user_ids:
                continue

            birthday_role = guild.get_role(role_id) if role_id else None

            for uid in user_ids:
                member = guild.get_member(uid)
                if not member:
                    continue

                # Assign birthday role if configured
                if birthday_role:
                    try:
                        await member.add_roles(birthday_role, reason="Birthday role for today")
                    except discord.Forbidden:
                        pass

                embed = discord.Embed(
                    color=CUPIDX_COLOR,
                    description=(
                        f"{EMOJI_GIFT} **Happy Birthday, {member.mention}!** {EMOJI_GIFT}\n\n"
                        f"{EMOJI_STAR} Wishing you an amazing day filled with joy!\n"
                        f"{EMOJI_DOT} Everyone in the server loves you!"
                    )
                )
                embed.set_author(
                    name=f"🎂 It's {member.display_name}'s Birthday!",
                    icon_url=member.display_avatar.url
                )
                embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    @birthday_announce_task.before_loop
    async def before_birthday_task(self):
        await self.bot.wait_until_ready()

    # ─── Birthday Commands ───────────────────────────────────────
    @commands.group(name="birthday", aliases=["bday"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def birthday(self, ctx: commands.Context):
        body = (
            f"{EMOJI_DOT} `birthday set <DD/MM>` — Set your birthday\n"
            f"{EMOJI_DOT} `birthday list` — List all server birthdays\n"
            f"{EMOJI_DOT} `birthday config <#channel> [role]` — Set announce channel & optional role\n"
            f"{EMOJI_DOT} `birthday remove` — Remove your birthday\n"
        )
        await ctx.send(view=v2_card(f"{EMOJI_GIFT} Birthday System", body))

    @birthday.command(name="set")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def birthday_set(self, ctx: commands.Context, date: str):
        """Set your birthday. Format: DD/MM  e.g. 25/12"""
        try:
            day, month = map(int, date.strip().split("/"))
            # Validate date (use a non-leap year for base validation)
            datetime(year=2001, month=month, day=day)
        except (ValueError, AttributeError):
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} Invalid Date",
                    f"Please use the format `DD/MM`. Example: `25/12` for December 25th."
                )
            )
            return

        await self._set_birthday(ctx.guild.id, ctx.author.id, month, day)
        await ctx.send(
            view=v2_card(
                f"{EMOJI_TICK} Birthday Set",
                f"{EMOJI_GIFT} Your birthday has been set to **{day:02d}/{month:02d}**.\n"
                f"{EMOJI_DOT} The server will celebrate with you on that day!"
            )
        )

    @birthday.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def birthday_remove(self, ctx: commands.Context):
        existing = await self._get_birthday(ctx.guild.id, ctx.author.id)
        if not existing:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_WARN} No Birthday",
                    "You have not set a birthday in this server."
                )
            )
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM birthdays WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, ctx.author.id),
            )
            await db.commit()
        await ctx.send(
            view=v2_card(
                f"{EMOJI_TICK} Birthday Removed",
                "Your birthday has been removed from this server."
            )
        )

    @birthday.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def birthday_list(self, ctx: commands.Context):
        rows = await self._get_all_birthdays(ctx.guild.id)
        if not rows:
            await ctx.send(
                view=v2_card(
                    f"{EMOJI_INFO} Birthday List",
                    "No birthdays have been set in this server yet."
                )
            )
            return

        lines = []
        for uid, month, day in rows:
            member = ctx.guild.get_member(uid)
            name = member.mention if member else f"`{uid}`"
            lines.append(f"{EMOJI_DOT} {name} — **{day:02d}/{month:02d}**")

        # Chunk into pages of 15
        chunks = [lines[i:i + 15] for i in range(0, len(lines), 15)]
        for idx, chunk in enumerate(chunks):
            header = f"{EMOJI_GIFT} Birthday List — Page {idx+1}/{len(chunks)}"
            await ctx.send(view=v2_card(header, "\n".join(chunk)))

    @birthday.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def birthday_config(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        role: discord.Role = None,
    ):
        """Set the announcement channel and optional birthday role."""
        await self._set_birthday_config(ctx.guild.id, channel.id, role.id if role else None)
        role_text = f"\n{EMOJI_ROLE} Birthday Role: {role.mention}" if role else ""
        await ctx.send(
            view=v2_card(
                f"{EMOJI_TICK} Birthday Config Saved",
                f"{EMOJI_ANNOUNCE} Announce Channel: {channel.mention}{role_text}\n"
                f"{EMOJI_DOT} Birthdays will be announced automatically every day."
            )
        )


# ═══════════════════════════════════════════════════════════
#                         SETUP
# ═══════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    await bot.add_cog(Extras(bot))
