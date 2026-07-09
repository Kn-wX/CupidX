from __future__ import annotations
import discord
from utils.detectfile import *
from discord.ext import commands
from discord.ext.commands import Context
import aiosqlite
import asyncio
from typing import List
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button

EMOJI_TICK = "<:CupidXtick1:1474369967271968949>"
EMOJI_CROSS = "<:CupidXCross:1473996646873436336>"
EMOJI_WARN = "<:CupidXWarning:1474348304186867784>"
EMOJI_DOT = "<a:CupidXdot:1473986328126558209>"
EMOJI_SHIELD = "🛡️"

DB_PATH = "db/emergency.db"

def v2_card(title: str, body: str) -> LayoutView:
    """Creates a Components v2 card with title and body text."""
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view

class EmergencyRestoreView(LayoutView):
    def __init__(self, ctx: Context, role_count: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.value = None
        self.role_count = role_count

        title = "🔄 Confirm Restore"
        body = (
            f"{EMOJI_WARN} **Confirm restoration?**\n\n"
            f"{EMOJI_DOT} **{role_count} roles** will have permissions restored\n"
            f"{EMOJI_DOT} This action **cannot be undone**\n"
            f"{EMOJI_DOT} Database will be cleared after restore"
        )
        c = Container()
        c.add_item(TextDisplay(f"## {title}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(body))
        self.add_item(c)

        self.confirm_button = Button(label="Confirm Restore", style=discord.ButtonStyle.green)
        self.cancel_button = Button(label="Cancel", style=discord.ButtonStyle.red)
        self.add_item(self.confirm_button)
        self.add_item(self.cancel_button)

        self.confirm_button.callback = self.confirm_callback
        self.cancel_button.callback = self.cancel_callback

    async def confirm_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Only the server owner can confirm.", ephemeral=True
            )
            return
        self.value = True
        await interaction.response.defer()
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Only the server owner can cancel.", ephemeral=True
            )
            return
        self.value = False
        await interaction.response.defer()
        self.stop()

class Emergency(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = DB_PATH
        self.bot.loop.create_task(self.initialize_database())

    async def initialize_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS authorised_users (
                    guild_id INTEGER,
                    user_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS emergency_roles (
                    guild_id INTEGER,
                    role_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS restore_roles (
                    guild_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    disabled_perms TEXT NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS role_positions (
                    guild_id INTEGER,
                    role_id INTEGER,
                    previous_position INTEGER
                )
            """)
            await db.commit()

    async def is_guild_owner(self, ctx: Context) -> bool:
        return ctx.guild is not None and ctx.author.id == ctx.guild.owner_id

    async def is_guild_owner_or_authorised(self, ctx: Context) -> bool:
        if await self.is_guild_owner(ctx):
            return True
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, ctx.author.id)
            ) as cursor:
                return await cursor.fetchone() is not None

    # ========== MAIN EMERGENCY GROUP ==========
    @commands.group(
        name="emergency",
        aliases=["emg"],
        invoke_without_command=True
    )
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def emergency(self, ctx: Context):
        if ctx.invoked_subcommand is not None:
            return

        body = (
            f"{EMOJI_SHIELD} **Emergency Protection System**\n\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency enable` – Auto-add dangerous roles\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency disable` – Clear emergency list\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency authorise` – Manage authorized users\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency role` – Manual role management\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergencysituation` (emgs) – **EXECUTE EMERGENCY**\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergencyrestore` (emgrestore) – Restore permissions\n\n"
            f"*Owner/Authorized users only. Protects against malicious activity.*"
        )
        await ctx.reply(view=v2_card("🛡️ Emergency Commands", body))

    @emergency.command(name="enable")
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def enable(self, ctx: Context):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        dangerous_perms = [
            "administrator",
            "ban_members",
            "kick_members",
            "manage_channels",
            "manage_roles",
            "manage_guild"
        ]
        roles_added = []

        async with aiosqlite.connect(self.db_path) as db:
            for role in ctx.guild.roles:
                if role.managed or role.position >= ctx.guild.me.top_role.position:
                    continue

                if any(getattr(role.permissions, perm, False) for perm in dangerous_perms):
                    async with db.execute(
                        "SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?",
                        (ctx.guild.id, role.id)
                    ) as cursor:
                        if not await cursor.fetchone():
                            await db.execute(
                                "INSERT INTO emergency_roles (guild_id, role_id) VALUES (?, ?)",
                                (ctx.guild.id, role.id)
                            )
                            roles_added.append(role)
            await db.commit()

        if roles_added:
            role_list = "\n".join(f"{EMOJI_DOT} {role.mention}" for role in roles_added[:10])
            body = f"{EMOJI_TICK} **{len(roles_added)} roles** added to emergency list:\n{role_list}"
        else:
            body = f"{EMOJI_WARN} No new dangerous roles found."

        await ctx.reply(view=v2_card("🛡️ Emergency Mode Enabled", body))

    @emergency.command(name="disable")
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def disable(self, ctx: Context):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM emergency_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        await ctx.reply(view=v2_card("🛡️ Emergency Mode Disabled", f"{EMOJI_TICK} All emergency roles cleared."))

    # ========== AUTHORISE GROUP ==========
    @emergency.group(
        name="authorise",
        aliases=["ath"],
        invoke_without_command=True
    )
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def authorise(self, ctx: Context):
        if ctx.invoked_subcommand is not None:
            return

        body = (
            f"{EMOJI_DOT} `{ctx.prefix}emergency authorise add <user>` – Add authorized user\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency authorise remove <user>` – Remove user\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency authorise list` – View authorized users"
        )
        await ctx.reply(view=v2_card("👥 Authorise Commands", body))

    @authorise.command(name="add")
    @commands.guild_only()
    async def authorise_add(self, ctx: Context, member: discord.Member):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM authorised_users WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                if count >= 5:
                    await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Limit Reached", f"{EMOJI_WARN} Max 5 authorized users allowed."))
                    return

            async with db.execute(
                "SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id)
            ) as cursor:
                if await cursor.fetchone():
                    await ctx.reply(
                        view=v2_card("<:CupidXCross:1473996646873436336> Already Authorized",
                                     f"{EMOJI_CROSS} {member.mention} already authorized.")
                    )
                    return

            await db.execute(
                "INSERT INTO authorised_users (guild_id, user_id) VALUES (?, ?)",
                (ctx.guild.id, member.id)
            )
            await db.commit()

        await ctx.reply(view=v2_card("<:CupidXtick1:1474369967271968949> User Authorized", f"{EMOJI_TICK} {member.mention} can now use emergency commands."))

    @authorise.command(name="remove")
    @commands.guild_only()
    async def authorise_remove(self, ctx: Context, member: discord.Member):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id)
            ) as cursor:
                if not await cursor.fetchone():
                    await ctx.reply(
                        view=v2_card("<:CupidXCross:1473996646873436336> Not Authorized",
                                     f"{EMOJI_CROSS} {member.mention} not in authorized list.")
                    )
                    return

            await db.execute(
                "DELETE FROM authorised_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id)
            )
            await db.commit()

        await ctx.reply(view=v2_card("<:CupidXtick1:1474369967271968949> User Removed", f"{EMOJI_TICK} {member.mention} removed from authorized list."))

    @authorise.command(name="list", aliases=["view"])
    @commands.guild_only()
    async def list_authorized(self, ctx: Context):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id FROM authorised_users WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                users = await cursor.fetchall()

        if not users:
            await ctx.reply(view=v2_card("👥 Authorized Users", f"{EMOJI_WARN} No authorized users."))
            return

        user_list = "\n".join(
            f"{i+1}. "
            f"{ctx.guild.get_member(uid[0]).display_name if ctx.guild.get_member(uid[0]) else f'Unknown ({uid[0]})'} "
            f"(`{uid[0]}`)"
            for i, uid in enumerate(users)
        )
        await ctx.reply(view=v2_card("👥 Authorized Users", user_list))

    # ========== ROLE GROUP ==========
    @emergency.group(
        name="role",
        invoke_without_command=True
    )
    @commands.guild_only()
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def role_group(self, ctx: Context):
        if ctx.invoked_subcommand is not None:
            return

        body = (
            f"{EMOJI_DOT} `{ctx.prefix}emergency role add <role>` – Add to emergency list\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency role remove <role>` – Remove from list\n"
            f"{EMOJI_DOT} `{ctx.prefix}emergency role list` – View emergency roles"
        )
        await ctx.reply(view=v2_card("📋 Role Commands", body))

    @role_group.command(name="add")
    @commands.guild_only()
    async def role_add(self, ctx: Context, role: discord.Role):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM emergency_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                if count >= 25:
                    await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Limit Reached", f"{EMOJI_WARN} Max 25 emergency roles."))
                    return

            async with db.execute(
                "SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?",
                (ctx.guild.id, role.id)
            ) as cursor:
                if await cursor.fetchone():
                    await ctx.reply(
                        view=v2_card("<:CupidXCross:1473996646873436336> Already Added",
                                     f"{EMOJI_CROSS} {role.mention} already in emergency list.")
                    )
                    return

            await db.execute(
                "INSERT INTO emergency_roles (guild_id, role_id) VALUES (?, ?)",
                (ctx.guild.id, role.id)
            )
            await db.commit()

        await ctx.reply(view=v2_card("<:CupidXtick1:1474369967271968949> Role Added", f"{EMOJI_TICK} {role.mention} added to emergency list."))

    @role_group.command(name="remove")
    @commands.guild_only()
    async def role_remove(self, ctx: Context, role: discord.Role):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?",
                (ctx.guild.id, role.id)
            ) as cursor:
                if not await cursor.fetchone():
                    await ctx.reply(
                        view=v2_card("<:CupidXCross:1473996646873436336> Not Found",
                                     f"{EMOJI_CROSS} {role.mention} not in emergency list.")
                    )
                    return

            await db.execute(
                "DELETE FROM emergency_roles WHERE guild_id = ? AND role_id = ?",
                (ctx.guild.id, role.id)
            )
            await db.commit()

        await ctx.reply(view=v2_card("<:CupidXtick1:1474369967271968949> Role Removed", f"{EMOJI_TICK} {role.mention} removed from emergency list."))

    @role_group.command(name="list", aliases=["view"])
    @commands.guild_only()
    async def list_roles(self, ctx: Context):
        if not await self.is_guild_owner_or_authorised(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Not authorized."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role_id FROM emergency_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                roles = await cursor.fetchall()

        if not roles:
            await ctx.reply(view=v2_card("📋 Emergency Roles", f"{EMOJI_WARN} No emergency roles configured."))
            return

        role_list = "\n".join(
            f"{i+1}. "
            f"{ctx.guild.get_role(rid[0]).mention if ctx.guild.get_role(rid[0]) else f'Deleted ({rid[0]})'} "
            f"(`{rid[0]}`)"
            for i, rid in enumerate(roles)
        )
        await ctx.reply(view=v2_card("📋 Emergency Roles", role_list))

    # ========== EXECUTE EMERGENCY ==========
    @commands.command(name="emergencysituation", aliases=["emgs", "emergency-situation"])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 40, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def emergencysituation(self, ctx: Context):
        if not await self.is_guild_owner_or_authorised(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Not authorized for emergency execution."))
            return

        processing = await ctx.reply(view=v2_card("⏳ Processing", "Executing emergency situation... Please wait."))

        antinuke_enabled = False
        try:
            async with aiosqlite.connect('db/anti.db') as anti:
                async with anti.execute(
                    "SELECT status FROM antinuke WHERE guild_id = ?",
                    (ctx.guild.id,)
                ) as cursor:
                    status = await cursor.fetchone()
                    if status:
                        antinuke_enabled = True
                        await anti.execute(
                            'DELETE FROM antinuke WHERE guild_id = ?',
                            (ctx.guild.id,)
                        )
                        await anti.commit()
        except:
            pass

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM restore_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

            async with db.execute(
                "SELECT role_id FROM emergency_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                emergency_roles = await cursor.fetchall()

        if not emergency_roles:
            await processing.delete()
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> No Roles", f"{EMOJI_CROSS} No emergency roles configured."))
            return

        bot_top_role = ctx.guild.me.top_role
        dangerous_perms = [
            "administrator",
            "ban_members",
            "kick_members",
            "manage_channels",
            "manage_roles",
            "manage_guild"
        ]

        modified_roles = []
        unchanged_roles = []

        async with aiosqlite.connect(self.db_path) as db:
            for role_data in emergency_roles:
                role = ctx.guild.get_role(role_data[0])
                if not role or role.position >= bot_top_role.position or role.managed:
                    if role:
                        unchanged_roles.append(role)
                    continue

                role_perms = role.permissions
                disabled_perms = []
                perms_changed = False

                for perm in dangerous_perms:
                    if getattr(role_perms, perm, False):
                        setattr(role_perms, perm, False)
                        disabled_perms.append(perm)
                        perms_changed = True

                if perms_changed:
                    try:
                        await role.edit(
                            permissions=role_perms,
                            reason="Emergency: Disabled dangerous perms"
                        )
                        modified_roles.append(role)
                        await db.execute(
                            "INSERT INTO restore_roles (guild_id, role_id, disabled_perms) VALUES (?, ?, ?)",
                            (ctx.guild.id, role.id, ','.join(disabled_perms))
                        )
                    except discord.Forbidden:
                        unchanged_roles.append(role)

            await db.commit()

        most_populated = max(
            [
                r for r in ctx.guild.roles
                if not r.managed and r.position < bot_top_role.position and r != ctx.guild.default_role
            ],
            key=lambda r: len(r.members),
            default=None
        )

        success_list = "\n".join(f"{EMOJI_TICK} {r.mention}" for r in modified_roles[:5]) if modified_roles else "None"
        error_list = "\n".join(f"{EMOJI_WARN} {r.mention}" for r in unchanged_roles[:5]) if unchanged_roles else "None"

        body = f"**Modified ({len(modified_roles)}):**\n{success_list}\n\n**Errors ({len(unchanged_roles)}):**\n{error_list}"

        if most_populated:
            try:
                await most_populated.edit(
                    position=bot_top_role.position - 1,
                    reason="Emergency: Safety positioning"
                )
                body += f"\n\n{EMOJI_SHIELD} **{most_populated.mention}** moved to safety position"
            except discord.Forbidden:
                body += f"\n\n{EMOJI_WARN} Could not move {most_populated.mention}"

        await processing.delete()
        await ctx.reply(view=v2_card("🛡️ Emergency Executed", body))

        if antinuke_enabled:
            try:
                async with aiosqlite.connect('db/anti.db') as anti:
                    await anti.execute(
                        "INSERT INTO antinuke (guild_id, status) VALUES (?, 1)",
                        (ctx.guild.id,)
                    )
                    await anti.commit()
            except:
                pass

    # ========== RESTORE ==========
    @commands.command(
        name="emergencyrestore",
        aliases=["emgrestore", "emgsrestore", "emgbackup"]
    )
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def emergencyrestore(self, ctx: Context):
        if not await self.is_guild_owner(ctx):
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Access Denied", f"{EMOJI_CROSS} Server owner only."))
            return

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role_id, disabled_perms FROM restore_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                restore_roles = await cursor.fetchall()

        if not restore_roles:
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Nothing to Restore", f"{EMOJI_CROSS} No disabled permissions found."))
            return

        view = EmergencyRestoreView(ctx, len(restore_roles))
        await ctx.reply(view=view)
        await view.wait()

        if view.value is None:
            await ctx.reply(view=v2_card("⏰ Timed Out", f"{EMOJI_WARN} Restore cancelled."))
            return
        if view.value is False:
            await ctx.reply(view=v2_card("<:CupidXCross:1473996646873436336> Cancelled", f"{EMOJI_CROSS} Restore cancelled."))
            return

        modified_roles = []
        unchanged_roles = []

        async with aiosqlite.connect(self.db_path) as db:
            for role_id, disabled_perms in restore_roles:
                role = ctx.guild.get_role(role_id)
                if not role:
                    continue

                role_perms = role.permissions
                perms_restored = False

                for perm in disabled_perms.split(','):
                    if hasattr(role_perms, perm):
                        setattr(role_perms, perm, True)
                        perms_restored = True

                if perms_restored:
                    try:
                        await role.edit(permissions=role_perms, reason="Emergency Restore")
                        modified_roles.append(role)
                    except discord.Forbidden:
                        unchanged_roles.append(role)

            await db.execute("DELETE FROM restore_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        success_list = "\n".join(f"{EMOJI_TICK} {r.mention}" for r in modified_roles[:5]) if modified_roles else "None"
        error_list = "\n".join(f"{EMOJI_WARN} {r.mention}" for r in unchanged_roles[:5]) if unchanged_roles else "None"

        body = (
            f"**Restored ({len(modified_roles)}):**\n{success_list}\n\n"
            f"**Errors ({len(unchanged_roles)}):**\n{error_list}\n\n"
            f"{EMOJI_TICK} Database cleared."
        )
        await ctx.reply(view=v2_card("<:CupidXtick1:1474369967271968949> Restore Complete", body))

async def setup(bot: commands.Bot):
    await bot.add_cog(Emergency(bot))
