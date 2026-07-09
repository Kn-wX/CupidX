import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *
from discord.ui import Button, LayoutView, Container, TextDisplay, Separator, ActionRow

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


def v2_confirm_card(title: str, body: str, confirm_btn: Button, cancel_btn: Button) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    c.add_item(Separator())
    c.add_item(ActionRow(confirm_btn, cancel_btn))
    view.add_item(c)
    return view


# ─────────────────────────────────────────────
#  DB SETUP
# ─────────────────────────────────────────────

DB_PATH = "modtools.db"


async def _ensure_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trusted_users (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antibot_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS antibot_whitelist (
                guild_id INTEGER NOT NULL,
                bot_id   INTEGER NOT NULL,
                PRIMARY KEY (guild_id, bot_id)
            )
        """)
        await db.commit()


# ─────────────────────────────────────────────
#  TRUSTED — DB HELPERS
# ─────────────────────────────────────────────

async def _trusted_add(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM trusted_users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO trusted_users (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id)
        )
        await db.commit()
        return True


async def _trusted_remove(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM trusted_users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "DELETE FROM trusted_users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        await db.commit()
        return True


async def _trusted_list(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM trusted_users WHERE guild_id=?",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def _trusted_reset(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM trusted_users WHERE guild_id=?", (guild_id,)
        )
        count = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM trusted_users WHERE guild_id=?", (guild_id,))
        await db.commit()
        return count


# ─────────────────────────────────────────────
#  ANTIBOT — DB HELPERS
# ─────────────────────────────────────────────

async def _channel_add(guild_id: int, channel_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM antibot_channels WHERE guild_id=? AND channel_id=?",
            (guild_id, channel_id)
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO antibot_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        await db.commit()
        return True


async def _channel_remove(guild_id: int, channel_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM antibot_channels WHERE guild_id=? AND channel_id=?",
            (guild_id, channel_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "DELETE FROM antibot_channels WHERE guild_id=? AND channel_id=?",
            (guild_id, channel_id)
        )
        await db.commit()
        return True


async def _channel_list(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT channel_id FROM antibot_channels WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def _channel_reset(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM antibot_channels WHERE guild_id=?", (guild_id,)
        )
        count = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM antibot_channels WHERE guild_id=?", (guild_id,))
        await db.commit()
        return count


async def _whitelist_add(guild_id: int, bot_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM antibot_whitelist WHERE guild_id=? AND bot_id=?",
            (guild_id, bot_id)
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO antibot_whitelist (guild_id, bot_id) VALUES (?, ?)",
            (guild_id, bot_id)
        )
        await db.commit()
        return True


async def _whitelist_remove(guild_id: int, bot_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM antibot_whitelist WHERE guild_id=? AND bot_id=?",
            (guild_id, bot_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "DELETE FROM antibot_whitelist WHERE guild_id=? AND bot_id=?",
            (guild_id, bot_id)
        )
        await db.commit()
        return True


async def _whitelist_list(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT bot_id FROM antibot_whitelist WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def _whitelist_reset(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM antibot_whitelist WHERE guild_id=?", (guild_id,)
        )
        count = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM antibot_whitelist WHERE guild_id=?", (guild_id,))
        await db.commit()
        return count


# ─────────────────────────────────────────────
#  COG
# ─────────────────────────────────────────────

class ModTools(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(_ensure_tables())

    # ══════════════════════════════════════════
    #  ANTIBOT — EVENT LISTENER
    # ══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-delete bot messages in protected channels (unless whitelisted)."""
        if not message.guild or not message.author.bot:
            return

        channels = await _channel_list(message.guild.id)
        if message.channel.id not in channels:
            return

        whitelist = await _whitelist_list(message.guild.id)
        if message.author.id in whitelist:
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ══════════════════════════════════════════
    #  TRUSTED — COMMANDS
    # ══════════════════════════════════════════

    @commands.group(name="trusted", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def trusted(self, ctx):
        view = LayoutView()
        c = Container()
        c.add_item(TextDisplay("## 🛡️ Trusted User System"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Grant elevated permissions to trusted staff members.\n"
            "Trusted users bypass certain bot restrictions.\n"
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "**▶ Available Commands**\n"
            "`.trusted add @user` — Add a trusted member\n"
            "`.trusted remove @user` — Remove a trusted member\n"
            "`.trusted show` — List all trusted members\n"
            "`.trusted reset` — Remove all trusted members"
        ))
        view.add_item(c)
        await ctx.reply(view=view, mention_author=False)

    # ── trusted add ──────────────────────────

    @trusted.command(name="add", help="Add a member to the trusted list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def trusted_add(self, ctx, member: discord.Member = commands.parameter(description="Member to trust")):
        if member.bot:
            return await ctx.reply(
                view=v2_card("⚠️ Invalid Target", "You cannot add a **bot** to the trusted list."),
                mention_author=False
            )
        if member == ctx.author:
            return await ctx.reply(
                view=v2_card("⚠️ Invalid Target", "You cannot add **yourself** to the trusted list."),
                mention_author=False
            )

        added = await _trusted_add(ctx.guild.id, member.id)
        if not added:
            return await ctx.reply(
                view=v2_card("Already Trusted", f"{member.mention} is already in the trusted list."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Trusted Added", f"{member.mention} has been added to the **trusted list**.\nThey now have elevated bot permissions."),
            mention_author=False
        )

    # ── trusted remove ────────────────────────

    @trusted.command(name="remove", help="Remove a member from the trusted list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def trusted_remove(self, ctx, member: discord.Member = commands.parameter(description="Member to untrust")):
        removed = await _trusted_remove(ctx.guild.id, member.id)
        if not removed:
            return await ctx.reply(
                view=v2_card("Not Found", f"{member.mention} is **not** in the trusted list."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Trusted Removed", f"{member.mention} has been removed from the **trusted list**."),
            mention_author=False
        )

    # ── trusted show ──────────────────────────

    @trusted.command(name="show", help="Show all trusted members")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def trusted_show(self, ctx):
        user_ids = await _trusted_list(ctx.guild.id)
        if not user_ids:
            return await ctx.reply(
                view=v2_card("Trusted List", "No trusted members set.\nUse `.trusted add @user` to add one."),
                mention_author=False
            )

        lines = []
        for i, uid in enumerate(user_ids, 1):
            m = ctx.guild.get_member(uid)
            lines.append(f"`{i}.` {m.mention} — `{m}`" if m else f"`{i}.` Unknown — `ID: {uid}`")

        view = LayoutView()
        c = Container()
        c.add_item(TextDisplay(f"## 🛡️ Trusted Members — {ctx.guild.name}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Total:** `{len(user_ids)}` trusted member(s)\n"))
        c.add_item(Separator())
        c.add_item(TextDisplay("\n".join(lines)))
        view.add_item(c)
        await ctx.reply(view=view, mention_author=False)

    # ── trusted reset ─────────────────────────

    @trusted.command(name="reset", help="Reset all trusted members")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def trusted_reset(self, ctx):
        user_ids = await _trusted_list(ctx.guild.id)
        if not user_ids:
            return await ctx.reply(
                view=v2_card("Nothing to Reset", "There are no trusted members to remove."),
                mention_author=False
            )

        confirm_btn = Button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_btn  = Button(label="Cancel",        style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "⚠️ Confirm Reset",
                f"Are you sure you want to remove **all {len(user_ids)} trusted member(s)**?\nThis action **cannot be undone**.",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            removed = await _trusted_reset(ctx.guild.id)
            await interaction.response.edit_message(
                view=v2_card("✅ Trusted Reset", f"Successfully removed **{removed}** trusted member(s).")
            )

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", "Trusted list reset has been **cancelled**."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ══════════════════════════════════════════
    #  ANTIBOT — COMMANDS
    # ══════════════════════════════════════════

    @commands.group(name="antibot", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def antibot(self, ctx):
        view = LayoutView()
        c = Container()
        c.add_item(TextDisplay("## 🚫 Antibot — Auto Delete"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Automatically delete bot messages in protected channels.\n"
            "Whitelist specific bots to let them post freely.\n"
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "**▶ Channel Commands**\n"
            "`.antibot channel add <#channel>` — Protect a channel\n"
            "`.antibot channel remove <#channel>` — Unprotect a channel\n"
            "`.antibot channel show` — List protected channels\n"
            "`.antibot channel reset` — Remove all protected channels\n"
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "**▶ Whitelist Commands**\n"
            "`.antibot whitelist add <@bot>` — Whitelist a bot\n"
            "`.antibot whitelist remove <@bot>` — Remove from whitelist\n"
            "`.antibot whitelist show` — List whitelisted bots\n"
            "`.antibot whitelist reset` — Clear all whitelisted bots"
        ))
        view.add_item(c)
        await ctx.reply(view=view, mention_author=False)

    # ── antibot channel ───────────────────────

    @antibot.group(name="channel", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def antibot_channel(self, ctx):
        await ctx.invoke(self.antibot)

    @antibot_channel.command(name="add", help="Add a channel to antibot protection")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def channel_add(self, ctx, channel: discord.TextChannel = commands.parameter(description="Channel to protect")):
        added = await _channel_add(ctx.guild.id, channel.id)
        if not added:
            return await ctx.reply(
                view=v2_card("Already Protected", f"{channel.mention} is already in the **antibot list**."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Channel Protected", f"{channel.mention} is now **protected**.\nBot messages will be auto-deleted here."),
            mention_author=False
        )

    @antibot_channel.command(name="remove", help="Remove a channel from antibot protection")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def channel_remove(self, ctx, channel: discord.TextChannel = commands.parameter(description="Channel to unprotect")):
        removed = await _channel_remove(ctx.guild.id, channel.id)
        if not removed:
            return await ctx.reply(
                view=v2_card("Not Found", f"{channel.mention} is **not** in the protection list."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Channel Removed", f"{channel.mention} removed from **antibot protection**."),
            mention_author=False
        )

    @antibot_channel.command(name="show", help="Show all antibot-protected channels")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def channel_show(self, ctx):
        channel_ids = await _channel_list(ctx.guild.id)
        if not channel_ids:
            return await ctx.reply(
                view=v2_card("Protected Channels", "No channels protected yet.\nUse `.antibot channel add #channel` to add one."),
                mention_author=False
            )

        lines = []
        for i, cid in enumerate(channel_ids, 1):
            ch = ctx.guild.get_channel(cid)
            lines.append(f"`{i}.` {ch.mention}" if ch else f"`{i}.` Deleted Channel — `ID: {cid}`")

        view = LayoutView()
        c = Container()
        c.add_item(TextDisplay("## 🚫 Antibot Protected Channels"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Total:** `{len(channel_ids)}` protected channel(s)\n"))
        c.add_item(Separator())
        c.add_item(TextDisplay("\n".join(lines)))
        view.add_item(c)
        await ctx.reply(view=view, mention_author=False)

    @antibot_channel.command(name="reset", help="Reset all protected channels")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def channel_reset(self, ctx):
        channels = await _channel_list(ctx.guild.id)
        if not channels:
            return await ctx.reply(
                view=v2_card("Nothing to Reset", "No protected channels to remove."),
                mention_author=False
            )

        confirm_btn = Button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_btn  = Button(label="Cancel",        style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "⚠️ Confirm Reset",
                f"Are you sure you want to remove **all {len(channels)} protected channel(s)**?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            removed = await _channel_reset(ctx.guild.id)
            await interaction.response.edit_message(
                view=v2_card("✅ Channels Reset", f"Removed **{removed}** protected channel(s).")
            )

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", "Channel reset has been **cancelled**."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

    # ── antibot whitelist ─────────────────────

    @antibot.group(name="whitelist", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def antibot_whitelist(self, ctx):
        await ctx.invoke(self.antibot)

    @antibot_whitelist.command(name="add", help="Whitelist a bot from antibot deletion")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def whitelist_add(self, ctx, bot_member: discord.Member = commands.parameter(description="Bot to whitelist")):
        if not bot_member.bot:
            return await ctx.reply(
                view=v2_card("⚠️ Not a Bot", f"{bot_member.mention} is **not a bot**. Only bots can be whitelisted."),
                mention_author=False
            )
        added = await _whitelist_add(ctx.guild.id, bot_member.id)
        if not added:
            return await ctx.reply(
                view=v2_card("Already Whitelisted", f"{bot_member.mention} is already in the **whitelist**."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Bot Whitelisted", f"{bot_member.mention} added to **whitelist**.\nIts messages won't be deleted."),
            mention_author=False
        )

    @antibot_whitelist.command(name="remove", help="Remove a bot from the whitelist")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def whitelist_remove(self, ctx, bot_member: discord.Member = commands.parameter(description="Bot to remove")):
        removed = await _whitelist_remove(ctx.guild.id, bot_member.id)
        if not removed:
            return await ctx.reply(
                view=v2_card("Not Found", f"{bot_member.mention} is **not** in the whitelist."),
                mention_author=False
            )
        await ctx.reply(
            view=v2_card("✅ Removed from Whitelist", f"{bot_member.mention} removed from **antibot whitelist**."),
            mention_author=False
        )

    @antibot_whitelist.command(name="show", help="Show all whitelisted bots")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def whitelist_show(self, ctx):
        bot_ids = await _whitelist_list(ctx.guild.id)
        if not bot_ids:
            return await ctx.reply(
                view=v2_card("Whitelist", "No bots whitelisted yet.\nUse `.antibot whitelist add @bot` to add one."),
                mention_author=False
            )

        lines = []
        for i, bid in enumerate(bot_ids, 1):
            m = ctx.guild.get_member(bid)
            lines.append(f"`{i}.` {m.mention} — `{m}`" if m else f"`{i}.` Unknown Bot — `ID: {bid}`")

        view = LayoutView()
        c = Container()
        c.add_item(TextDisplay("## ✅ Antibot Whitelist"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Total:** `{len(bot_ids)}` whitelisted bot(s)\n"))
        c.add_item(Separator())
        c.add_item(TextDisplay("\n".join(lines)))
        view.add_item(c)
        await ctx.reply(view=view, mention_author=False)

    @antibot_whitelist.command(name="reset", help="Reset all whitelisted bots")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def whitelist_reset(self, ctx):
        bots = await _whitelist_list(ctx.guild.id)
        if not bots:
            return await ctx.reply(
                view=v2_card("Nothing to Reset", "The whitelist is already empty."),
                mention_author=False
            )

        confirm_btn = Button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_btn  = Button(label="Cancel",        style=discord.ButtonStyle.secondary)

        await ctx.reply(
            view=v2_confirm_card(
                "⚠️ Confirm Reset",
                f"Are you sure you want to remove **all {len(bots)} whitelisted bot(s)**?",
                confirm_btn, cancel_btn
            ),
            mention_author=False
        )

        async def confirm_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            removed = await _whitelist_reset(ctx.guild.id)
            await interaction.response.edit_message(
                view=v2_card("✅ Whitelist Cleared", f"Removed **{removed}** bot(s) from the whitelist.")
            )

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This is not for you!", ephemeral=True)
            await interaction.response.edit_message(
                view=v2_card("Cancelled", "Whitelist reset has been **cancelled**."))

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb


async def setup(bot):
    await bot.add_cog(ModTools(bot))
