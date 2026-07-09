import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import time
from collections import defaultdict
from utils.Tools import *
from utils.detectfile import *

# ================================================
# EMOJI CONFIG
# ================================================

class E:
# Status
    ENABLED  = EMOJI_ENABLE
    DISABLED = EMOJI_DISABLE
    LOADING  = EMOJI_LOADING
    TIMER    = EMOJI_TIMER

    # Actions
    TICK        = EMOJI_TICK
    TICK1       = EMOJI_TICK
    CROSS       = EMOJI_CROSS
    WARNING     = EMOJI_WARN
    DELETE      = EMOJI_TRASH
    QUESTION    = EMOJI_QUESTION
    SHIELD      = EMOJI_SHIELD

    # Info
    USER        = EMOJI_USER
    MENTION     = EMOJI_ROBOT3
    MAIL        = EMOJI_MAIL
    REASON      = EMOJI_APP
    CHANNEL     = EMOJI_APP2
    ROLE        = EMOJI_USE
    LOG         = EMOJI_PUZZLE2
    SETTINGS    = "<:cog:1487152125069889677>"

# ================================================
# SPAM TRACKER (in-memory)
# ================================================

_spam_tracker: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

# ================================================
# DB HELPERS
# ================================================

DB = "db/automod.db"

async def db_exec(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB) as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetch(query: str, params: tuple = (), one=False):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone() if one else await cur.fetchall()

# ================================================
# HELPER: FOOTER
# ================================================

def footer(ctx) -> dict:
    return dict(
        text=f"Command: {ctx.command.qualified_name}  •  Requested by {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
    )

# ================================================
# COMPONENTS V2 HELPERS
# ================================================

def _embed_to_container(embed: discord.Embed, controls=None) -> discord.ui.Container:
    items = []
    if embed.title:
        items.append(discord.ui.TextDisplay(f"## {embed.title}"))
    if embed.description:
        items.append(discord.ui.TextDisplay(embed.description))
    for field in embed.fields:
        items.append(discord.ui.TextDisplay(f"**{field.name}**\n{field.value}"))
    footer_text = getattr(getattr(embed, "footer", None), "text", None)
    if footer_text:
        items.append(discord.ui.TextDisplay(f"-# {footer_text}"))
    if controls:
        if items:
            items.append(discord.ui.Separator())
        for control in controls:
            items.append(control)
    return discord.ui.Container(*items)

def _embed_to_layout(embed: discord.Embed, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=timeout)
    view.add_item(_embed_to_container(embed, controls=controls))
    return view

def _text_to_layout(text: str, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    return _embed_to_layout(discord.Embed(description=text), controls=controls, timeout=timeout)

# ================================================
# HELPER: NOT ENABLED EMBED
# ================================================

def not_enabled_embed(ctx, bot) -> discord.Embed:
    e = discord.Embed(
        title=f"{E.CROSS} Automod Not Enabled",
        description=(
            f"Your server doesn't have Automod enabled yet.\n\n"
            f"**Status:** {E.DISABLED} Disabled\n"
            f"**Enable it:** `{ctx.prefix}automod enable`"
        ),
        color=0x2B2D31
    )
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.set_footer(**footer(ctx))
    return e

# ================================================
# HELPER: ACCESS DENIED
# ================================================

def access_denied_embed(ctx) -> discord.Embed:
    e = discord.Embed(
        title=f"{E.CROSS} Access Denied",
        description="Your top role must be at **same** or **higher** position than my top role.",
        color=0xFF4444
    )
    e.set_footer(**footer(ctx))
    return e

def has_access(ctx) -> bool:
    return ctx.author == ctx.guild.owner or ctx.author.top_role.position >= ctx.guild.me.top_role.position

# ================================================
# CONFIRM DISABLE VIEW
# ================================================

class ConfirmDisable(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.author = author
        self.value  = None

        self.yes_button    = discord.ui.Button(label="Yes, Disable", style=discord.ButtonStyle.secondary)
        self.cancel_button = discord.ui.Button(label="Cancel",        style=discord.ButtonStyle.secondary)

        async def yes_cb(interaction: discord.Interaction):
            self.value = True
            await interaction.response.defer()
            self.stop()

        async def cancel_cb(interaction: discord.Interaction):
            self.value = False
            await interaction.response.defer()
            self.stop()

        self.yes_button.callback    = yes_cb
        self.cancel_button.callback = cancel_cb

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("### Confirm Disable"),
            discord.ui.TextDisplay("Are you sure? This action will disable AutoMod completely."),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.yes_button, self.cancel_button),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} You can't interact with this."), ephemeral=True
            )
            return False
        return True

# ================================================
# SHOW RULES VIEW
# ================================================

class ShowRules(discord.ui.LayoutView):
    def __init__(self, author, selected_events):
        super().__init__(timeout=90)
        self.author          = author
        self.selected_events = selected_events

        rules_button = discord.ui.Button(label="View Rules Info", style=discord.ButtonStyle.secondary)

        async def rules_cb(interaction: discord.Interaction):
            rules = {
                "Anti NSFW link":    "**Anti NSFW Link**\nBlocks messages with NSFW/adult links.\nPunishment: Block message *(fixed)*",
                "Anti caps":         "**Anti Caps**\nTriggers if >70% caps (min 45 chars).\nDefault: Mute 1 min",
                "Anti link":         "**Anti Link**\nBlocks all links (Spotify/GIFs/invites bypassed).\nDefault: Mute 7 min",
                "Anti invites":      "**Anti Invites**\nBlocks Discord server invites (own server bypassed).\nDefault: Mute 12 min",
                "Anti emoji spam":   "**Anti Emoji Spam**\nTriggers if >5 emojis in a message.\nDefault: Mute 1 min",
                "Anti mass mention": "**Anti Mass Mention**\nTriggers if >4 mentions in a message.\nDefault: Mute 3 min",
                "Anti spam":         "**Anti Spam**\nTriggers if >5 messages sent rapidly.\nDefault: Mute 12 min",
                "Anti bad words":    "**Anti Bad Words**\nBlocks configured bad words/phrases.\nDefault: Delete message",
                "Anti flood":        "**Anti Flood**\nBlocks repeated identical messages.\nDefault: Mute 5 min",
                "Anti zalgo":        "**Anti Zalgo**\nBlocks zalgo/corrupted text.\nDefault: Delete message",
            }
            enabled_text = "\n\n".join(rules[ev] for ev in self.selected_events if ev in rules)
            embed = discord.Embed(
                title=f"{E.SETTINGS} Active Module Rules",
                description=enabled_text or "No modules selected."
            )
            embed.set_footer(text="Punishments can be changed via automod punishment command.")
            await interaction.response.send_message(view=_embed_to_layout(embed), ephemeral=True)

        rules_button.callback = rules_cb

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("### Active AutoMod Modules"),
            discord.ui.TextDisplay("Use the button below to review each module's rule summary."),
            discord.ui.Separator(),
            discord.ui.ActionRow(rules_button),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} You can't interact with this."), ephemeral=True
            )
            return False
        return True

# ================================================
# PUNISHMENT SELECT VIEW
# ================================================

class PunishmentView(discord.ui.LayoutView):
    def __init__(self, author, guild_id, events, bot_ref):
        super().__init__(timeout=60)
        self.author          = author
        self.guild_id        = guild_id
        self.events          = events
        self.bot_ref         = bot_ref
        self.selected_events = []

        self.event_select = discord.ui.Select(
            placeholder="Select modules to update...",
            min_values=1,
            max_values=len(events),
            options=[discord.SelectOption(label=ev, value=ev) for ev in events]
        )
        self.event_select.callback = self._event_select_callback

        self.mute_button   = discord.ui.Button(label="Mute",   style=discord.ButtonStyle.secondary, disabled=True)
        self.kick_button   = discord.ui.Button(label="Kick",   style=discord.ButtonStyle.secondary, disabled=True)
        self.ban_button    = discord.ui.Button(label="Ban",    style=discord.ButtonStyle.secondary, disabled=True)
        self.delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.secondary, disabled=True)

        for button, punishment in [
            (self.mute_button,   "Mute"),
            (self.kick_button,   "Kick"),
            (self.ban_button,    "Ban"),
            (self.delete_button, "Delete"),
        ]:
            button.callback = self._make_punishment_cb(punishment)

        self._rebuild_container("### Punishment Settings", "Select modules first, then choose a punishment.")

    def _rebuild_container(self, header: str, body: str | None = None):
        self._children.clear()
        items = [discord.ui.TextDisplay(header)]
        if body:
            items.append(discord.ui.TextDisplay(body))
        items += [
            discord.ui.Separator(),
            discord.ui.ActionRow(self.event_select),
            discord.ui.ActionRow(self.mute_button, self.kick_button, self.ban_button, self.delete_button),
        ]
        self.add_item(discord.ui.Container(*items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} You can't interact with this."), ephemeral=True
            )
            return False
        return True

    def _make_punishment_cb(self, punishment: str):
        async def callback(interaction: discord.Interaction):
            for ev in self.selected_events:
                await db_exec(
                    "INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)",
                    (self.guild_id, ev, punishment)
                )
            updated = await db_fetch(
                "SELECT event, punishment FROM automod_punishments WHERE guild_id = ? AND event != 'Anti NSFW link'",
                (self.guild_id,)
            )
            lines = [f"{E.TICK} **{ev}** → `{pun}`" for ev, pun in updated]
            embed = discord.Embed(
                title=f"{E.TICK1} Punishments Updated",
                description="\n".join(lines) or "No modules configured."
            )
            embed.set_footer(text="Run automod punishment again to change anytime.")
            await interaction.response.edit_message(view=_embed_to_layout(embed))
        return callback

    async def _event_select_callback(self, interaction: discord.Interaction):
        self.selected_events = self.event_select.values
        for btn in [self.mute_button, self.kick_button, self.ban_button, self.delete_button]:
            btn.disabled = False
        self._rebuild_container(
            "### Punishment Settings",
            f"Now pick a punishment for: **{', '.join(self.selected_events)}**"
        )
        await interaction.response.edit_message(view=self)

# ================================================
# MAIN COG
# ================================================

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.default_punishment = "Mute"
        self.bot.loop.create_task(self.init_db())

        self.bad_words = [
            "nigger", "nigga", "faggot", "fag", "retard", "chink",
            "kike", "tranny", "cunt", "whore", "slut"
        ]

    # ── DB INIT ──────────────────────────────────
    async def init_db(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_punishments (
                    guild_id INTEGER,
                    event TEXT,
                    punishment TEXT,
                    PRIMARY KEY (guild_id, event)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_ignored (
                    guild_id INTEGER,
                    type TEXT,
                    id INTEGER,
                    PRIMARY KEY (guild_id, type, id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_logging (
                    guild_id INTEGER,
                    log_channel INTEGER,
                    PRIMARY KEY (guild_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_warn_count (
                    guild_id INTEGER,
                    user_id INTEGER,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    # ── HELPERS ──────────────────────────────────
    async def is_automod_enabled(self, guild_id: int) -> bool:
        row = await db_fetch("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,), one=True)
        return row is not None and row[0] == 1

    async def get_exempt_roles_channels(self, guild_id: int):
        roles    = await db_fetch("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'role'",    (guild_id,))
        channels = await db_fetch("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,))
        return [discord.Object(r[0]) for r in roles], [discord.Object(c[0]) for c in channels]

    async def is_anti_nsfw_enabled(self, guild_id: int) -> bool:
        row = await db_fetch("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti NSFW link'", (guild_id,), one=True)
        return row is not None

    async def get_punishment(self, guild_id: int, event: str) -> str:
        row = await db_fetch("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = ?", (guild_id, event), one=True)
        return row[0] if row else "Mute"

    async def get_log_channel(self, guild_id: int) -> int | None:
        row = await db_fetch("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild_id,), one=True)
        return row[0] if row else None

    async def is_module_enabled(self, guild_id: int, module: str) -> bool:
        row = await db_fetch("SELECT 1 FROM automod_punishments WHERE guild_id = ? AND event = ?", (guild_id, module), one=True)
        return row is not None

    async def is_exempt(self, message: discord.Message) -> bool:
        guild_id = message.guild.id
        exempt_roles, exempt_channels = await self.get_exempt_roles_channels(guild_id)
        exempt_role_ids    = {obj.id for obj in exempt_roles}
        exempt_channel_ids = {obj.id for obj in exempt_channels}
        if message.channel.id in exempt_channel_ids:
            return True
        if any(r.id in exempt_role_ids for r in message.author.roles):
            return True
        return False

    async def is_antinuke_whitelisted(self, guild_id: int, user_id: int) -> bool:
        """Check if user is whitelisted in the antinuke system (db/anti.db)."""
        try:
            async with aiosqlite.connect("db/anti.db") as db:
                async with db.execute(
                    "SELECT user_id FROM whitelisted_users WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id)
                ) as cur:
                    row = await cur.fetchone()
                    return row is not None
        except Exception:
            return False

    async def increment_warn(self, guild_id: int, user_id: int) -> int:
        await db_exec(
            "INSERT INTO automod_warn_count (guild_id, user_id, count) VALUES (?, ?, 1) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET count = count + 1",
            (guild_id, user_id)
        )
        row = await db_fetch("SELECT count FROM automod_warn_count WHERE guild_id = ? AND user_id = ?", (guild_id, user_id), one=True)
        return row[0] if row else 1

    async def apply_punishment(self, message: discord.Message, event: str, reason: str):
        guild      = message.guild
        member     = message.author
        guild_id   = guild.id
        punishment = await self.get_punishment(guild_id, event)

        dm_sent     = False
        action_text = ""

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        try:
            dm_embed = discord.Embed(
                title=f"{E.WARNING} AutoMod Action — {guild.name}",
                description=(
                    f"{E.REASON} **Reason:** {reason}\n"
                    f"{E.SETTINGS} **Module:** `{event}`\n"
                    f"{E.TIMER} **Punishment:** `{punishment}`\n\n"
                    f"Please follow the server rules to avoid further action."
                ),
                color=0xFF6B6B
            )
            dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else self.bot.user.display_avatar.url)
            await member.send(view=_embed_to_layout(dm_embed))
            dm_sent = True
        except Exception:
            pass

        try:
            if punishment == "Mute":
                duration = {
                    "Anti spam": 12, "Anti caps": 1, "Anti link": 7,
                    "Anti invites": 12, "Anti emoji spam": 1,
                    "Anti mass mention": 3, "Anti bad words": 5,
                    "Anti flood": 5, "Anti zalgo": 3,
                }.get(event, 5)
                from datetime import timedelta
                await member.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(minutes=duration),
                    reason=f"AutoMod [{event}]: {reason}"
                )
                action_text = f"Muted for {duration} minutes"

            elif punishment == "Kick":
                await member.kick(reason=f"AutoMod [{event}]: {reason}")
                action_text = "Kicked"

            elif punishment == "Ban":
                await guild.ban(member, reason=f"AutoMod [{event}]: {reason}", delete_message_days=1)
                action_text = "Banned"

            elif punishment == "Delete":
                action_text = "Message Deleted"

        except (discord.Forbidden, discord.HTTPException):
            action_text = "Action Failed (missing permissions)"

        warn_count     = await self.increment_warn(guild_id, member.id)
        log_channel_id = await self.get_log_channel(guild_id)

        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title=f"{E.SHIELD} AutoMod Log",
                    color=0xFF6B6B,
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(name=f"{E.USER} User",       value=f"{member.mention} (`{member.id}`)", inline=True)
                log_embed.add_field(name=f"{E.SETTINGS} Module", value=f"`{event}`",                        inline=True)
                log_embed.add_field(name=f"{E.REASON} Reason",   value=reason,                              inline=False)
                log_embed.add_field(name=f"{E.TIMER} Action",    value=action_text,                         inline=True)
                log_embed.add_field(name=f"{E.WARNING} Warns",   value=f"`{warn_count}` total",             inline=True)
                log_embed.add_field(name=f"{E.MAIL} DM Sent",    value=f"`{'Yes' if dm_sent else 'No'}`",   inline=True)
                log_embed.add_field(name=f"{E.CHANNEL} Channel", value=message.channel.mention,             inline=True)
                if member.avatar:
                    log_embed.set_thumbnail(url=member.avatar.url)
                log_embed.set_footer(text=f"CupidX AutoMod  •  {guild.name}")
                try:
                    await log_channel.send(view=_embed_to_layout(log_embed))
                except Exception:
                    pass

    # ── MESSAGE LISTENER ─────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return

        guild_id = message.guild.id

        if not await self.is_automod_enabled(guild_id):
            return
        if message.author.guild_permissions.manage_messages:
            return
        if await self.is_exempt(message):
            return
        if await self.is_antinuke_whitelisted(guild_id, message.author.id):
            return

        content = message.content

        if await self.is_module_enabled(guild_id, "Anti spam"):
            now = time.time()
            uid = message.author.id
            _spam_tracker[guild_id][uid] = [
                t for t in _spam_tracker[guild_id][uid] if now - t < 5
            ]
            _spam_tracker[guild_id][uid].append(now)
            if len(_spam_tracker[guild_id][uid]) > 5:
                _spam_tracker[guild_id][uid].clear()
                await self.apply_punishment(message, "Anti spam", "Sending messages too rapidly (spam detected)")
                return

        if await self.is_module_enabled(guild_id, "Anti flood"):
            uid    = message.author.id
            recent = _spam_tracker[guild_id].get(f"flood_{uid}", [])
            recent = [(t, c) for t, c in recent if time.time() - t < 10]
            if sum(1 for _, c in recent if c == content) >= 3:
                _spam_tracker[guild_id][f"flood_{uid}"] = []
                await self.apply_punishment(message, "Anti flood", "Sending identical messages repeatedly")
                return
            recent.append((time.time(), content))
            _spam_tracker[guild_id][f"flood_{uid}"] = recent

        if await self.is_module_enabled(guild_id, "Anti zalgo"):
            zalgo_chars = sum(1 for c in content if '\u0300' <= c <= '\u036f' or c == '\u0489')
            if zalgo_chars > 5:
                await self.apply_punishment(message, "Anti zalgo", "Message contains zalgo/corrupted text")
                return

        if await self.is_module_enabled(guild_id, "Anti caps"):
            letters = [c for c in content if c.isalpha()]
            if len(content) >= 45 and len(letters) > 0:
                caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if caps_ratio > 0.70:
                    await self.apply_punishment(message, "Anti caps", f"Message is {int(caps_ratio*100)}% uppercase caps")
                    return

        if await self.is_module_enabled(guild_id, "Anti link"):
            import re
            url_pattern = r"(https?://[^\s]+|discord\.gg/[^\s]+)"
            urls        = re.findall(url_pattern, content, re.IGNORECASE)
            bypassed    = ["spotify.com", "tenor.com", "giphy.com", "discord.gg", "discordapp.com"]
            bad_urls    = [u for u in urls if not any(bp in u.lower() for bp in bypassed)]
            if bad_urls:
                await self.apply_punishment(message, "Anti link", f"Sent a link: `{bad_urls[0][:60]}`")
                return

        if await self.is_module_enabled(guild_id, "Anti invites"):
            import re
            inv_pattern = r"discord(?:\.gg|app\.com\/invite|\.com\/invite)\/([a-zA-Z0-9\-]+)"
            invites     = re.findall(inv_pattern, content, re.IGNORECASE)
            if invites:
                own_invites = [inv.code for inv in await message.guild.invites()]
                foreign     = [i for i in invites if i not in own_invites]
                if foreign:
                    await self.apply_punishment(message, "Anti invites", "Sent a foreign Discord invite")
                    return

        if await self.is_module_enabled(guild_id, "Anti emoji spam"):
            import re
            unicode_emojis = re.findall(
                r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF'
                r'\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF'
                r'\u2600-\u26FF\u2700-\u27BF]', content
            )
            custom_emojis = re.findall(r'<a?:\w+:\d+>', content)
            total_emojis  = len(unicode_emojis) + len(custom_emojis)
            if total_emojis > 5:
                await self.apply_punishment(message, "Anti emoji spam", f"Sent {total_emojis} emojis in one message")
                return

        if await self.is_module_enabled(guild_id, "Anti mass mention"):
            mentions = len(set(message.mentions)) + len(set(message.role_mentions))
            if mentions > 4:
                await self.apply_punishment(message, "Anti mass mention", f"Mentioned {mentions} users/roles at once")
                return

        if await self.is_module_enabled(guild_id, "Anti bad words"):
            lower     = content.lower()
            triggered = next((w for w in self.bad_words if w in lower), None)
            if triggered:
                await self.apply_punishment(message, "Anti bad words", "Used a prohibited word")
                return

    # ── GUILD REMOVE ─────────────────────────────
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        gid = guild.id
        for table in ["automod", "automod_punishments", "automod_ignored", "automod_logging", "automod_warn_count"]:
            await db_exec(f"DELETE FROM {table} WHERE guild_id = ?", (gid,))

    # ==============================================
    #         HYBRID GROUP — AUTOMOD
    # ==============================================

    @commands.hybrid_group(name="automod", invoke_without_command=True, fallback="help")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.guild_only()
    async def automod(self, ctx):
        """AutoMod command center."""
        if ctx.subcommand_passed is not None:
            return
        p = ctx.prefix
        embed = discord.Embed(
            title="AutoMod — Command Center",
            description=(
                f"Protect **{ctx.guild.name}** with CupidX's advanced automoderation system.\n"
                f"Use the commands below to configure everything.\n\u200b"
            ),
            color=0x5865F2
        )
        embed.set_author(name="CupidX AutoMod", icon_url=self.bot.user.display_avatar.url)
        embed.add_field(
            name="Setup & Control",
            value=(
                f"`{p}automod enable` — Enable & select modules\n"
                f"`{p}automod disable` — Fully disable automod\n"
                f"`{p}automod config` — View current settings\n"
                f"`{p}automod punishment` — Change punishments"
            ),
            inline=False
        )
        embed.add_field(
            name="Whitelist",
            value=(
                f"`{p}automod ignore channel #ch` — Exempt a channel\n"
                f"`{p}automod ignore role @role` — Exempt a role\n"
                f"`{p}automod ignore show` — View whitelist\n"
                f"`{p}automod ignore reset` — Clear whitelist"
            ),
            inline=False
        )
        embed.add_field(
            name="Logging",
            value=f"`{p}automod logging #channel` — Set log channel",
            inline=False
        )
        embed.add_field(
            name="Modules Available",
            value=(
                "Anti Spam  •  Anti Caps  •  Anti Link\n"
                "Anti Invites  •  Anti Mass Mention\n"
                "Anti Emoji Spam  •  Anti NSFW Links\n"
                "Anti Bad Words  •  Anti Flood  •  Anti Zalgo"
            ),
            inline=False
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="cupidx AutoMod System", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(view=_embed_to_layout(embed))
        ctx.command.reset_cooldown(ctx)

    # ── ENABLE ────────────────────────────────────
    @automod.command(name="enable", help="Enable automod modules.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def enable(self, ctx):
        """Enable automod and select modules."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))

        if await self.is_automod_enabled(guild_id):
            embed = discord.Embed(
                title=f"{E.WARNING} Already Enabled",
                description=(
                    f"AutoMod is already active on **{ctx.guild.name}**.\n\n"
                    f"**Status:** {E.ENABLED} Enabled\n"
                    f"**Disable:** `{ctx.prefix}automod disable`\n"
                    f"**View Settings:** `{ctx.prefix}automod config`"
                ),
                color=0xFEE75C
            )
            embed.set_footer(**footer(ctx))
            return await ctx.send(view=_embed_to_layout(embed))

        all_events = [
            "Anti spam", "Anti caps", "Anti link", "Anti invites",
            "Anti mass mention", "Anti emoji spam", "Anti NSFW link",
            "Anti bad words", "Anti flood", "Anti zalgo",
        ]

        # ENABLED/DISABLED emoji on LEFT, module name after — no normal emojis
        status_lines = "\n".join(
            f"{E.DISABLED} **{ev}** — Inactive"
            for ev in all_events
        )
        embed = discord.Embed(
            title=f"{E.SETTINGS} AutoMod Setup — {ctx.guild.name}",
            description=(
                "Select the modules you want to enable from the dropdown,\n"
                "or click **Enable All** to activate everything at once.\n\u200b\n"
                + status_lines
            ),
            color=0x5865F2
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(**footer(ctx))

        select_menu = discord.ui.Select(
            placeholder="Choose modules to enable...",
            min_values=1,
            max_values=len(all_events),
            options=[
                discord.SelectOption(label=ev, value=ev)
                for ev in all_events
            ]
        )

        async def select_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message(
                    view=_text_to_layout(f"{E.CROSS} Not your setup."), ephemeral=True
                )
            await self._do_enable(ctx, guild_id, select_menu.values, interaction)

        select_menu.callback = select_cb

        btn_all = discord.ui.Button(label="Enable All Modules", style=discord.ButtonStyle.secondary)

        async def all_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message(
                    view=_text_to_layout(f"{E.CROSS} Not your setup."), ephemeral=True
                )
            await self._do_enable(ctx, guild_id, all_events, interaction)

        btn_all.callback = all_cb

        btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def cancel_cb(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message(
                    view=_text_to_layout(f"{E.CROSS} Not yours."), ephemeral=True
                )
            select_menu.disabled = True
            btn_all.disabled     = True
            btn_cancel.disabled  = True
            cancel_embed = discord.Embed(
                title=f"{E.CROSS} Setup Cancelled",
                description="AutoMod setup was cancelled. No changes were made."
            )
            await interaction.response.edit_message(
                view=_embed_to_layout(
                    cancel_embed,
                    controls=[
                        discord.ui.ActionRow(select_menu),
                        discord.ui.ActionRow(btn_all, btn_cancel),
                    ]
                )
            )

        btn_cancel.callback = cancel_cb

        layout = _embed_to_layout(
            embed,
            controls=[
                discord.ui.ActionRow(select_menu),
                discord.ui.ActionRow(btn_all, btn_cancel),
            ],
            timeout=60
        )
        await ctx.send(view=layout)

    async def _do_enable(self, ctx, guild_id, selected_events, interaction):
        """Internal: enable selected modules with loading animation."""
        import asyncio

        STAGES = [
            (5,   "Waking up AutoMod engine..."),
            (12,  "Scanning server structure..."),
            (20,  "Verifying bot permissions..."),
            (30,  "Loading selected modules..."),
            (42,  "Binding spam tracker..."),
            (54,  "Configuring punishment rules..."),
            (65,  "Setting up Anti NSFW filter..."),
            (75,  "Linking audit log hooks..."),
            (85,  "Encrypting module config..."),
            (93,  "Syncing with database..."),
            (100, "All systems online! AutoMod is live."),
        ]

        def build_bar(percent: int, length: int = 18) -> str:
            filled = int(length * percent / 100)
            bar    = "█" * filled + "░" * (length - filled)
            return f"`[{bar}]` **{percent}%**"

        def loading_view(percent: int, stage: str) -> discord.ui.LayoutView:
            embed = discord.Embed(
                title="AutoMod Setup — Loading",
                description=(
                    f"{build_bar(percent)}\n\n"
                    f"**Stage:** {stage}\n"
                    f"{'─' * 30}\n"
                    f"*Please wait, do not run commands...*"
                ),
                color=0x5865F2
            )
            embed.set_footer(text="CupidX AutoMod Setup Engine")
            return _embed_to_layout(embed)

        await interaction.response.edit_message(view=loading_view(0, "Initializing..."))
        await asyncio.sleep(0.4)

        for percent, stage in STAGES:
            try:
                await interaction.edit_original_response(view=loading_view(percent, stage))
            except Exception:
                pass
            await asyncio.sleep(0.5)

        await db_exec("INSERT OR REPLACE INTO automod (guild_id, enabled) VALUES (?, 1)", (guild_id,))
        for ev in selected_events:
            await db_exec(
                "INSERT OR REPLACE INTO automod_punishments (guild_id, event, punishment) VALUES (?, ?, ?)",
                (guild_id, ev, self.default_punishment)
            )

        if "Anti NSFW link" in selected_events:
            exempt_roles, exempt_channels = await self.get_exempt_roles_channels(guild_id)
            nsfw_keywords = [
                "porn", "xxx", "adult", "nsfw", "xnxx", "onlyfans", "brazzers",
                "xhamster", "xvideos", "pornhub", "redtube", "livejasmin",
                "youporn", "tube8", "pornhat", "swxvid", "ixxx"
            ]
            try:
                await interaction.guild.create_automod_rule(
                    name="Anti NSFW Links",
                    event_type=discord.AutoModRuleEventType.message_send,
                    trigger=discord.AutoModTrigger(
                        type=discord.AutoModRuleTriggerType.keyword,
                        keyword_filter=nsfw_keywords,
                    ),
                    actions=[discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)],
                    enabled=True,
                    exempt_roles=exempt_roles,
                    exempt_channels=exempt_channels,
                    reason="CupidX AutoMod — Anti NSFW setup"
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        all_events_list = [
            "Anti spam", "Anti caps", "Anti link", "Anti invites",
            "Anti mass mention", "Anti emoji spam", "Anti NSFW link",
            "Anti bad words", "Anti flood", "Anti zalgo",
        ]

        # ENABLED/DISABLED emoji on LEFT side — no normal emojis
        status_lines = "\n".join(
            (f"{E.ENABLED} **{ev}** — Active" if ev in selected_events else f"{E.DISABLED} **{ev}** — Off")
            for ev in all_events_list
        )
        embed = discord.Embed(
            title=f"{E.TICK1} AutoMod Enabled — {ctx.guild.name}",
            description=(
                f"**{len(selected_events)} module(s)** are now active.\n\u200b\n"
                + status_lines
            ),
            color=0x57F287
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)
        embed.set_footer(**footer(ctx))

        btn_log = discord.ui.Button(label="Enable Logging Channel", style=discord.ButtonStyle.secondary)

        async def log_cb(interaction2: discord.Interaction):
            if interaction2.user != ctx.author:
                return await interaction2.response.send_message(
                    view=_text_to_layout(f"{E.CROSS} Not yours."), ephemeral=True
                )
            if not interaction2.guild.me.guild_permissions.manage_channels:
                return await interaction2.response.send_message(
                    view=_text_to_layout("I need `Manage Channels` permission."), ephemeral=True
                )
            for ch in interaction2.guild.channels:
                if ch.name == "cupidx-automod":
                    return await interaction2.response.send_message(
                        view=_text_to_layout(f"Log channel already exists: {ch.mention}"), ephemeral=True
                    )
            overwrites = {
                interaction2.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction2.guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }
            try:
                log_ch = await interaction2.guild.create_text_channel("cupidx-automod", overwrites=overwrites)
                await db_exec(
                    "INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)",
                    (guild_id, log_ch.id)
                )
                await interaction2.response.send_message(
                    view=_text_to_layout(f"{E.TICK1} Log channel created: {log_ch.mention}"), ephemeral=True
                )
            except discord.HTTPException as err:
                await interaction2.response.send_message(
                    view=_text_to_layout(f"Failed: {err}"), ephemeral=True
                )

        btn_log.callback = log_cb

        rules_select = discord.ui.Select(
            placeholder="View a module's rules...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=ev, value=ev)
                for ev in selected_events
            ]
        )

        RULES_INFO = {
            "Anti NSFW link":    "**Anti NSFW Link**\nBlocks messages containing NSFW/adult site links.\n**Punishment:** Block message *(fixed, cannot be changed)*",
            "Anti caps":         "**Anti Caps**\nTriggers when >70% of a message (min 45 chars) is uppercase.\n**Default punishment:** Mute 1 min",
            "Anti link":         "**Anti Link**\nBlocks all URLs. Spotify, GIFs, and Discord invite links are bypassed.\n**Default punishment:** Mute 7 min",
            "Anti invites":      "**Anti Invites**\nBlocks foreign Discord server invites. Your own server's invites are bypassed.\n**Default punishment:** Mute 12 min",
            "Anti emoji spam":   "**Anti Emoji Spam**\nTriggers when a message contains more than 5 emojis (unicode + custom).\n**Default punishment:** Mute 1 min",
            "Anti mass mention": "**Anti Mass Mention**\nTriggers when more than 4 users/roles are mentioned in one message.\n**Default punishment:** Mute 3 min",
            "Anti spam":         "**Anti Spam**\nTriggers when a user sends more than 5 messages within 5 seconds.\n**Default punishment:** Mute 12 min",
            "Anti bad words":    "**Anti Bad Words**\nBlocks messages containing configured prohibited words/phrases.\n**Default punishment:** Delete message",
            "Anti flood":        "**Anti Flood**\nTriggers when the same message is sent 3+ times within 10 seconds.\n**Default punishment:** Mute 5 min",
            "Anti zalgo":        "**Anti Zalgo**\nBlocks messages containing zalgo/corrupted unicode text (>5 combining chars).\n**Default punishment:** Delete message",
        }

        async def rules_select_cb(interaction3: discord.Interaction):
            chosen     = rules_select.values[0]
            info_embed = discord.Embed(
                title=f"{E.SETTINGS} Module Info — {chosen}",
                description=RULES_INFO.get(chosen, "No info available."),
                color=0x5865F2
            )
            info_embed.set_footer(text="Change punishments anytime via: automod punishment")
            await interaction3.response.send_message(view=_embed_to_layout(info_embed), ephemeral=True)

        rules_select.callback = rules_select_cb

        await interaction.edit_original_response(
            view=_embed_to_layout(
                embed,
                controls=[
                    discord.ui.ActionRow(rules_select),
                    discord.ui.ActionRow(btn_log),
                ],
                timeout=90
            )
        )

    # ── DISABLE ───────────────────────────────────
    @automod.command(name="disable", help="Disable automod completely.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        """Fully disable automod."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        view = ConfirmDisable(ctx.author)
        msg  = await ctx.send(view=view)
        await view.wait()

        if view.value is None:
            timeout_embed = discord.Embed(
                title=f"{E.WARNING} Timed Out",
                description="No response received. AutoMod disable cancelled.",
                color=0xFEE75C
            )
            timeout_embed.set_footer(text="This action cannot be undone.")
            await msg.edit(view=_embed_to_layout(timeout_embed))

        elif view.value:
            for table in ["automod", "automod_punishments", "automod_ignored", "automod_logging"]:
                await db_exec(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))

            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        await rule.delete(reason="AutoMod disabled via CupidX")
                        break
            except (discord.Forbidden, discord.HTTPException):
                pass

            done_embed = discord.Embed(
                title=f"{E.TICK1} AutoMod Disabled",
                description=(
                    f"AutoMod has been fully disabled for **{ctx.guild.name}**.\n\n"
                    f"**Status:** {E.DISABLED} Disabled\n"
                    f"**Re-enable:** `{ctx.prefix}automod enable`"
                ),
                color=0x57F287
            )
            done_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            done_embed.set_footer(**footer(ctx))
            await msg.edit(view=_embed_to_layout(done_embed))

        else:
            cancel_embed = discord.Embed(
                title=f"{E.CROSS} Cancelled",
                description="AutoMod disable was cancelled. Everything remains active.",
                color=0xED4245
            )
            cancel_embed.set_footer(**footer(ctx))
            await msg.edit(view=_embed_to_layout(cancel_embed))

    # ── PUNISHMENT ───────────────────────────────────
    @automod.command(name="punishment", aliases=["punish"], help="Configure punishments for automod modules.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def punishment(self, ctx):
        """Change punishments per module."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        rows = await db_fetch(
            "SELECT event, punishment FROM automod_punishments WHERE guild_id = ? AND event != 'Anti NSFW link'",
            (guild_id,)
        )
        if not rows:
            return await ctx.send(view=_text_to_layout(
                f"{E.WARNING} No modules are enabled. Run `{ctx.prefix}automod enable` first."
            ))

        current_lines = "\n".join(f"{E.TICK} **{ev}** → `{pun or 'Mute'}`" for ev, pun in rows)
        embed = discord.Embed(
            title=f"{E.SETTINGS} Punishment Settings — {ctx.guild.name}",
            description=(
                "**Step 1:** Select which module(s) to update.\n"
                "**Step 2:** Pick the punishment.\n\u200b\n"
                + current_lines
            ),
            color=0xFEE75C
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Mute is recommended to prevent raids without banning legitimate users.")

        events = [ev for ev, _ in rows]
        view   = PunishmentView(ctx.author, guild_id, events, self)
        await ctx.send(view=view)

    # ── CONFIG ────────────────────────────────────
    @automod.command(name="config", aliases=["settings", "show", "view"], help="View automod settings.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        """View current automod configuration."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        rows          = await db_fetch(
            "SELECT event, punishment FROM automod_punishments WHERE guild_id = ? AND event != 'Anti NSFW link'",
            (guild_id,)
        )
        log_row       = await db_fetch("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild_id,), one=True)
        nsfw_on       = await self.is_anti_nsfw_enabled(guild_id)
        exempt_roles, exempt_channels = await self.get_exempt_roles_channels(guild_id)

        modules_text = "\n".join(f"{E.TICK} **{ev}** → `{pun or 'Mute'}`" for ev, pun in rows)
        if nsfw_on:
            modules_text += f"\n{E.TICK} **Anti NSFW link** → `Block Message`"

        log_val = "Not set"
        if log_row and log_row[0]:
            ch      = ctx.guild.get_channel(log_row[0])
            log_val = ch.mention if ch else "Channel deleted"

        role_text = ", ".join(
            (ctx.guild.get_role(r.id).mention if ctx.guild.get_role(r.id) else f"Deleted ({r.id})")
            for r in exempt_roles
        ) or "None"
        ch_text = ", ".join(
            (ctx.guild.get_channel(c.id).mention if ctx.guild.get_channel(c.id) else f"Deleted ({c.id})")
            for c in exempt_channels
        ) or "None"

        embed = discord.Embed(
            title=f"{E.SETTINGS} AutoMod Config — {ctx.guild.name}",
            description=(
                f"**Status:** {E.ENABLED} Enabled\n\u200b\n"
                f"{E.SHIELD} **Active Modules**\n{modules_text or 'None'}\n\u200b\n"
                f"{E.LOG} **Log Channel:** {log_val}\n"
                f"{E.ROLE} **Exempt Roles:** {role_text}\n"
                f"{E.CHANNEL} **Exempt Channels:** {ch_text}"
            ),
            color=0x5865F2
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Use '{ctx.prefix}automod punishment' to change punishments.")
        await ctx.send(view=_embed_to_layout(embed))

    # ── LOGGING ───────────────────────────────────
    @automod.command(name="logging", help="Set the logging channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def logging(self, ctx, channel: discord.TextChannel):
        """Set automod log channel."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        await db_exec(
            "INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)",
            (guild_id, channel.id)
        )
        embed = discord.Embed(
            title=f"{E.TICK1} Log Channel Set",
            description=f"AutoMod logs will now be sent to {channel.mention}.",
            color=0x57F287
        )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    # ==============================================
    #       SUBGROUP — AUTOMOD IGNORE (WHITELIST)
    # ==============================================

    @automod.group(name="ignore", aliases=["exempt", "whitelist", "wl"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.guild_only()
    async def automod_ignore(self, ctx):
        """Whitelist channels or roles from automod."""
        if ctx.subcommand_passed is not None:
            return
        p = ctx.prefix
        embed = discord.Embed(
            title="AutoMod Ignore — Whitelist",
            description=(
                "Exempt channels and roles from all automod checks.\n\u200b\n"
                f"`{p}automod ignore channel #ch` — Exempt a channel\n"
                f"`{p}automod ignore role @role` — Exempt a role\n"
                f"`{p}automod ignore show` — View whitelist\n"
                f"`{p}automod ignore reset` — Reset whitelist"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="CupidX AutoMod", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(view=_embed_to_layout(embed))
        ctx.command.reset_cooldown(ctx)

    @automod_ignore.command(name="channel", help="Whitelist a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_channel(self, ctx, channel: discord.TextChannel):
        """Exempt a channel from automod."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?",
                (guild_id, channel.id)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title=f"{E.WARNING} Already Whitelisted",
                    description=(
                        f"{channel.mention} is already exempted.\n"
                        f"Use `{ctx.prefix}automod unignore channel` to remove it."
                    ),
                    color=0xFEE75C
                )
                embed.set_footer(**footer(ctx))
                return await ctx.send(view=_embed_to_layout(embed))

            cnt_cur = await db.execute(
                "SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,)
            )
            if (await cnt_cur.fetchone())[0] >= 10:
                return await ctx.send(view=_text_to_layout(
                    f"{E.CROSS} You can only whitelist up to **10 channels**."
                ))

            await db.execute(
                "INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'channel', ?)",
                (guild_id, channel.id)
            )
            await db.commit()

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        exc = list(rule.exempt_channels) + [channel]
                        await rule.edit(exempt_channels=exc, reason="Channel whitelisted via CupidX automod")
                        break
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            title=f"{E.TICK1} Channel Whitelisted",
            description=f"{channel.mention} is now exempt from all automod checks.",
            color=0x57F287
        )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    @automod_ignore.command(name="role", help="Whitelist a role.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_role(self, ctx, role: discord.Role):
        """Exempt a role from automod."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id = ?",
                (guild_id, role.id)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title=f"{E.WARNING} Already Whitelisted",
                    description=(
                        f"{role.mention} is already exempted.\n"
                        f"Use `{ctx.prefix}automod unignore role` to remove it."
                    ),
                    color=0xFEE75C
                )
                embed.set_footer(**footer(ctx))
                return await ctx.send(view=_embed_to_layout(embed))

            cnt_cur = await db.execute(
                "SELECT COUNT(*) FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (guild_id,)
            )
            if (await cnt_cur.fetchone())[0] >= 10:
                return await ctx.send(view=_text_to_layout(
                    f"{E.CROSS} You can only whitelist up to **10 roles**."
                ))

            await db.execute(
                "INSERT OR REPLACE INTO automod_ignored (guild_id, type, id) VALUES (?, 'role', ?)",
                (guild_id, role.id)
            )
            await db.commit()

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        exc = list(rule.exempt_roles) + [role]
                        await rule.edit(exempt_roles=exc, reason="Role whitelisted via CupidX automod")
                        break
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            title=f"{E.TICK1} Role Whitelisted",
            description=f"{role.mention} is now exempt from all automod checks.",
            color=0x57F287
        )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    @automod_ignore.command(name="show", aliases=["view", "list", "config"], help="Show all whitelisted entities.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_show(self, ctx):
        """Show whitelist."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        rows = await db_fetch("SELECT type, id FROM automod_ignored WHERE guild_id = ?", (guild_id,))
        if not rows:
            embed = discord.Embed(
                title=f"{E.SHIELD} Whitelist — {ctx.guild.name}",
                description="No channels or roles are currently whitelisted.",
                color=0x5865F2
            )
            embed.set_footer(**footer(ctx))
            return await ctx.send(view=_embed_to_layout(embed))

        channels_list, roles_list = [], []
        for typ, eid in rows:
            if typ == "channel":
                ch = ctx.guild.get_channel(eid)
                channels_list.append(ch.mention if ch else f"Deleted Channel (`{eid}`)")
            elif typ == "role":
                ro = ctx.guild.get_role(eid)
                roles_list.append(ro.mention if ro else f"Deleted Role (`{eid}`)")

        embed = discord.Embed(
            title=f"{E.SHIELD} Whitelist — {ctx.guild.name}",
            description=(
                f"{E.CHANNEL} **Exempt Channels ({len(channels_list)}/10)**\n"
                + ("\n".join(channels_list) or "None")
                + f"\n\u200b\n{E.ROLE} **Exempt Roles ({len(roles_list)}/10)**\n"
                + ("\n".join(roles_list) or "None")
            ),
            color=0x5865F2
        )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    @automod_ignore.command(name="reset", help="Reset the full whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_reset(self, ctx):
        """Clear entire whitelist."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        await db_exec("DELETE FROM automod_ignored WHERE guild_id = ?", (guild_id,))

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        await rule.edit(exempt_channels=[], exempt_roles=[], reason="Whitelist reset via CupidX automod")
                        break
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            title=f"{E.TICK1} Whitelist Reset",
            description="All whitelisted channels and roles have been cleared.",
            color=0x57F287
        )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    # ==============================================
    #      SUBGROUP — AUTOMOD UNIGNORE
    # ==============================================

    @automod.group(name="unignore", aliases=["unwhitelist", "unwl"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def automod_unignore(self, ctx):
        """Remove channels or roles from whitelist."""
        if ctx.subcommand_passed is not None:
            return
        p = ctx.prefix
        embed = discord.Embed(
            title="AutoMod Unignore",
            description=(
                "Remove channels or roles from the whitelist.\n\u200b\n"
                f"`{p}automod unignore channel #ch` — Remove channel\n"
                f"`{p}automod unignore role @role` — Remove role"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="CupidX AutoMod", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(view=_embed_to_layout(embed))
        ctx.command.reset_cooldown(ctx)

    @automod_unignore.command(name="channel", help="Remove a channel from whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unignore_channel(self, ctx, channel: discord.TextChannel):
        """Remove channel from whitelist."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        exc = [c for c in rule.exempt_channels if c.id != channel.id]
                        await rule.edit(exempt_channels=exc, reason="Channel removed from NSFW whitelist")
                        break
            except discord.HTTPException:
                pass

        async with aiosqlite.connect(DB) as db:
            result = await db.execute(
                "DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?",
                (guild_id, channel.id)
            )
            await db.commit()

        if result.rowcount > 0:
            embed = discord.Embed(
                title=f"{E.TICK1} Channel Removed from Whitelist",
                description=f"{channel.mention} will now be checked by AutoMod.",
                color=0x57F287
            )
        else:
            embed = discord.Embed(
                title=f"{E.CROSS} Not Found",
                description=f"{channel.mention} was not in the whitelist.",
                color=0xED4245
            )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))

    @automod_unignore.command(name="role", help="Remove a role from whitelist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unignore_role(self, ctx, role: discord.Role):
        """Remove role from whitelist."""
        guild_id = ctx.guild.id
        if not has_access(ctx):
            return await ctx.send(view=_embed_to_layout(access_denied_embed(ctx)))
        if not await self.is_automod_enabled(guild_id):
            return await ctx.send(view=_embed_to_layout(not_enabled_embed(ctx, self.bot)))

        if await self.is_anti_nsfw_enabled(guild_id):
            try:
                for rule in await ctx.guild.fetch_automod_rules():
                    if rule.name == "Anti NSFW Links":
                        exc = [r for r in rule.exempt_roles if r.id != role.id]
                        await rule.edit(exempt_roles=exc, reason="Role removed from NSFW whitelist")
                        break
            except discord.HTTPException:
                pass

        async with aiosqlite.connect(DB) as db:
            result = await db.execute(
                "DELETE FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id = ?",
                (guild_id, role.id)
            )
            await db.commit()

        if result.rowcount > 0:
            embed = discord.Embed(
                title=f"{E.TICK1} Role Removed from Whitelist",
                description=f"{role.mention} will now be checked by AutoMod.",
                color=0x57F287
            )
        else:
            embed = discord.Embed(
                title=f"{E.CROSS} Not Found",
                description=f"{role.mention} was not in the whitelist.",
                color=0xED4245
            )
        embed.set_footer(**footer(ctx))
        await ctx.send(view=_embed_to_layout(embed))


async def setup(bot):
    await bot.add_cog(Automod(bot))
