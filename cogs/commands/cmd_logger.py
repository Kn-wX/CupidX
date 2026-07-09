from __future__ import annotations

import aiosqlite
import discord
from discord.ext import commands, tasks

from utils.config import OWNER_IDS

# ═══════════════════════════════════════════════════════
#                    EMOJI / COLOR CONFIG
# ═══════════════════════════════════════════════════════
TICK    = "<:CupidXtick1:1474369967271968949>"
CROSS   = "<:CupidXCross:1473996646873436336>"
WARN    = "<:CupidXWarning:1474348304186867784>"
LOADING = "<a:CupidXloading:1474386958741536891>"
GUILD_E = "<a:CupidXSecurity:1474353507615248472>"
GLOBE   = "<a:CupidXping:1480122681150930997>"
CROWN   = "<:crown:1486975202125680753>"
CMD_E   = "<:CupidXCommands:1475152376737566722>"

# ── All embeds BLACK ──
COLOR_BLACK   = 0x000000
COLOR_SUCCESS = 0x57F287
COLOR_WARN    = 0xFEE75C

MEDALS   = ["🥇", "🥈", "🥉"]
PER_PAGE = 4
DB_PATH  = "db/cmd_logger.db"


# ═══════════════════════════════════════════════════════
#   PERSONAL EPHEMERAL VIEW  (private per-user session)
# ═══════════════════════════════════════════════════════
class PersonalRankView(discord.ui.View):
    """
    Sent as ephemeral — only the clicker sees it.
    Each user navigates their own pages independently.
    No other user sees anything change.
    """

    def __init__(self, cog: "CmdLogger", user_id: int, start_page: int = 0):
        super().__init__(timeout=120)
        self.cog     = cog
        self.user_id = user_id
        self.page    = start_page

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"> {WARN} Ye sirf tumhare liye hai.", ephemeral=True
            )
            return False
        return True

    async def _build_embed(self) -> discord.Embed:
        total_db, total_cmds = await self.cog._get_totals()
        total_live           = len(self.cog.client.guilds)
        max_page             = max(0, (total_db - 1) // PER_PAGE) if total_db else 0
        self.page            = max(0, min(self.page, max_page))

        rows   = await self.cog._get_page_rows(self.page)
        offset = self.page * PER_PAGE

        embed = discord.Embed(
            title=f"{CMD_E}  CupidX — Command Usage Rank",
            color=COLOR_BLACK
        )
        embed.set_thumbnail(url=self.cog.client.user.display_avatar.url)

        if not rows:
            embed.description = f"> {WARN} No command usage recorded yet."
        else:
            lines = []
            for i, (guild_id, guild_name, count) in enumerate(rows, 1):
                global_rank = offset + i
                medal = MEDALS[global_rank - 1] if global_rank <= 3 else f"`#{global_rank}`"
                g     = self.cog.client.get_guild(guild_id)
                name  = g.name if g else guild_name
                lines.append(
                    f"{medal} **{name}**\n"
                    f"　　{CMD_E} **Cmnd use:** {count:,}"
                )
            embed.description = "\n\n".join(lines)

        embed.set_footer(
            text=(
                f"Page {self.page + 1}/{max_page + 1}  •  "
                f"Total Guilds: {total_live}  •  "
                f"Total Commands: {total_cmds:,}"
            ),
            icon_url=self.cog.client.user.display_avatar.url
        )
        embed.timestamp = discord.utils.utcnow()

        # Disable buttons at boundaries
        self.btn_first.disabled = self.page == 0
        self.btn_prev.disabled  = self.page == 0
        self.btn_next.disabled  = self.page >= max_page
        self.btn_last.disabled  = self.page >= max_page
        return embed

    async def _refresh(self, interaction: discord.Interaction):
        embed = await self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏮ First", style=discord.ButtonStyle.secondary,
                       custom_id="pr_first")
    async def btn_first(self, interaction: discord.Interaction, _):
        self.page = 0
        await self._refresh(interaction)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary,
                       custom_id="pr_prev")
    async def btn_prev(self, interaction: discord.Interaction, _):
        if self.page > 0:
            self.page -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary,
                       custom_id="pr_next")
    async def btn_next(self, interaction: discord.Interaction, _):
        total    = await self.cog._total_guilds_in_db()
        max_page = max(0, (total - 1) // PER_PAGE)
        if self.page < max_page:
            self.page += 1
        await self._refresh(interaction)

    @discord.ui.button(label="Last ⏭", style=discord.ButtonStyle.secondary,
                       custom_id="pr_last")
    async def btn_last(self, interaction: discord.Interaction, _):
        total    = await self.cog._total_guilds_in_db()
        max_page = max(0, (total - 1) // PER_PAGE)
        self.page = max_page
        await self._refresh(interaction)

    async def on_timeout(self):
        pass   # Silently expire


# ═══════════════════════════════════════════════════════
#   PUBLIC LIVE EMBED VIEW  (pinned on channel)
#   Buttons open a PRIVATE session — public embed untouched
# ═══════════════════════════════════════════════════════
class LiveEmbedView(discord.ui.View):
    """
    Persistent buttons on the public pinned embed.
    Any click → ephemeral private paginated view for that user only.
    Public embed is NEVER affected by button clicks.
    """

    def __init__(self, cog: "CmdLogger"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _open_private(self, interaction: discord.Interaction, start_page: int):
        view  = PersonalRankView(self.cog, interaction.user.id, start_page)
        embed = await view._build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="⏮ First", style=discord.ButtonStyle.secondary,
                       custom_id="live_first")
    async def live_first(self, interaction: discord.Interaction, _):
        await self._open_private(interaction, 0)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary,
                       custom_id="live_prev")
    async def live_prev(self, interaction: discord.Interaction, _):
        await self._open_private(interaction, 0)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary,
                       custom_id="live_next")
    async def live_next(self, interaction: discord.Interaction, _):
        total    = await self.cog._total_guilds_in_db()
        max_page = max(0, (total - 1) // PER_PAGE)
        await self._open_private(interaction, min(1, max_page))

    @discord.ui.button(label="Last ⏭", style=discord.ButtonStyle.secondary,
                       custom_id="live_last")
    async def live_last(self, interaction: discord.Interaction, _):
        total    = await self.cog._total_guilds_in_db()
        max_page = max(0, (total - 1) // PER_PAGE)
        await self._open_private(interaction, max_page)


# ═══════════════════════════════════════════════════════
#                        COG
# ═══════════════════════════════════════════════════════
class CmdLogger(commands.Cog):
    """Tracks command usage per guild — live leaderboard with private pagination."""

    def __init__(self, client: commands.Bot):
        self.client              = client
        self.log_channel_id: int | None = None
        self.rank_message_id: int | None = None
        self._db_ready           = False
        self._live_view          = LiveEmbedView(self)
        self.client.loop.create_task(self._init_db())

    # ── DB ────────────────────────────────────────────

    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_cmd_count (
                    guild_id   INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    count      INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cmd_logger_settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await db.commit()

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM cmd_logger_settings") as cur:
                for key, val in await cur.fetchall():
                    if key == "log_channel_id" and val:
                        self.log_channel_id = int(val)
                    elif key == "rank_message_id" and val:
                        self.rank_message_id = int(val)

        self._db_ready = True
        if not self.live_rank_update.is_running():
            self.live_rank_update.start()

    async def _save_setting(self, key: str, value: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cmd_logger_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            await db.commit()

    # ── Helpers ───────────────────────────────────────

    async def _increment(self, guild: discord.Guild):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO guild_cmd_count (guild_id, guild_name, count)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id) DO UPDATE SET
                    guild_name = excluded.guild_name,
                    count = count + 1
            """, (guild.id, guild.name))
            await db.commit()

    async def _total_guilds_in_db(self) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM guild_cmd_count") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    async def _get_page_rows(self, page: int):
        offset = page * PER_PAGE
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id, guild_name, count FROM guild_cmd_count "
                "ORDER BY count DESC LIMIT ? OFFSET ?",
                (PER_PAGE, offset)
            ) as cur:
                return await cur.fetchall()

    async def _get_totals(self):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*), SUM(count) FROM guild_cmd_count"
            ) as cur:
                row = await cur.fetchone()
                return (row[0] or 0), (row[1] or 0)

    # ── Public live embed (always page 1) ─────────────

    async def _build_live_embed(self) -> discord.Embed:
        total_db, total_cmds = await self._get_totals()
        total_live           = len(self.client.guilds)
        max_page             = max(0, (total_db - 1) // PER_PAGE) if total_db else 0
        rows                 = await self._get_page_rows(0)

        embed = discord.Embed(
            title=f"{CMD_E}  CupidX — Command Usage Rank",
            color=COLOR_BLACK
        )
        embed.set_thumbnail(url=self.client.user.display_avatar.url)

        if not rows:
            embed.description = f"> {WARN} No command usage recorded yet."
        else:
            lines = []
            for i, (guild_id, guild_name, count) in enumerate(rows, 1):
                medal = MEDALS[i - 1] if i <= 3 else f"`#{i}`"
                g     = self.client.get_guild(guild_id)
                name  = g.name if g else guild_name
                lines.append(
                    f"{medal} **{name}**\n"
                    f"　　{CMD_E} **Cmnd use:** {count:,}"
                )
            embed.description = "\n\n".join(lines)

        embed.set_footer(
            text=(
                f"Page 1/{max_page + 1}  •  "
                f"Total Guilds: {total_live}  •  "
                f"Total Commands: {total_cmds:,}  •  "
                f"Updates every 5s  |  Buttons = Only you can see"
            ),
            icon_url=self.client.user.display_avatar.url
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    # ── Live task ─────────────────────────────────────

    @tasks.loop(seconds=30)
    async def live_rank_update(self):
        if not self._db_ready or not self.log_channel_id:
            return

        channel = self.client.get_channel(self.log_channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        embed = await self._build_live_embed()

        import datetime

        # Agar message exist karta hai
        if self.rank_message_id:
            try:
                msg = await channel.fetch_message(self.rank_message_id)

                # 50 minute se purana hai → delete karke naya bhejo (429 avoid)
                age = (discord.utils.utcnow() - msg.created_at).total_seconds()
                if age > 3000:
                    await msg.delete()
                    self.rank_message_id = None
                    await self._save_setting("rank_message_id", "")
                else:
                    await msg.edit(embed=embed, view=self._live_view)
                    return

            except discord.HTTPException as e:
                if e.status == 429:
                    # Rate limited — skip is iteration
                    return
                # NotFound ya kuch aur → naya message bhejo
                self.rank_message_id = None
            except discord.Forbidden:
                return

        # Naya message bhejo
        try:
            msg = await channel.send(embed=embed, view=self._live_view)
            self.rank_message_id = msg.id
            await self._save_setting("rank_message_id", str(msg.id))
        except Exception:
            pass

    @live_rank_update.before_loop
    async def before_live(self):
        await self.client.wait_until_ready()

    # ── Event ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if ctx.guild and not ctx.author.bot:
            await self._increment(ctx.guild)

    # ════════════════════════════════════════════════
    #   COMMANDS
    # ════════════════════════════════════════════════

    @commands.hybrid_command(
        name="setlogchannel",
        aliases=["setrankchannel", "setcmdlog"],
        help="Set the channel for live rank embed."
    )
    @commands.is_owner()
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        # Delete old rank message so no duplicate embed appears
        if self.rank_message_id and self.log_channel_id:
            old_ch = self.client.get_channel(self.log_channel_id)
            if old_ch and isinstance(old_ch, discord.TextChannel):
                try:
                    old_msg = await old_ch.fetch_message(self.rank_message_id)
                    await old_msg.delete()
                except Exception:
                    pass

        self.log_channel_id  = channel.id
        self.rank_message_id = None
        await self._save_setting("log_channel_id",  str(channel.id))
        await self._save_setting("rank_message_id", "")

        embed = discord.Embed(
            title=f"{TICK}  Log Channel Set",
            description=(
                f"> {GUILD_E} Channel: {channel.mention}\n"
                f"> {CMD_E} Live rank embed will appear there every **5 seconds**."
            ),
            color=COLOR_BLACK
        )
        embed.set_footer(text="CupidX Rank Logger", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(
        name="cmdrank",
        aliases=["commandrank", "serverrank", "topservers"],
        help="Show current command usage rank."
    )
    @commands.is_owner()
    async def cmd_rank(self, ctx: commands.Context):
        embed = await self._build_live_embed()
        await ctx.send(embed=embed, view=self._live_view)

    @commands.command(
        name="resetcmdrank",
        aliases=["resetrank"],
        help="Reset all command usage counts."
    )
    @commands.is_owner()
    async def reset_cmd_rank(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM guild_cmd_count")
            await db.commit()

        embed = discord.Embed(
            title=f"{TICK}  Rank Reset",
            description=f"> {WARN} All command usage counts have been cleared.",
            color=COLOR_WARN
        )
        embed.set_footer(text="CupidX Rank Logger", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await ctx.reply(embed=embed, mention_author=False)


async def setup(client: commands.Bot):
    await client.add_cog(CmdLogger(client))
