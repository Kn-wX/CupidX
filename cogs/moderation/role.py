import discord
from discord.ext import commands
import asyncio
import re
import aiosqlite
from typing import *
from utils.Tools import *
from discord.ui import Button, View, LayoutView, Container, TextDisplay, Separator, ActionRow

time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for key, value in matches:
        try:
            time += time_dict[value] * float(key)
        except KeyError:
            raise commands.BadArgument(f"{value} is an invalid time key! h|m|s|d are valid arguments")
        except ValueError:
            raise commands.BadArgument(f"{key} is not a number!")
    return round(time)


# ─────────────────────────────────────────────
#  DANGEROUS PERMISSIONS — never assign roles with these
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


def get_dangerous_permissions(role: discord.Role) -> list[str]:
    """Returns list of dangerous perm names the role has. Empty = safe."""
    perms = role.permissions
    return [
        p.replace("_", " ").title()
        for p in DANGEROUS_PERMS
        if getattr(perms, p, False)
    ]


# ─────────────────────────────────────────────
#  V2 CARD HELPERS
# ─────────────────────────────────────────────

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view


def v2_loading_card(percent: int, stage: str, label: str = "Processing") -> LayoutView:
    length = 18
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## ⚙️  {label}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"`[{bar}]` **{percent}%**\n\n"
        f"**Stage:** {stage}\n"
        f"{'─' * 28}\n"
        f"*Please wait, do not run other commands...*"
    ))
    view.add_item(c)
    return view


def v2_confirm_card(title: str, body: str, confirm_btn: Button, cancel_btn: Button) -> LayoutView:
    """V2 confirm card with buttons inside container."""
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    c.add_item(Separator())
    c.add_item(ActionRow(confirm_btn, cancel_btn))
    view.add_item(c)
    return view


def v2_dangerous_block(dangerous: list[str]) -> LayoutView:
    perms_text = "\n".join(f"⚠️ `{p}`" for p in dangerous)
    return v2_card(
        "⛔  Dangerous Role Blocked",
        f"This role contains **dangerous permissions** and cannot be assigned to members.\n\n"
        f"**Blocked permissions:**\n{perms_text}\n\n"
        f"Please use a safe role without these permissions."
    )


# ─────────────────────────────────────────────
#  BULK ROLE HELPER — with live loading bar
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  LOCKROLE CHECK HELPER
# ─────────────────────────────────────────────

LOCKROLE_DB = "db/lockrole.db"

async def is_role_locked(guild_id: int, role_id: int) -> bool:
    """Check karo ki role locked hai ya nahi lockrole DB se."""
    try:
        async with aiosqlite.connect(LOCKROLE_DB) as db:
            async with db.execute(
                "SELECT 1 FROM locked_roles WHERE guild_id=? AND role_id=?",
                (guild_id, role_id)
            ) as cur:
                return await cur.fetchone() is not None
    except Exception:
        return False

async def is_user_wl(guild_id: int, role_id: int, user_id: int) -> bool:
    """Check karo ki user lockrole whitelist mein hai ya nahi."""
    try:
        async with aiosqlite.connect(LOCKROLE_DB) as db:
            async with db.execute(
                "SELECT 1 FROM lockrole_wl WHERE guild_id=? AND role_id=? AND user_id=?",
                (guild_id, role_id, user_id)
            ) as cur:
                return await cur.fetchone() is not None
    except Exception:
        return False


BULK_DELAY = 0.5
BULK_MAX_BACKOFF = 30.0


async def bulk_assign(
    interaction: discord.Interaction,
    members: list[discord.Member],
    role: discord.Role,
    action: str,
    reason: str,
    label: str,
):
    """
    Bulk add/remove a role with rate-limit-safe pacing.
    - 0.5s delay between each API call to stay well under Discord limits.
    - On 429 HTTPException, sleeps for retry_after + 1s then retries once.
    - Loading bar updated every ~5% progress.
    Returns count of successful operations.
    """
    total = len(members)
    count = 0
    last_reported = -1

    for i, member in enumerate(members):
        retried = False
        while True:
            try:
                if action == "add":
                    await member.add_roles(role, reason=reason)
                else:
                    await member.remove_roles(role, reason=reason)
                count += 1
                break
            except discord.HTTPException as e:
                if e.status == 429 and not retried:
                    retry_after = float(getattr(e, "retry_after", None) or 5)
                    retry_after = min(retry_after + 1.0, BULK_MAX_BACKOFF)
                    retried = True
                    await asyncio.sleep(retry_after)
                    continue
                break
            except Exception:
                break

        await asyncio.sleep(BULK_DELAY)

        percent = int((i + 1) / total * 100)
        if percent - last_reported >= 5:
            last_reported = percent
            stage = f"{'Assigning' if action == 'add' else 'Removing'} {role.name} — {i+1}/{total} members"
            try:
                await interaction.edit_original_response(
                    view=v2_loading_card(percent, stage, label)
                )
            except Exception:
                pass

    return count


# ─────────────────────────────────────────────
#  COG
# ─────────────────────────────────────────────

class Role(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0x000000

    # ── role (base) ──────────────────────────────

    @commands.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @top_check()
    async def role(self, ctx, member: discord.Member = commands.parameter(description="The member to adjust roles for"),
                   *, role: discord.Role = commands.parameter(description="The role to add/remove")):
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send(view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

        if role >= ctx.guild.me.top_role:
            return await ctx.send(view=v2_card("Error", "I can't manage roles higher than or equal to my top role!"))

        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            return await ctx.send(view=v2_card("Access Denied", "You can't manage roles for a user with a higher or equal role than yours!"))

        # Dangerous permission check
        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        # LockRole check — agar role locked hai toh block karo
        if await is_role_locked(ctx.guild.id, role.id):
            if not await is_user_wl(ctx.guild.id, role.id, ctx.author.id):
                return await ctx.send(view=v2_card(
                    "❌  Locked Role",
                    f"{role.mention} is a **locked role** and cannot be assigned via commands.\n\n"
                    f"Only whitelisted users can assign this role.\n"
                    f"Use `lockrole wl add @user {role.mention}` to whitelist someone."
                ))

        try:
            if role not in member.roles:
                await member.add_roles(role, reason=f"Role added by {ctx.author} (ID: {ctx.author.id})")
                await ctx.send(view=v2_card("✅  Role Added", f"Successfully **added** {role.mention} to {member.mention}."))
            else:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author} (ID: {ctx.author.id})")
                await ctx.send(view=v2_card("✅  Role Removed", f"Successfully **removed** {role.mention} from {member.mention}."))
        except discord.Forbidden:
            await ctx.send(view=v2_card("Error ⚠️", "I don't have permission to manage roles for this user!"))
        except Exception as e:
            await ctx.send(view=v2_card("Error ⚠️", f"An unexpected error occurred: {str(e)}"))

    # ── role temp ────────────────────────────────

    @role.command(help="Give role to member for particular time")
    @commands.bot_has_permissions(manage_roles=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    async def temp(self, ctx,
                   role: discord.Role = commands.parameter(description="The role to grant temporarily"),
                   time: str = commands.parameter(description="Duration (e.g. 1h, 30m)"),
                   *, user: discord.Member = commands.parameter(description="The member to grant the role to")):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            return await ctx.send(view=v2_card("Error", "You can't manage a role that is higher or equal to your top role!"))

        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(view=v2_card("Error", f"{role} is higher than my top role, move my role above {role}."))

        # Dangerous permission check
        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        # LockRole check
        if await is_role_locked(ctx.guild.id, role.id):
            if not await is_user_wl(ctx.guild.id, role.id, ctx.author.id):
                return await ctx.send(view=v2_card(
                    "\u274c  Locked Role",
                    f"{role.mention} is a **locked role** and cannot be assigned via commands.\n\n"
                    f"Only whitelisted users can assign this role."
                ))

        seconds = convert(time)
        await user.add_roles(role, reason=None)
        await ctx.send(view=v2_card("✅  Role Added", f"Successfully added {role.mention} to {user.mention} for **{time}**."))
        await asyncio.sleep(seconds)
        await user.remove_roles(role)

    # ── role delete ──────────────────────────────

    @role.command(help="Delete a role in the guild")
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def delete(self, ctx, *, role: discord.Role = commands.parameter(description="The role to delete")):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            return await ctx.send(view=v2_card("Error", "You cannot delete a role that is higher or equal to your top role!"))

        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(view=v2_card("Error", f"I cannot delete {role} because it is higher than my top role."))

        await role.delete()
        await ctx.send(view=v2_card("✅  Role Deleted", f"Successfully deleted **{role.name}**."))

    # ── role create ──────────────────────────────

    @role.command(help="Create a role in the guild")
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def create(self, ctx, *, name: str = commands.parameter(description="Name of the new role")):
        await ctx.guild.create_role(name=name, color=discord.Color.default())
        await ctx.send(view=v2_card("✅  Role Created", f"Successfully created role **{name}**."))

    # ── role rename ──────────────────────────────

    @role.command(help="Renames a role in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rename(self, ctx,
                     role: discord.Role = commands.parameter(description="The role to rename"),
                     *, newname: str = commands.parameter(description="The new name for the role")):
        if role.position >= ctx.author.top_role.position:
            return await ctx.send(view=v2_card("Error", f"You can't manage {role.mention} — it's higher or equal to your top role."))

        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(view=v2_card("Error", f"I can't manage {role.mention} — it's higher than my top role."))

        old_name = role.name
        await role.edit(name=newname)
        await ctx.send(view=v2_card("✅  Role Renamed", f"Role **{old_name}** has been renamed to **{newname}**."))

    # ─────────────────────────────────────────────
    #  ROLE ALL / HUMANS / BOTS / UNVERIFIED
    #  All with: dangerous perm check + V2 confirm card + loading bar
    # ─────────────────────────────────────────────

    @role.command(name="humans", help="Gives role to all humans in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_humans(self, ctx, *, role: discord.Role = commands.parameter(description="The role to give to all humans")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        targets = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"All humans already have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        msg = await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to assign {role.mention} to **{len(targets)}** humans?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Assigning Role to Humans"))
            count = await bulk_assign(interaction, targets, role, "add",
                                      f"Role Humans by {ctx.author}", "Assigning Role to Humans")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully assigned {role.mention} to **{count}** human(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. No humans will be assigned {role.mention}."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @role.command(name="bots", help="Gives role to all the bots in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_bots(self, ctx, *, role: discord.Role = commands.parameter(description="The role to give to all bots")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        targets = [m for m in ctx.guild.members if m.bot and role not in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"All bots already have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to assign {role.mention} to **{len(targets)}** bots?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Assigning Role to Bots"))
            count = await bulk_assign(interaction, targets, role, "add",
                                      f"Role Bots by {ctx.author}", "Assigning Role to Bots")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully assigned {role.mention} to **{count}** bot(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. No bots will be assigned {role.mention}."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @role.command(name="unverified", help="Gives role to all the unverified members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_unverified(self, ctx, *, role: discord.Role = commands.parameter(description="The role to give to unverified members")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        targets = [m for m in ctx.guild.members if m.avatar is None and role not in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"No unverified members found without {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to assign {role.mention} to **{len(targets)}** unverified members?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Assigning Role to Unverified"))
            count = await bulk_assign(interaction, targets, role, "add",
                                      f"Role Unverified by {ctx.author}", "Assigning Role to Unverified")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully assigned {role.mention} to **{count}** unverified member(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. No unverified members will be assigned {role.mention}."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @role.command(name="all", help="Gives role to all the members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_all(self, ctx, *, role: discord.Role = commands.parameter(description="The role to give to all members")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        dangerous = get_dangerous_permissions(role)
        if dangerous:
            return await ctx.send(view=v2_dangerous_block(dangerous))

        targets = [m for m in ctx.guild.members if role not in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"{role.mention} is already given to all members."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to assign {role.mention} to **{len(targets)}** members?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Assigning Role to All Members"))
            count = await bulk_assign(interaction, targets, role, "add",
                                      f"Role All by {ctx.author}", "Assigning Role to All Members")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully assigned {role.mention} to **{count}** member(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. No members will be assigned {role.mention}."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ─────────────────────────────────────────────
    #  REMOVEROLE GROUP
    # ─────────────────────────────────────────────

    @commands.group(name="removerole", invoke_without_command=True,
                    aliases=['rrole'], help="Remove a role from all members.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rrole(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    # ──────────────────────────────────────────────

    @rrole.command(name="humans", help="Removes a role from all the humans in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_humans(self, ctx, *, role: discord.Role = commands.parameter(description="The role to remove from all humans")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        targets = [m for m in ctx.guild.members if not m.bot and role in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"No humans currently have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to remove {role.mention} from **{len(targets)}** humans?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Removing Role from Humans"))
            count = await bulk_assign(interaction, targets, role, "remove",
                                      f"RRole Humans by {ctx.author}", "Removing Role from Humans")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully removed {role.mention} from **{count}** human(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. {role.mention} will not be removed from any humans."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @rrole.command(name="bots", help="Removes a role from all the bots in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_bots(self, ctx, *, role: discord.Role = commands.parameter(description="The role to remove from all bots")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        targets = [m for m in ctx.guild.members if m.bot and role in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"No bots currently have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to remove {role.mention} from **{len(targets)}** bots?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Removing Role from Bots"))
            count = await bulk_assign(interaction, targets, role, "remove",
                                      f"RRole Bots by {ctx.author}", "Removing Role from Bots")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully removed {role.mention} from **{count}** bot(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. {role.mention} will not be removed from any bots."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @rrole.command(name="all", help="Removes a role from all members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_all(self, ctx, *, role: discord.Role = commands.parameter(description="The role to remove from all members")):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        targets = [m for m in ctx.guild.members if role in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"No members currently have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to remove {role.mention} from **{len(targets)}** members?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Removing Role from All Members"))
            count = await bulk_assign(interaction, targets, role, "remove",
                                      f"RRole All by {ctx.author}", "Removing Role from All Members")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully removed {role.mention} from **{count}** member(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. {role.mention} will not be removed from anyone."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ──────────────────────────────────────────────

    @rrole.command(name="unverified", help="Removes a role from all the unverified members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_unverified(self, ctx, *, role: discord.Role):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(view=v2_card("⛔  Access Denied", "Your role should be above my top role."))

        targets = [m for m in ctx.guild.members if m.avatar is None and role in m.roles]
        if not targets:
            return await ctx.reply(view=v2_card("Already Done", f"No unverified members currently have {role.mention}."))

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "Confirm Action",
                f"Are you sure you want to remove {role.mention} from **{len(targets)}** unverified members?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(
                    view=v2_card("Missing Permission", "⚠️ I don't have permission to manage roles!"))

            await interaction.response.edit_message(view=v2_loading_card(1, "Starting...", "Removing Role from Unverified"))
            count = await bulk_assign(interaction, targets, role, "remove",
                                      f"RRole Unverified by {ctx.author}", "Removing Role from Unverified")
            await interaction.channel.send(view=v2_card("✅  Done", f"Successfully removed {role.mention} from **{count}** unverified member(s)."))

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This action is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", f"Action cancelled. {role.mention} will not be removed from any unverified members."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb


async def setup(bot):
    await bot.add_cog(Role(bot))
