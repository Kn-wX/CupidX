import discord
from discord.ext import commands
import aiosqlite
import asyncio
import os
import time
from typing import Optional

# ═══════════════════════════════════════════
#           CONFIGURATION
# ═══════════════════════════════════════════
COLOR   = 0x2b2d31
db_path = "db/afk.db"

TICK    = "<:CupidXtick1:1474369967271968949>"
CROSS   = "<:CupidXCross:1473996646873436336>"
WARN    = "<:CupidXWarning:1474348304186867784>"
LOADING = "<a:CupidXloading:1474386958741536891>"

# ═══════════════════════════════════════════
#           V2 CARD HELPERS
# ═══════════════════════════════════════════


def _v2_card(text: str, controls=None, timeout: float = 120.0) -> discord.ui.LayoutView:
    items: list = [discord.ui.TextDisplay(text)]
    if controls:
        items.append(discord.ui.Separator())
        for c_ in controls:
            items.append(c_)
    view = discord.ui.LayoutView(timeout=timeout)
    view.add_item(discord.ui.Container(*items))
    return view


def _v2_loading(text: str) -> discord.ui.LayoutView:
    return _v2_card(f"{LOADING} {text}")


def _v2_simple(text: str) -> discord.ui.LayoutView:
    return _v2_card(text)


# ═══════════════════════════════════════════
#           AFK SETUP VIEW  (V2 Style)
# ═══════════════════════════════════════════
class AFKSystemView(discord.ui.LayoutView):
    def __init__(self, user: discord.Member, reason: str):
        super().__init__(timeout=60)
        self.user      = user
        self.reason    = reason
        self.mode      = None
        self.dm        = None
        self.cancelled = False
        self._msg      = None   # set after reply so on_timeout can edit
        self._build_step1()

    # ── Step 1 ────────────────────────────────
    def _build_step1(self):
        self.clear_items()

        # Server AFK — danger (red/orange, closest Discord supports to orange)
        btn_server = discord.ui.Button(
            label="Server AFK",
            style=discord.ButtonStyle.danger,
            custom_id="afk_server",
        )
        btn_global = discord.ui.Button(
            label="Global AFK",
            style=discord.ButtonStyle.secondary,
            custom_id="afk_global",
        )
        btn_cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="afk_cancel_1",
        )

        btn_server.callback = self._server_cb
        btn_global.callback = self._global_cb
        btn_cancel.callback = self._cancel_cb

        text = (
            f"## AFK Setup  —  Step 1 / 2\n"
            f"**Reason:** {self.reason}\n\n"
            f"**Server AFK** — Only active in this server\n"
            f"**Global AFK** — Active across all servers\n\n"
            f"-# This menu will expire in 60 seconds."
        )
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            discord.ui.Separator(),
            discord.ui.ActionRow(btn_server, btn_global, btn_cancel),
        )
        self.add_item(container)

    # ── Step 2 ────────────────────────────────
    def _build_step2(self):
        self.clear_items()

        btn_yes    = discord.ui.Button(label="Enable DM Logs",  style=discord.ButtonStyle.secondary, custom_id="afk_dm_yes")
        btn_no     = discord.ui.Button(label="Disable DM Logs", style=discord.ButtonStyle.secondary, custom_id="afk_dm_no")
        btn_cancel = discord.ui.Button(label="Cancel",          style=discord.ButtonStyle.secondary, custom_id="afk_cancel_2")

        btn_yes.callback    = self._dm_yes_cb
        btn_no.callback     = self._dm_no_cb
        btn_cancel.callback = self._cancel_cb

        scope_label = "Server" if self.mode == "server" else "Global"
        text = (
            f"## AFK Setup  —  Step 2 / 2\n"
            f"**Scope:** `{scope_label}`\n"
            f"**Reason:** {self.reason}\n\n"
            f"Would you like DM notifications when someone mentions you?\n\n"
            f"-# This menu will expire in 60 seconds."
        )
        container = discord.ui.Container(
            discord.ui.TextDisplay(text),
            discord.ui.Separator(),
            discord.ui.ActionRow(btn_yes, btn_no, btn_cancel),
        )
        self.add_item(container)

    # ── Callbacks ─────────────────────────────
    async def _blocked(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                view=_v2_simple("This menu is only for you!"),
                
                ephemeral=True
            )
            return True
        return False

    async def _server_cb(self, interaction: discord.Interaction):
        if await self._blocked(interaction): return
        self.mode = "server"
        self._build_step2()
        await interaction.response.edit_message(view=self)

    async def _global_cb(self, interaction: discord.Interaction):
        if await self._blocked(interaction): return
        self.mode = "global"
        self._build_step2()
        await interaction.response.edit_message(view=self)

    async def _cancel_cb(self, interaction: discord.Interaction):
        if await self._blocked(interaction): return
        self.cancelled = True
        self.stop()
        await interaction.response.edit_message(
            view=_v2_simple("## AFK Setup Cancelled\nThe AFK setup was cancelled."),
            
        )

    async def _dm_yes_cb(self, interaction: discord.Interaction):
        if await self._blocked(interaction): return
        self.dm = "True"
        await interaction.response.defer()
        self.stop()

    async def _dm_no_cb(self, interaction: discord.Interaction):
        if await self._blocked(interaction): return
        self.dm = "False"
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        try:
            if self._msg:
                await self._msg.edit(
                    view=_v2_simple("## AFK Setup Expired\nThis menu has expired. Please run `/afk` again."),
                    
                )
        except Exception:
            pass


# ═══════════════════════════════════════════
#           AFK COG
# ═══════════════════════════════════════════
class afk(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        async with aiosqlite.connect(db_path) as db:

            cur = await db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='afk'"
            )
            existing = await cur.fetchone()
            needs_migration = False

            if existing:
                table_sql = existing[0] or ""
                if ("PRIMARY KEY (user_id, guild_id)" not in table_sql and
                        "PRIMARY KEY(user_id, guild_id)" not in table_sql):
                    needs_migration = True

            if needs_migration:
                for col_sql in [
                    "ALTER TABLE afk ADD COLUMN scope    TEXT    DEFAULT 'server'",
                    "ALTER TABLE afk ADD COLUMN guild_id INTEGER DEFAULT 0",
                ]:
                    try:
                        await db.execute(col_sql)
                    except Exception:
                        pass
                await db.commit()

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS afk_new (
                        user_id  INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL DEFAULT 0,
                        AFK      TEXT,
                        reason   TEXT,
                        time     INTEGER,
                        mentions INTEGER DEFAULT 0,
                        dm       TEXT    DEFAULT 'False',
                        scope    TEXT    DEFAULT 'server',
                        PRIMARY KEY (user_id, guild_id)
                    )
                """)
                await db.execute("""
                    INSERT OR IGNORE INTO afk_new
                        (user_id, guild_id, AFK, reason, time, mentions, dm, scope)
                    SELECT
                        user_id,
                        COALESCE(guild_id, 0),
                        AFK, reason, time,
                        COALESCE(mentions, 0),
                        COALESCE(dm, 'False'),
                        COALESCE(scope, 'server')
                    FROM afk
                """)
                await db.execute("DROP TABLE afk")
                await db.execute("ALTER TABLE afk_new RENAME TO afk")
                await db.commit()

            else:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS afk (
                        user_id  INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL DEFAULT 0,
                        AFK      TEXT,
                        reason   TEXT,
                        time     INTEGER,
                        mentions INTEGER DEFAULT 0,
                        dm       TEXT    DEFAULT 'False',
                        scope    TEXT    DEFAULT 'server',
                        PRIMARY KEY (user_id, guild_id)
                    )
                """)
                await db.commit()

    # ── Time Formatter ──
    def time_formatter(self, seconds: int) -> str:
        if seconds < 1: return "0s"
        minutes, seconds = divmod(int(seconds), 60)
        hours,   minutes = divmod(minutes, 60)
        days,    hours   = divmod(hours,   24)
        parts = []
        if days:    parts.append(f"**{days}**d")
        if hours:   parts.append(f"**{hours}**h")
        if minutes: parts.append(f"**{minutes}**m")
        parts.append(f"**{seconds}**s")
        return " ".join(parts)

    # ── Nickname Helper ──
    async def _set_nick(self, member: discord.Member, prefix: str = "[AFK] "):
        try:
            base = member.display_name
            if prefix:
                if not base.startswith("[AFK] "):
                    await member.edit(nick=f"[AFK] {base}"[:32])
            else:
                if base.startswith("[AFK] "):
                    await member.edit(nick=base[6:].strip() or None)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── DB Helpers ──
    async def _get_afk(self, user_id: int, guild_id: int):
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT reason, time, mentions, dm, scope, guild_id FROM afk "
                "WHERE user_id = ? AND guild_id = ? AND AFK = 'True' AND scope = 'server'",
                (user_id, guild_id)
            )
            row = await cur.fetchone()
            if row:
                return row, guild_id

            cur = await db.execute(
                "SELECT reason, time, mentions, dm, scope, guild_id FROM afk "
                "WHERE user_id = ? AND guild_id = 0 AND AFK = 'True' AND scope = 'global'",
                (user_id,)
            )
            row = await cur.fetchone()
            if row:
                return row, 0

        return None, None

    async def _remove_afk(self, user_id: int, guild_id: int, scope: str):
        async with aiosqlite.connect(db_path) as db:
            if scope == 'server':
                await db.execute(
                    "UPDATE afk SET AFK = 'False', mentions = 0 "
                    "WHERE user_id = ? AND guild_id = ? AND scope = 'server'",
                    (user_id, guild_id)
                )
            else:
                await db.execute(
                    "UPDATE afk SET AFK = 'False', mentions = 0 "
                    "WHERE user_id = ? AND guild_id = 0 AND scope = 'global'",
                    (user_id,)
                )
            await db.commit()

    # ── Auto Delete Helper ──
    async def _auto_delete(self, message: discord.Message, delay: int):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass

    # ════════════════════════════════════════
    #           ON MESSAGE LISTENER
    # ════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # ── Welcome Back ──
        row, _ = await self._get_afk(message.author.id, message.guild.id)
        if row:
            m_reason, m_time, m_mentions, m_dm, m_scope, m_guild_id = row
            duration_str = self.time_formatter(int(time.time()) - int(m_time))
            await self._remove_afk(message.author.id, message.guild.id, m_scope)
            await self._set_nick(message.author, prefix="")

            text = (
                f"## Welcome Back!\n"
                f"**{message.author.display_name}**, your AFK has been removed.\n\n"
                f"**Duration:** {duration_str}\n"
                f"**Reason was:** {m_reason}\n"
                f"**Mentions:** `{m_mentions}`"
            )
            try:
                sent = await message.reply(view=_v2_simple(text), mention_author=False)
                asyncio.create_task(self._auto_delete(sent, 6))
            except Exception:
                pass
            return  # ✅ Stop here — don't process mentions for the returning user's message

        # ── Mention Check ──
        if not message.mentions:
            return

        for member in message.mentions:
            if member.id == message.author.id:
                continue

            info_row, _ = await self._get_afk(member.id, message.guild.id)
            if not info_row:
                continue

            m_reason, m_time, m_mentions, m_dm, m_scope, m_guild_id = info_row
            since_str = self.time_formatter(int(time.time()) - int(m_time))

            text = (
                f"## User is AFK\n"
                f"**{member.display_name}** is currently AFK.\n\n"
                f"**Reason:** {m_reason}\n"
                f"**Since:** <t:{m_time}:R> ({since_str} ago)\n\n"
                f"-# This message will disappear in 6 seconds."
            )
            try:
                sent = await message.reply(view=_v2_simple(text), mention_author=False)
                asyncio.create_task(self._auto_delete(sent, 6))
            except Exception:
                pass

            # ✅ Separate DB connection per mention update — no nesting
            async with aiosqlite.connect(db_path) as db:
                if m_scope == 'global':
                    await db.execute(
                        "UPDATE afk SET mentions = mentions + 1 "
                        "WHERE user_id = ? AND guild_id = 0 AND scope = 'global'",
                        (member.id,)
                    )
                else:
                    await db.execute(
                        "UPDATE afk SET mentions = mentions + 1 "
                        "WHERE user_id = ? AND guild_id = ? AND scope = 'server'",
                        (member.id, message.guild.id)
                    )
                await db.commit()

            # ── DM Log ──
            if m_dm == "True":
                try:
                    jump_btn = discord.ui.Button(
                        label="Jump to Message",
                        url=message.jump_url,
                        style=discord.ButtonStyle.link
                    )
                    dm_text = (
                        f"## AFK Mention Log\n"
                        f"**Mentioned By:** {message.author.mention} (`{message.author.id}`)\n"
                        f"**Server:** {message.guild.name}\n"
                        f"**Channel:** {message.channel.mention}\n\n"
                        f"**Message:**\n```\n{message.content[:200] or 'No text content.'}\n```\n"
                        f"-# CupidX AFK System"
                    )
                    dm_view = discord.ui.LayoutView(timeout=None)
                    dm_view.add_item(
                        discord.ui.Container(
                            discord.ui.TextDisplay(dm_text),
                            discord.ui.Separator(),
                            discord.ui.ActionRow(jump_btn),
                        )
                    )
                    await member.send(view=dm_view)
                except Exception:
                    pass

    # ════════════════════════════════════════
    #           /afk
    # ════════════════════════════════════════
    @commands.hybrid_command(name="afk", description="Set your AFK status")
    async def afk_cmd(self, ctx, *, reason: Optional[str] = "Away from keyboard"):

        row, _ = await self._get_afk(ctx.author.id, ctx.guild.id)
        if row:
            return await ctx.reply(
                view=_v2_simple(
                    f"## Already AFK\n"
                    f"You are already AFK! Use `/afkremove` to remove it first."
                ),
                
                ephemeral=True,
                mention_author=False
            )

        view = AFKSystemView(ctx.author, reason)
        msg  = await ctx.reply(view=view, mention_author=False)
        view._msg = msg  # for on_timeout
        await view.wait()

        if view.cancelled:
            return

        if view.mode is None or view.dm is None:
            await msg.edit(
                view=_v2_simple(
                    "## Setup Timed Out\nAFK setup timed out. Please run `/afk` again."
                ),
                
            )
            return

        save_guild_id = ctx.guild.id if view.mode == "server" else 0

        # ── Loading animation ──
        for step in [
            "## Setting AFK\n\n`1%`   ▱▱▱▱▱▱▱▱▱▱  Initializing...",
            "## Setting AFK\n\n`15%`  ██▱▱▱▱▱▱▱▱  Verifying user...",
            "## Setting AFK\n\n`40%`  ████▱▱▱▱▱▱  Applying scope...",
            "## Setting AFK\n\n`60%`  ██████▱▱▱▱  Writing to database...",
            "## Setting AFK\n\n`80%`  ████████▱▱  Updating nickname...",
            "## Setting AFK\n\n`100%` ██████████  Done!",
        ]:
            await asyncio.sleep(0.6)
            try:
                await msg.edit(view=_v2_simple(step))
            except Exception:
                break

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO afk
                   (user_id, guild_id, AFK, reason, time, mentions, dm, scope)
                   VALUES (?, ?, 'True', ?, ?, 0, ?, ?)""",
                (ctx.author.id, save_guild_id, reason, int(time.time()), view.dm, view.mode)
            )
            await db.commit()

        await self._set_nick(ctx.author, prefix="[AFK] ")

        scope_label = "Server"  if view.mode == "server" else "Global"
        dm_label    = "Enabled" if view.dm == "True"     else "Disabled"

        text = (
            f"## AFK Activated\n"
            f"**{ctx.author.display_name}** is now AFK.\n\n"
            f"**Reason:** {reason}\n"
            f"**Scope:** {scope_label}\n"
            f"**DM Logs:** {dm_label}\n\n"
            f"-# Your AFK will be removed when you send a message."
        )
        await msg.edit(view=_v2_simple(text))

    # ════════════════════════════════════════
    #           /afkremove
    # ════════════════════════════════════════
    @commands.hybrid_command(name="afkremove", description="Manually remove your AFK status")
    async def afk_remove(self, ctx):
        row, _ = await self._get_afk(ctx.author.id, ctx.guild.id)
        if not row:
            return await ctx.reply(
                view=_v2_simple("## Not AFK\nYou are not AFK right now."),
                
                ephemeral=True,
                mention_author=False
            )

        m_reason, m_time, m_mentions, m_dm, m_scope, m_guild_id = row
        duration_str = self.time_formatter(int(time.time()) - int(m_time))
        await self._remove_afk(ctx.author.id, ctx.guild.id, m_scope)
        await self._set_nick(ctx.author, prefix="")

        text = (
            f"## AFK Removed\n"
            f"**{ctx.author.display_name}**'s AFK has been removed.\n\n"
            f"**Duration:** {duration_str}\n"
            f"**Reason was:** {m_reason}\n"
            f"**Total Mentions:** `{m_mentions}`"
        )
        await ctx.reply(view=_v2_simple(text), mention_author=False)

    # ════════════════════════════════════════
    #           /afkforceremove  (owner only)
    # ════════════════════════════════════════
    @commands.hybrid_command(name="afkforceremove", description="[Owner] Force remove a user's AFK status")
    async def afk_force_remove(self, ctx, member: discord.Member):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply(
                view=_v2_simple("## Permission Denied\nOnly the server owner can use this command."),
                
                ephemeral=True,
                mention_author=False
            )

        row, _ = await self._get_afk(member.id, ctx.guild.id)
        if not row:
            return await ctx.reply(
                view=_v2_simple(f"## Not AFK\n**{member.display_name}** is not AFK right now."),
                
                ephemeral=True,
                mention_author=False
            )

        m_reason, m_time, m_mentions, m_dm, m_scope, m_guild_id = row
        duration_str = self.time_formatter(int(time.time()) - int(m_time))
        await self._remove_afk(member.id, ctx.guild.id, m_scope)
        await self._set_nick(member, prefix="")

        text = (
            f"## AFK Force Removed\n"
            f"**{member.display_name}**'s AFK has been removed by {ctx.author.mention}.\n\n"
            f"**Duration:** {duration_str}\n"
            f"**Reason was:** {m_reason}\n"
            f"**Total Mentions:** `{m_mentions}`\n\n"
            f"-# Removed by {ctx.author.display_name}"
        )
        await ctx.reply(view=_v2_simple(text), mention_author=False)

    # ════════════════════════════════════════
    #           /afkcheck
    # ════════════════════════════════════════
    @commands.hybrid_command(name="afkcheck", description="Check a user's AFK status")
    async def afk_check(self, ctx, member: discord.Member):
        row, _ = await self._get_afk(member.id, ctx.guild.id)
        if not row:
            return await ctx.reply(
                view=_v2_simple(f"## Not AFK\n**{member.display_name}** is not AFK."),
                
                mention_author=False
            )

        m_reason, m_time, m_mentions, m_dm, m_scope, m_guild_id = row
        since_str   = self.time_formatter(int(time.time()) - int(m_time))
        scope_label = "Server" if m_scope == "server" else "Global"

        text = (
            f"## AFK Status\n"
            f"**{member.display_name}** is currently AFK.\n\n"
            f"**Reason:** {m_reason}\n"
            f"**Since:** <t:{m_time}:R> ({since_str} ago)\n"
            f"**Mentions:** `{m_mentions}`\n"
            f"**Scope:** {scope_label}\n"
            f"**DM Logs:** {'On' if m_dm == 'True' else 'Off'}\n\n"
            f"-# Requested by {ctx.author.display_name}"
        )
        await ctx.reply(view=_v2_simple(text), mention_author=False)

    # ════════════════════════════════════════
    #           /afklist
    # ════════════════════════════════════════
    @commands.hybrid_command(name="afklist", description="View all AFK users in this server")
    async def afk_list(self, ctx):
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                """
                SELECT user_id, reason, time, mentions
                FROM afk
                WHERE AFK = 'True'
                  AND (
                    (scope = 'server' AND guild_id = ?)
                    OR
                    (scope = 'global' AND guild_id = 0)
                  )
                ORDER BY time ASC
                """,
                (ctx.guild.id,)
            )
            rows = await cur.fetchall()

        if not rows:
            return await ctx.reply(
                view=_v2_simple(
                    f"## AFK List  —  {ctx.guild.name}\n"
                    f"No one is AFK in this server right now."
                ),
                
                mention_author=False
            )

        lines = [f"## AFK List  —  {ctx.guild.name}\n"]
        for i, (uid, reason, ts, mentions) in enumerate(rows[:15], 1):
            m         = ctx.guild.get_member(uid)
            name      = m.display_name if m else f"<@{uid}>"
            since_str = self.time_formatter(int(time.time()) - int(ts))
            lines.append(
                f"`{i}.` **{name}**\n"
                f"> {reason}  .  {since_str}  .  `{mentions}` mentions"
            )

        lines.append(f"\n-# Total AFK: {len(rows)}")
        await ctx.reply(view=_v2_simple("\n\n".join(lines)), mention_author=False)


async def setup(client):
    await client.add_cog(afk(client))
