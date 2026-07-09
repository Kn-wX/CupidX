from __future__ import annotations
from utils.detectfile import *
import asyncio
import os
import aiosqlite
import discord
from discord.ext import commands
from discord.ext.commands import Context
from typing import List, Tuple

from utils.Tools import blacklist_check, ignore_check

DATABASE_PATH = 'db/customrole.db'

EMOJI_TICK   = "<:CupidXtick1:1474369967271968949>"
EMOJI_CROSS  = "<:CupidXCross:1473996646873436336>"
EMOJI_WARN   = "<:CupidXWarning:1474348304186867784>"
EMOJI_DOT    = "<a:CupidXdot:1473986328126558209>"
EMOJI_LOAD   = "<a:CupidXdot:1473986328126558209>"

from discord.ui import LayoutView, Container, TextDisplay, Separator, Button, ActionRow

NO_PING = discord.AllowedMentions.none()

# ─────────────────────────────────────────────
#  DANGEROUS PERMISSIONS — bot will NEVER give roles with these
# ─────────────────────────────────────────────

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


def has_dangerous_permissions(role: discord.Role) -> list[str]:
    """Returns list of dangerous permission names the role has. Empty = safe."""
    perms = role.permissions
    found = []
    for perm_name in DANGEROUS_PERMS:
        if getattr(perms, perm_name, False):
            found.append(perm_name.replace("_", " ").title())
    return found


# ─────────────────────────────────────────────
#  V2 CARD BUILDERS
# ─────────────────────────────────────────────

def v2_card(title: str, body: str) -> LayoutView:
    """General purpose card — title + separator + body."""
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view


def v2_setup_card(role_label: str, role: discord.Role, invoker: discord.Member) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {EMOJI_TICK}  Setup Complete"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{EMOJI_DOT} **Type** › `{role_label}`\n"
        f"{EMOJI_DOT} **Role** › {role.mention}\n"
        f"{EMOJI_DOT} **By**   › {invoker.mention}\n\n"
        f"Use `{role_label} <@user>` to toggle this role.\n"
        f"Only members with the **Authorized Role** can use toggle commands."
    ))
    view.add_item(c)
    return view


def v2_toggle_card(action: str, role: discord.Role, target: discord.Member, invoker: discord.Member) -> LayoutView:
    emoji = EMOJI_TICK if action == "added" else EMOJI_CROSS
    verb  = "Given" if action == "added" else "Removed"
    prep  = "to" if action == "added" else "from"
    view  = LayoutView()
    c     = Container()
    c.add_item(TextDisplay(f"## {emoji}  Role {verb}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{EMOJI_DOT} **Role**   › {role.mention}\n"
        f"{EMOJI_DOT} **User**   › {target.mention}\n"
        f"{EMOJI_DOT} **By**     › {invoker.mention}"
    ))
    view.add_item(c)
    return view


def v2_loading_card(percent: int, stage: str) -> LayoutView:
    length = 18
    filled = int(length * percent / 100)
    bar    = "█" * filled + "░" * (length - filled)
    view   = LayoutView()
    c      = Container()
    c.add_item(TextDisplay("## ⚙️  Setup Processing"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"`[{bar}]` **{percent}%**\n\n"
        f"**Stage:** {stage}\n"
        f"{'─' * 28}\n"
        f"*Please wait...*"
    ))
    view.add_item(c)
    return view


def v2_auth_setup_card(role: discord.Role, invoker: discord.Member) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {EMOJI_TICK}  Authorized Role Set"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{EMOJI_DOT} **Role**   › {role.mention}\n"
        f"{EMOJI_DOT} **By**     › {invoker.mention}\n\n"
        f"Members with this role can now use all toggle commands\n"
        f"(staff, girl, vip, guest, friend, mod, baby, couple, etc.)\n\n"
        f"{EMOJI_WARN} **Roles with dangerous permissions can never be assigned by the bot.**"
    ))
    view.add_item(c)
    return view


# ─────────────────────────────────────────────
#  COG
# ─────────────────────────────────────────────

class Customrole(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldown = {}
        self.rate_limit_timeout = 5
        self.bot.loop.create_task(self.create_tables())

    # ── low-level role helpers ──────────────────

    async def _is_role_locked(self, guild_id: int, role_id: int) -> bool:
        """Check if a role is locked in lockrole.db."""
        if not os.path.exists("db/lockrole.db"):
            return False
        try:
            async with aiosqlite.connect("db/lockrole.db") as db:
                # Table exist karti hai check karo pehle
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='locked_roles'"
                ) as cur:
                    if not await cur.fetchone():
                        return False
                async with db.execute(
                    "SELECT 1 FROM locked_roles WHERE guild_id=? AND role_id=?",
                    (guild_id, role_id)
                ) as cur:
                    return await cur.fetchone() is not None
        except Exception:
            return False

    async def _is_lockrole_wl(self, guild_id: int, role_id: int, user_id: int) -> bool:
        """Check if user is whitelisted in lockrole for this role."""
        if not os.path.exists("db/lockrole.db"):
            return False
        try:
            async with aiosqlite.connect("db/lockrole.db") as db:
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='lockrole_wl'"
                ) as cur:
                    if not await cur.fetchone():
                        return False
                async with db.execute(
                    "SELECT 1 FROM lockrole_wl WHERE guild_id=? AND role_id=? AND user_id=?",
                    (guild_id, role_id, user_id)
                ) as cur:
                    return await cur.fetchone() is not None
        except Exception:
            return False

    async def add_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.add_roles(discord.Object(id=role_id), reason="Customrole | Role Added")
        else:
            raise discord.Forbidden("Bot lacks Manage Roles permission.")

    async def remove_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.remove_roles(discord.Object(id=role_id), reason="Customrole | Role Removed")
        else:
            raise discord.Forbidden("Bot lacks Manage Roles permission.")

    # ── authorized role check ───────────────────

    async def get_authorized_role(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT auth_role FROM roles WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row and row[0] else None

    async def is_authorized(self, context: Context) -> bool:
        """Returns True if user is guild owner, admin, or has the authorized role."""
        if context.author == context.guild.owner:
            return True
        if context.author.guild_permissions.administrator:
            return True
        auth_role_id = await self.get_authorized_role(context.guild.id)
        if auth_role_id:
            role = context.guild.get_role(auth_role_id)
            if role and role in context.author.roles:
                return True
        return False

    # ── shared toggle handler ───────────────────

    async def handle_role_command(self, context: Context, member: discord.Member, role_type: str):
        # Authorization gate — admin OR authorized role
        if not await self.is_authorized(context):
            await context.reply(
                view=v2_card(
                    "Access Denied",
                    f"{EMOJI_WARN} You need the **Authorized Role** or **Administrator** permission to use this command."
                ),
                allowed_mentions=NO_PING
            )
            return

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                f"SELECT {role_type} FROM roles WHERE guild_id = ?", (context.guild.id,)
            ) as cur:
                data = await cur.fetchone()

        if not data:
            await context.reply(
                view=v2_card("Not Configured", f"{EMOJI_CROSS} No role config found for **{context.guild.name}**."),
                allowed_mentions=NO_PING
            )
            return

        role = context.guild.get_role(data[0]) if data[0] else None
        if not role:
            await context.reply(
                view=v2_card("Not Configured", f"{EMOJI_CROSS} `{role_type}` role is not set up yet."),
                allowed_mentions=NO_PING
            )
            return

        # Dangerous permission block
        dangerous = has_dangerous_permissions(role)
        if dangerous:
            perms_text = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            await context.reply(
                view=v2_card(
                    "Dangerous Role Blocked",
                    f"{EMOJI_CROSS} This role contains **dangerous permissions** and cannot be assigned by the bot.\n\n"
                    f"**Dangerous permissions found:**\n{perms_text}\n\n"
                    f"Please set up a safe role without these permissions."
                ),
                allowed_mentions=NO_PING
            )
            return

        # LockRole check — agar role locked hai toh WL check karo
        if await self._is_role_locked(context.guild.id, role.id):
            is_owner = context.author == context.guild.owner
            is_wl    = await self._is_lockrole_wl(context.guild.id, role.id, context.author.id)
            if not (is_owner or is_wl):
                await context.reply(
                    view=v2_card(
                        "Role Locked",
                        f"{EMOJI_CROSS} {role.mention} is a **locked role**.\n\n"
                        f"You are not whitelisted to assign this role.\n"
                        f"Ask an admin to use `lockrole wl add @you {role.mention}`."
                    ),
                    allowed_mentions=NO_PING
                )
                return

        if role not in member.roles:
            await self.add_role(role_id=role.id, member=member)
            action = "added"
        else:
            await self.remove_role(role_id=role.id, member=member)
            action = "removed"

        await context.reply(
            view=v2_toggle_card(action, role, member, context.author),
            allowed_mentions=NO_PING
        )

    # ── DB helpers ──────────────────────────────

    async def create_tables(self):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS roles (
                    guild_id INTEGER PRIMARY KEY,
                    auth_role INTEGER,
                    staff    INTEGER,
                    girl     INTEGER,
                    vip      INTEGER,
                    guest    INTEGER,
                    frnd     INTEGER,
                    mod      INTEGER,
                    owner    INTEGER,
                    baby     INTEGER,
                    couple   INTEGER
                )
            ''')
            # Migrate: add auth_role column if old table exists without it
            try:
                await db.execute("ALTER TABLE roles ADD COLUMN auth_role INTEGER")
            except Exception:
                pass
            await db.execute('''
                CREATE TABLE IF NOT EXISTS custom_roles (
                    guild_id INTEGER,
                    name     TEXT,
                    role_id  INTEGER,
                    PRIMARY KEY (guild_id, name)
                )
            ''')
            await db.commit()

    async def update_role_data(self, guild_id: int, column: str, value: int | None):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                f"INSERT INTO roles (guild_id, {column}) VALUES (?, ?) "
                f"ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}",
                (guild_id, value)
            )
            await db.commit()

    async def fetch_role_data(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT staff, girl, vip, guest, frnd, mod, owner, baby, couple "
                "FROM roles WHERE guild_id = ?", (guild_id,)
            ) as cur:
                return await cur.fetchone()

    async def fetch_custom_role_data(self, guild_id: int) -> List[Tuple[str, int]]:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT name, role_id FROM custom_roles WHERE guild_id = ?", (guild_id,)
            ) as cur:
                return await cur.fetchall()

    # ─────────────────────────────────────────────
    #  SETUP GROUP
    # ─────────────────────────────────────────────

    @commands.group(name="setup", invoke_without_command=True, help="Setup custom roles for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def set(self, context: Context):
        if context.invoked_subcommand is None:
            body = (
                f"{EMOJI_DOT} `setup auth <role>`   – **Set authorized role** *(required)*\n"
                f"{EMOJI_DOT} `setup staff <role>`  – Staff role\n"
                f"{EMOJI_DOT} `setup girl <role>`   – Girl role\n"
                f"{EMOJI_DOT} `setup vip <role>`    – VIP role\n"
                f"{EMOJI_DOT} `setup guest <role>`  – Guest role\n"
                f"{EMOJI_DOT} `setup friend <role>` – Friend role\n"
                f"{EMOJI_DOT} `setup mod <role>`    – Mod role\n"
                f"{EMOJI_DOT} `setup owner <role>`  – Owner role\n"
                f"{EMOJI_DOT} `setup baby <role>`   – Baby role\n"
                f"{EMOJI_DOT} `setup couple <role>` – Couple role\n"
                f"{EMOJI_DOT} `setup config`        – Show current config\n"
                f"{EMOJI_DOT} `setup create <n> <role>` – Create custom command\n"
                f"{EMOJI_DOT} `setup delete <n>`    – Delete custom command\n"
                f"{EMOJI_DOT} `setup list`          – List custom commands\n"
                f"{EMOJI_DOT} `setup reset`         – Reset all settings\n\n"
                f"{EMOJI_WARN} **Roles with dangerous permissions will be blocked automatically.**"
            )
            await context.reply(
                view=v2_card("<a:emojisetting:1476854070412316713>  Setup Commands", body),
                allowed_mentions=NO_PING
            )
            context.command.reset_cooldown(context)

    # ── shared setup helper ─────────────────────

    async def _role_setup_command(self, context: Context, role: discord.Role, role_name: str):
        if context.author != context.guild.owner and \
                context.author.top_role.position <= context.guild.me.top_role.position:
            await context.reply(
                view=v2_card("Access Denied", f"{EMOJI_WARN} Your top role must be above my top role."),
                allowed_mentions=NO_PING
            )
            return

        # Block dangerous roles from being registered
        dangerous = has_dangerous_permissions(role)
        if dangerous:
            perms_text = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            await context.reply(
                view=v2_card(
                    "Dangerous Role Blocked",
                    f"{EMOJI_CROSS} Cannot register a role with **dangerous permissions**.\n\n"
                    f"**Blocked permissions:**\n{perms_text}\n\n"
                    f"Create a safe role without these permissions first."
                ),
                allowed_mentions=NO_PING
            )
            return

        await self.update_role_data(context.guild.id, role_name, role.id)
        await context.reply(
            view=v2_setup_card(role_name, role, context.author),
            allowed_mentions=NO_PING
        )

    # ── AUTHORIZED ROLE SETUP ───────────────────

    @set.command(name="auth", aliases=["authorize", "authRole"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def auth(self, context: Context, role: discord.Role):
        """Set the authorized role — members with this role can use toggle commands."""
        if context.author != context.guild.owner and \
                context.author.top_role.position <= context.guild.me.top_role.position:
            await context.reply(
                view=v2_card("Access Denied", f"{EMOJI_WARN} Your top role must be above my top role."),
                allowed_mentions=NO_PING
            )
            return

        # Block dangerous roles from being set as auth role
        dangerous = has_dangerous_permissions(role)
        if dangerous:
            perms_text = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            await context.reply(
                view=v2_card(
                    "Dangerous Role Blocked",
                    f"{EMOJI_CROSS} Cannot set a role with **dangerous permissions** as the authorized role.\n\n"
                    f"**Blocked permissions:**\n{perms_text}\n\n"
                    f"Create a safe role without these permissions first."
                ),
                allowed_mentions=NO_PING
            )
            return

        # Loading animation for the setup
        STAGES = [
            (15,  "Validating role..."),
            (35,  "Checking permissions..."),
            (55,  "Binding role to system..."),
            (75,  "Saving to database..."),
            (90,  "Verifying configuration..."),
            (100, "Authorized role is active!"),
        ]

        msg = await context.reply(view=v2_loading_card(0, "Initializing..."), allowed_mentions=NO_PING)
        await asyncio.sleep(0.3)

        for percent, stage in STAGES:
            try:
                await msg.edit(view=v2_loading_card(percent, stage))
            except Exception:
                pass
            await asyncio.sleep(0.45)

        await self.update_role_data(context.guild.id, "auth_role", role.id)
        await msg.edit(view=v2_auth_setup_card(role, context.author))

    # ── fixed setup subcommands ─────────────────

    @set.command(name="staff")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def staff(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "staff")

    @set.command(name="girl")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def girl(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "girl")

    @set.command(name="vip")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def vip(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "vip")

    @set.command(name="guest")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def guest(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "guest")

    @set.command(name="friend")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def friend(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "frnd")

    @set.command(name="mod")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def mod(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "mod")

    @set.command(name="owner")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def owner_role(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "owner")

    @set.command(name="baby")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def baby(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "baby")

    @set.command(name="couple")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def couple(self, context: Context, role: discord.Role):
        await self._role_setup_command(context, role, "couple")

    # ─────────────────────────────────────────────
    #  CONFIG / CREATE / DELETE / LIST / RESET
    # ─────────────────────────────────────────────

    @set.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, context: Context):
        role_data = await self.fetch_role_data(context.guild.id)
        auth_role_id = await self.get_authorized_role(context.guild.id)
        auth_role = context.guild.get_role(auth_role_id) if auth_role_id else None

        lines = [
            f"{EMOJI_DOT} **Auth Role** › {auth_role.mention if auth_role else '`Not set`'}"
        ]

        if role_data:
            names = ["Staff", "Girl", "VIP", "Guest", "Friend", "Mod", "Owner", "Baby", "Couple"]
            for name, role_id in zip(names, role_data):
                role = context.guild.get_role(role_id) if role_id else None
                lines.append(f"{EMOJI_DOT} **{name}** › {role.mention if role else '`Not set`'}")
        else:
            lines.append(f"{EMOJI_DOT} *No roles configured yet.*")

        await context.reply(
            view=v2_card("<a:emojisetting:1476854070412316713>  Current Config", "\n".join(lines)),
            allowed_mentions=NO_PING
        )

    @set.command(name="create")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def create(self, context: Context, name: str, role: discord.Role):
        name = name.lower()

        # Block dangerous roles
        dangerous = has_dangerous_permissions(role)
        if dangerous:
            perms_text = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            await context.reply(
                view=v2_card(
                    "Dangerous Role Blocked",
                    f"{EMOJI_CROSS} Cannot create a command for a role with **dangerous permissions**.\n\n"
                    f"**Blocked permissions:**\n{perms_text}"
                ),
                allowed_mentions=NO_PING
            )
            return

        # Block locked roles from being registered as custom commands
        if await self._is_role_locked(context.guild.id, role.id):
            await context.reply(
                view=v2_card(
                    "Role Locked",
                    f"{EMOJI_CROSS} {role.mention} is a **locked role** and cannot be registered as a custom command.\n\n"
                    f"Unlock it first via `lockrole remove {role.mention}`, or choose a different role."
                ),
                allowed_mentions=NO_PING
            )
            return

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM custom_roles WHERE guild_id = ?", (context.guild.id,)
            ) as cur:
                if (await cur.fetchone())[0] >= 56:
                    await context.reply(
                        view=v2_card("Limit Reached", f"{EMOJI_WARN} Maximum 56 custom role commands allowed."),
                        allowed_mentions=NO_PING
                    )
                    return
            async with db.execute(
                "SELECT name FROM custom_roles WHERE guild_id = ?", (context.guild.id,)
            ) as cur:
                if any(name == row[0] for row in await cur.fetchall()):
                    await context.reply(
                        view=v2_card("Already Exists", f"{EMOJI_CROSS} Command `{name}` already exists."),
                        allowed_mentions=NO_PING
                    )
                    return
            await db.execute(
                "INSERT INTO custom_roles (guild_id, name, role_id) VALUES (?, ?, ?)",
                (context.guild.id, name, role.id)
            )
            await db.commit()

        await context.reply(
            view=v2_card(
                f"{EMOJI_TICK}  Command Created",
                f"{EMOJI_DOT} **Name** › `{name}`\n"
                f"{EMOJI_DOT} **Role** › {role.mention}\n\n"
                f"Use `{name} <@user>` to toggle this role.\n"
                f"Only members with the **Authorized Role** can use it."
            ),
            allowed_mentions=NO_PING
        )

    @set.command(name="delete", aliases=["remove"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def delete(self, context: Context, name: str):
        name = name.lower()
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT name FROM custom_roles WHERE guild_id = ? AND name = ?", (context.guild.id, name)
            ) as cur:
                if not await cur.fetchone():
                    await context.reply(
                        view=v2_card("Not Found", f"{EMOJI_CROSS} No command `{name}` found."),
                        allowed_mentions=NO_PING
                    )
                    return
            await db.execute(
                "DELETE FROM custom_roles WHERE guild_id = ? AND name = ?", (context.guild.id, name)
            )
            await db.commit()
        await context.reply(
            view=v2_card(f"{EMOJI_TICK}  Deleted", f"Custom command `{name}` has been removed."),
            allowed_mentions=NO_PING
        )

    @set.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def list_cmds(self, context: Context):
        custom_roles = await self.fetch_custom_role_data(context.guild.id)
        if not custom_roles:
            await context.reply(
                view=v2_card("Empty", f"{EMOJI_CROSS} No custom role commands created yet."),
                allowed_mentions=NO_PING
            )
            return

        def chunks(data, size):
            for i in range(0, len(data), size):
                yield data[i:i + size]

        pages = list(chunks(custom_roles, 7))
        for i, page in enumerate(pages, 1):
            lines = [
                f"{EMOJI_DOT} `{n}` › {context.guild.get_role(rid).mention}"
                for n, rid in page
                if context.guild.get_role(rid)
            ]
            await context.reply(
                view=v2_card(
                    f"Custom Commands  ({i}/{len(pages)})",
                    "\n".join(lines) + f"\n\n`{len(custom_roles)}` total command(s)"
                ),
                allowed_mentions=NO_PING
            )

    @set.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, context: Context):
        if context.author != context.guild.owner and \
                context.author.top_role.position <= context.guild.me.top_role.position:
            await context.reply(
                view=v2_card("Access Denied", f"{EMOJI_WARN} Your top role must be above my top role."),
                allowed_mentions=NO_PING
            )
            return

        role_data = await self.fetch_role_data(context.guild.id)

        # Loading animation for reset
        STAGES = [
            (20, "Clearing role data..."),
            (45, "Removing custom commands..."),
            (70, "Wiping auth role..."),
            (90, "Finalizing reset..."),
            (100, "Reset complete!"),
        ]
        msg = await context.reply(view=v2_loading_card(0, "Initializing reset..."), allowed_mentions=NO_PING)
        await asyncio.sleep(0.3)
        for percent, stage in STAGES:
            try:
                await msg.edit(view=v2_loading_card(percent, stage))
            except Exception:
                pass
            await asyncio.sleep(0.4)

        fields = ["staff", "girl", "vip", "guest", "frnd", "mod", "owner", "baby", "couple"]
        removed = []
        if role_data:
            for name, role_id in zip(fields, role_data):
                if role_id:
                    role = context.guild.get_role(role_id)
                    if role:
                        removed.append(f"{EMOJI_DOT} **{name.capitalize()}** › {role.mention}")
                    await self.update_role_data(context.guild.id, name, None)

        await self.update_role_data(context.guild.id, "auth_role", None)

        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM custom_roles WHERE guild_id = ?", (context.guild.id,))
            await db.commit()

        body = ("All roles, auth role, and custom commands have been cleared.\n\n"
                + ("\n".join(removed) if removed else f"{EMOJI_DOT} No roles were configured."))
        await msg.edit(view=v2_card(f"{EMOJI_TICK}  Reset Complete", body))

    # ─────────────────────────────────────────────
    #  LISTENER — dangerous role auto-remove from setup
    # ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Agar koi setup mein saved role ke permissions dangerous ho jayein, auto-remove karo."""
        # Sirf tab kaam karo jab permissions badli hoon
        if before.permissions == after.permissions:
            return

        # Naya dangerous check
        dangerous = has_dangerous_permissions(after)
        if not dangerous:
            return  # Safe hai, kuch nahi karna

        guild_id = after.guild.id
        role_id  = after.id
        cleared  = []

        # Standard role columns check karo
        ROLE_COLUMNS = ["staff", "girl", "vip", "guest", "frnd", "mod", "owner", "baby", "couple", "auth_role"]
        async with aiosqlite.connect(DATABASE_PATH) as db:
            for col in ROLE_COLUMNS:
                try:
                    async with db.execute(
                        f"SELECT {col} FROM roles WHERE guild_id=?", (guild_id,)
                    ) as cur:
                        row = await cur.fetchone()
                    if row and row[0] == role_id:
                        await db.execute(
                            f"UPDATE roles SET {col}=NULL WHERE guild_id=?", (guild_id,)
                        )
                        cleared.append(col)
                except Exception:
                    pass

            # Custom roles table check karo
            async with db.execute(
                "SELECT name FROM custom_roles WHERE guild_id=? AND role_id=?",
                (guild_id, role_id)
            ) as cur:
                custom_rows = await cur.fetchall()
            if custom_rows:
                await db.execute(
                    "DELETE FROM custom_roles WHERE guild_id=? AND role_id=?",
                    (guild_id, role_id)
                )
                for (name,) in custom_rows:
                    cleared.append(f"custom:`{name}`")

            await db.commit()

        if not cleared:
            return

        # Log channel ya system channel mein warn bhejo
        guild = after.guild
        target_ch = guild.system_channel
        if target_ch is None:
            for ch in guild.text_channels:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.view_channel:
                    target_ch = ch
                    break

        if target_ch:
            perms_text   = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            cleared_text = "\n".join(f"{EMOJI_DOT} `{c}`" for c in cleared)
            try:
                await target_ch.send(
                    view=v2_card(
                        f"{EMOJI_WARN}  Dangerous Role Auto-Removed",
                        f"{after.mention} was **automatically removed** from the setup config because it now has **dangerous permissions**.\n\n"
                        f"**Dangerous permissions detected:**\n{perms_text}\n\n"
                        f"**Removed from:**\n{cleared_text}\n\n"
                        f"Please set up a safe role again."
                    ),
                    allowed_mentions=NO_PING
                )
            except Exception:
                pass

    # ─────────────────────────────────────────────
    #  LISTENER — custom commands via on_message
    # ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return

        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        prefix_used = next((p for p in prefixes if message.content.startswith(p)), None)
        clean_content = message.content[len(prefix_used):].strip() if prefix_used else message.content.strip()

        if not clean_content:
            return

        cmd_name  = clean_content.split()[0].lower()
        guild_id  = message.guild.id

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM custom_roles WHERE guild_id = ? AND name = ?",
                (guild_id, cmd_name)
            ) as cur:
                result = await cur.fetchone()

        if not result:
            return

        role = message.guild.get_role(result[0])
        if not role:
            return

        # Authorization gate — guild owner, admin, OR authorized role holder
        author = message.author
        is_owner = author == message.guild.owner
        is_admin = author.guild_permissions.administrator
        auth_role_id = await self.get_authorized_role(guild_id)
        has_auth_role = False
        if auth_role_id:
            auth_role_obj = message.guild.get_role(auth_role_id)
            has_auth_role = auth_role_obj in author.roles if auth_role_obj else False

        if not (is_owner or is_admin or has_auth_role):
            await message.reply(
                view=v2_card(
                    "Access Denied",
                    f"{EMOJI_WARN} You need the **Authorized Role** or **Administrator** permission to use this command."
                ),
                allowed_mentions=NO_PING
            )
            return

        # Dangerous permission check
        dangerous = has_dangerous_permissions(role)
        if dangerous:
            perms_text = "\n".join(f"{EMOJI_WARN} `{p}`" for p in dangerous)
            await message.reply(
                view=v2_card(
                    "Dangerous Role Blocked",
                    f"{EMOJI_CROSS} This role has **dangerous permissions** and cannot be assigned.\n\n"
                    f"**Blocked permissions:**\n{perms_text}"
                ),
                allowed_mentions=NO_PING
            )
            return

        # LockRole check — agar role locked hai toh WL check karo
        if await self._is_role_locked(message.guild.id, role.id):
            is_owner = author == message.guild.owner
            is_wl    = await self._is_lockrole_wl(message.guild.id, role.id, author.id)
            if not (is_owner or is_wl):
                await message.reply(
                    view=v2_card(
                        "Role Locked",
                        f"{EMOJI_CROSS} {role.mention} is a **locked role**.\n\n"
                        f"You are not whitelisted to assign this role.\n"
                        f"Ask an admin to use `lockrole wl add @you {role.mention}`."
                    ),
                    allowed_mentions=NO_PING
                )
                return

        if not message.mentions:
            await message.reply(f"Usage: `{cmd_name} <@user>`", allowed_mentions=NO_PING)
            return

        target = message.mentions[0]

        try:
            if role in target.roles:
                await target.remove_roles(role, reason=f"CustomRole: {cmd_name}")
                await message.reply(
                    view=v2_toggle_card("removed", role, target, message.author),
                    allowed_mentions=NO_PING
                )
            else:
                await target.add_roles(role, reason=f"CustomRole: {cmd_name}")
                await message.reply(
                    view=v2_toggle_card("added", role, target, message.author),
                    allowed_mentions=NO_PING
                )
        except discord.Forbidden:
            await message.reply(
                view=v2_card("Permission Error", f"{EMOJI_CROSS} I can't manage this role — check my role position."),
                allowed_mentions=NO_PING
            )

    # ─────────────────────────────────────────────
    #  STANDARD TOGGLE COMMANDS
    # ─────────────────────────────────────────────

    @commands.command(name="staff", aliases=["official"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _staff(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "staff")

    @commands.command(name="girl", aliases=["qt"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _girl(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "girl")

    @commands.command(name="vip")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _vip(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "vip")

    @commands.command(name="guest")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _guest(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "guest")

    @commands.command(name="friend", aliases=["frnd"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _friend(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "frnd")

    @commands.command(name="mod", aliases=["moderator"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _mod(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "mod")

    @commands.command(name="security")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _owner(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "owner")

    @commands.command(name="baby")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _baby(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "baby")

    @commands.command(name="couple")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _couple(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, "couple")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Customrole(bot))
