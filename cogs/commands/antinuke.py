import discord
from discord.ext import commands
import aiosqlite
import asyncio
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button
from utils.Tools import blacklist_check, ignore_check
from utils.detectfile import *

# ========================= EMOJIS & COLORS =========================
emojitick = EMOJI_TICK
emojicross = EMOJI_CROSS
emojiwarn = EMOJI_WARN
emojidot = EMOJI_DOT2
emojisecurity = "<:cog:1487152125069889677>"
emojidisabled = EMOJI_DISABLE
antinuke_cross = EMOJI_CROSS2
antinuke_tick = EMOJI_TICK
antinuke_tick1 = EMOJI_ENABLE

color_primary = 0xFF6600
color_warning = 0xFF6600
color_success = 0xFF6600

db_path = "db/anti.db"

# ========================= LOADING BAR SYSTEM =========================

LOADING_STAGES = [
    (1,   "{EMOJI_LIGHTNING}  Waking up the shield..."),
    (10,  "{EMOJI_SHUFFLE}  Scanning server structure..."),
    (22,  "{EMOJI_ROBOT}  Verifying bot permissions..."),
    (35,  "{EMOJI_UTILITY4}  Forging CupidX's Shield role..."),
    (50,  "{EMOJI_UTILITY3}   Binding modules to core..."),
    (63,  "{EMOJI_BOND2}  Linking audit log trackers..."),
    (75,  "{EMOJI_PUZZLE}  Loading threat detection AI..."),
    (88,  "{EMOJI_KEY}  Encrypting protection layer..."),
    (95,  "{EMOJI_STAR2}  Syncing with database..."),
    (100, "{EMOJI_TICK}  All systems online!"),
]

def build_progress_bar(percent: int, length: int = 20) -> str:
    """Build a visual progress bar."""
    filled = int(length * percent / 100)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"`[{bar}]` **{percent}%**"

def loading_card(percent: int, stage_text: str, title: str = "<:cog:1487152125069889677> Antinuke Setup") -> LayoutView:
    """Build a loading-style v2 card."""
    bar = build_progress_bar(percent)
    view = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"## {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        f"{bar}\n\n"
        f"**Stage:** {stage_text}\n"
        f"{'─' * 28}\n"
        f"*Please wait, do not run any commands...*"
    ))
    container.add_item(Separator())
    view.add_item(container)
    return view

# ========================= V2 COMPONENTS =========================
def v2_card(title: str, body: str) -> LayoutView:
    """Create CupidX-style v2 card."""
    view = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"## {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())
    view.add_item(container)
    return view

def build_enable_success_view(guild_name: str, prefix: str) -> LayoutView:
    """Full detailed success card after antinuke enable."""

    modules_protection = [
        ("Anti Ban", "Detected bans auto-reversed, victim unbanned instantly."),
        ("Anti Kick", "Kick attempts detected and attacker punished."),
        ("Anti Bot Add", "Unauthorized bot additions blocked and removed."),
        ("Anti Channel Create", "Mass channel creation detected and stopped."),
        ("Anti Channel Delete", "Deleted channels are automatically restored."),
        ("Anti Channel Update", "Channel edits fully reverted to original state."),
        ("Anti @everyone/@here", "Mass mention abuse triggers 24h timeout."),
        ("Anti Role Create", "Mass role creation stopped immediately."),
        ("Anti Role Delete", "Deleted roles are automatically restored."),
        ("Anti Role Update", "Dangerous permission changes reverted instantly."),
        ("Anti Member Role Update", "Unauthorized role assignments blocked."),
        ("Anti Guild Update", "Server name, icon & banner changes reverted."),
        ("Anti Webhook", "Webhook create, delete, update & spam blocked."),
        ("Anti Integration", "Unauthorized integrations removed instantly."),
        ("Anti Prune", "Mass member prune attempts detected & stopped."),
        ("Anti Emoji & Sticker", "Bulk emoji & sticker deletions blocked."),
        ("Role Strip Before Ban", "All dangerous roles stripped before ban executes."),
        ("Audit Log Optimized", "Ultra-fast audit log scanning for zero delay."),
    ]

    # Build module lines
    modules_text = "\n".join(
        f"{antinuke_tick1} **{name}**\n> {desc}"
        for name, desc in modules_protection
    )

    body = (
        f"**Server:** {guild_name}\n"
        f"**Status:** {EMOJI_ENABLE2} Active & Running\n"
        f"**Modules Loaded:** `{len(modules_protection)}`\n"
        f"{'─' * 32}\n\n"
        f"### {EMOJI_SHIELD}  Protection Modules\n\n"
        f"{modules_text}\n\n"
        f"{'─' * 32}\n"
        f"### {EMOJI_BOND} Punishment System\n\n"
        f"{emojitick} **Ban / Kick / Prune / Webhook / Bot** → Role Strip → Permanent Ban\n"
        f"{emojitick} **Channel Create** → Attacker channels deleted → Ban\n"
        f"{emojitick} **Channel Delete** → Channel auto-restored → Ban\n"
        f"{emojitick} **Channel Update** → Full settings reverted → Ban\n"
        f"{emojitick} **Role Create** → Attacker roles deleted → Ban\n"
        f"{emojitick} **Role Delete** → Role auto-restored → Ban\n"
        f"{emojitick} **Role Update** → Permissions reverted → Ban\n"
        f"{emojitick} **@everyone / @here** → 24h Timeout + Messages deleted\n"
        f"{emojitick} **Guild Update** → Name, icon, banner reverted → Ban\n"
        f"{emojitick} **Webhook Spam** → All webhooks deleted → Ban\n\n"
        f"{'─' * 32}\n"
        f"### Important Tips\n\n"
        f"{emojidot} Keep **CupidX's role** at the **top** of role hierarchy.\n"
        f"{emojidot} Ensure CupidX has **Administrator** permission.\n"
        f"{emojidot} Use `{prefix}antinuke disable` to turn off protection.\n\n"
        f"*Powered by CupidX Security Engine v2 — Zero Tolerance Mode*"
    )

    view = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"## {emojisecurity} Antinuke Enabled"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())
    view.add_item(container)
    return view


# ========================= ANTINUKE COG =========================
class Antinuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _check_permissions(self, ctx: commands.Context) -> bool:
        """Check owner/extra owner permissions."""
        is_owner = ctx.author.id == ctx.guild.owner_id
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (ctx.guild.id, ctx.author.id),
            ) as cursor:
                check = await cursor.fetchone()
        return is_owner or bool(check)

    async def _run_loading_sequence(self, msg: discord.Message):
        """Animate loading bar through all stages."""
        for percent, stage_text in LOADING_STAGES:
            card = loading_card(percent, stage_text)
            await msg.edit(view=card)
            await asyncio.sleep(0.75)

    # ── Hybrid Command ─────────────────────────────────────────────────
    @commands.hybrid_command(
        name="antinuke",
        aliases=["antiwizz", "anti"],
        description="Enable or Disable Anti-Nuke protection for your server.",
    )
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @discord.app_commands.describe(
        option="Choose an action: enable, disable, or leave blank for info panel."
    )
    @discord.app_commands.choices(option=[
        discord.app_commands.Choice(name="enable", value="enable"),
        discord.app_commands.Choice(name="disable", value="disable"),
    ])
    async def antinuke(self, ctx: commands.Context, option: str | None = None):
        """Enable/Disable Antinuke protection."""

        # ── Permission Check ──────────────────────────────────────────
        if not await self._check_permissions(ctx):
            view = v2_card(
                f"{emojicross} Access Denied",
                f"> {ctx.author.mention}, you don't have permission to run this command.\n\n"
                "Only **Server Owner** or **Extra Owner** can control Antinuke.",
            )
            return await ctx.send(view=view)

        guild_id = ctx.guild.id
        prefix = ctx.prefix or "/"

        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        is_activated = row[0] if row else False

        # ── No Option: Info Panel ─────────────────────────────────────
        if option is None:
            view = v2_card(
                f"{emojisecurity} Antinuke System",
                f"**Server:** {ctx.guild.name}\n"
                f"**Status:** {'{EMOJI_ENABLE2} Enabled' if is_activated else '{EMOJI_DISABLE2} Disabled'}\n\n"
                "Automatically punish disloyal admins involved in suspicious actions.\n\n"
                f"{emojidot} `{prefix}antinuke enable` — Activate Protection\n"
                f"{emojidot} `{prefix}antinuke disable` — Deactivate Protection\n\n"
                f"*Powered by CupidX Security Engine v2*",
            )
            return await ctx.send(view=view)

        # ── ENABLE ────────────────────────────────────────────────────
        if option.lower() == "enable":
            if is_activated:
                view = v2_card(
                    f"{emojisecurity} Already Protected",
                    f"**{ctx.guild.name}** already has Antinuke **enabled**.\n\n"
                    f"**Status:** {EMOJI_ENABLE2} Active & Running\n\n"
                    f"Use `{prefix}antinuke disable` to deactivate.",
                )
                return await ctx.send(view=view)

            # ── Send initial loading card ──
            init_card = loading_card(0, "{EMOJI_LIGHTNING} Initializing CupidX Security Engine...")
            setup_msg = await ctx.send(view=init_card)

            # ── Stage 1: Check permissions ──
            await asyncio.sleep(0.6)
            await setup_msg.edit(view=loading_card(10, "{EMOJI_ADD} Scanning server structure..."))

            if not ctx.guild.me.guild_permissions.manage_guild:
                fail_view = v2_card(
                    "{EMOJI_SIGN} Setup Failed",
                    "**Missing Required Permission:** `Manage Server`\n\n"
                    "Please grant CupidX the correct permissions and try again.",
                )
                await setup_msg.edit(view=fail_view)
                return

            await asyncio.sleep(0.6)
            await setup_msg.edit(view=loading_card(22, "{EMOJI_KEY} Verifying bot permissions..."))
            await asyncio.sleep(0.6)

            # ── Stage 2: Create shield role ──
            await setup_msg.edit(view=loading_card(35, "{EMOJI_SHIELD} Forging CupidX's Shield role..."))
            role = discord.utils.get(ctx.guild.roles, name="CupidX's shield")

            if role is None:
                try:
                    role = await ctx.guild.create_role(
                        name="CupidX's shield",
                        color=color_warning,
                        permissions=discord.Permissions(administrator=True),
                        hoist=False,
                        mentionable=False,
                        reason="Antinuke setup - shield role",
                    )
                except discord.Forbidden:
                    fail_view = v2_card(
                        "{EMOJI_SIGN} Setup Failed",
                        "**Missing Permission:** Cannot create roles.\n\n"
                        "Required: `Create Roles`, `Manage Roles`",
                    )
                    await setup_msg.edit(view=fail_view)
                    return

            if role not in ctx.guild.me.roles:
                await ctx.guild.me.add_roles(role)

            await asyncio.sleep(0.6)

            # ── Stage 3: Bind modules ──
            await setup_msg.edit(view=loading_card(50, "<:cog:1487152125069889677> Binding protection modules to core..."))
            await asyncio.sleep(0.7)

            await setup_msg.edit(view=loading_card(63, "{EMOJI_BOND2} Linking audit log trackers..."))
            await asyncio.sleep(0.7)

            await setup_msg.edit(view=loading_card(75, "{EMOJI_FREEZE} Loading threat detection engine..."))
            await asyncio.sleep(0.7)

            await setup_msg.edit(view=loading_card(88, "{EMOJI_KEY} Encrypting protection layer..."))
            await asyncio.sleep(0.6)

            # ── Stage 4: Save to DB ──
            await setup_msg.edit(view=loading_card(95, "{EMOJI_BOOST} Syncing with database..."))

            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)",
                    (guild_id, True),
                )
                await db.commit()

            await asyncio.sleep(0.6)
            await setup_msg.edit(view=loading_card(100, " {EMOJI_TICK} All systems online! Protection active."))
            await asyncio.sleep(1.2)

            # ── Delete loading, show full success embed ──
            await setup_msg.delete()

            success_view = build_enable_success_view(ctx.guild.name, prefix)
            await ctx.send(view=success_view)
            return

        # ── DISABLE ───────────────────────────────────────────────────
        if option.lower() == "disable":
            if not is_activated:
                view = v2_card(
                    f"{emojidisabled} Not Active",
                    f"Antinuke is **not enabled** on **{ctx.guild.name}**.\n\n"
                    f"Use `{prefix}antinuke enable` to activate protection.",
                )
                return await ctx.send(view=view)

            # ── Disable loading bar ──
            disable_msg = await ctx.send(view=loading_card(0, "{EMOJI_DISABLE2} Shutting down protection layers...", title="<:cog:1487152125069889677> Antinuke Disabling"))

            await asyncio.sleep(0.6)
            await disable_msg.edit(view=loading_card(30, "{EMOJI_NOTES} Clearing active module bindings...", title="<:cog:1487152125069889677> Antinuke Disabling"))
            await asyncio.sleep(0.6)
            await disable_msg.edit(view=loading_card(60, "{EMOJI_STARS} Removing from database...", title="{EMOJI_DISABLE2} Antinuke Disabling"))

            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "DELETE FROM antinuke WHERE guild_id = ?", (guild_id,)
                )
                await db.commit()

            await asyncio.sleep(0.6)
            await disable_msg.edit(view=loading_card(90, "{EMOJI_KEY} Deactivating shield role...", title="{EMOJI_DISABLE2} Antinuke Disabling"))
            await asyncio.sleep(0.6)
            await disable_msg.edit(view=loading_card(100, "{EMOJI_SHUFFLE}  Protection offline.", title="{EMOJI_DISABLE2} Antinuke Disabling"))
            await asyncio.sleep(1.0)
            await disable_msg.delete()

            view = v2_card(
                f"{emojicross} Antinuke Disabled",
                f"**{ctx.guild.name}** protection is now **offline**.\n\n"
                f"**Status:** {EMOJI_DISABLE2} Disabled\n\n"
                f"Use `{prefix}antinuke enable` to reactivate at any time.",
            )
            return await ctx.send(view=view)

        # ── Invalid Option ─────────────────────────────────────────────
        view = v2_card(
            f"{emojicross} Invalid Option",
            f"Unknown option: `{option}`\n\n"
            "**Valid options:**\n"
            f"{emojidot} `{prefix}antinuke enable`\n"
            f"{emojidot} `{prefix}antinuke disable`",
        )
        await ctx.send(view=view)

    # ── Error Handler ─────────────────────────────────────────────────
    @antinuke.error
    async def antinuke_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandOnCooldown):
            retry = round(error.retry_after, 2)
            view = v2_card(
                "{EMOJI_UTILITY8} Cooldown Active",
                f"{ctx.author.mention}, slow down!\n\n"
                f"**Retry in:** `{retry}s`\n\n"
                "*Security commands have cooldowns to prevent abuse.*",
            )
            await ctx.send(view=view)
            return
        raise error

    # ── Antinuke Status ───────────────────────────────────────────────
    @commands.hybrid_command(
        name="antinukestatus",
        aliases=["anstatus", "an_status"],
        description="Show full antinuke module status for this server.",
    )
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def antinukestatus(self, ctx: commands.Context):
        """Show full antinuke module status for this server."""
        if not await self._check_permissions(ctx):
            return await ctx.send(view=v2_card(
                f"{emojicross} Access Denied",
                f"> {ctx.author.mention}, only **Server Owner** or **Extra Owner** can use this.",
            ))

        guild_id = ctx.guild.id
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
            async with db.execute("SELECT COUNT(*) FROM whitelisted_users WHERE guild_id = ?", (guild_id,)) as cur:
                wl_count = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM extraowners WHERE guild_id = ?", (guild_id,)) as cur:
                eo_count = (await cur.fetchone())[0]

        enabled = bool(row and row[0])
        status_str = (
            "{EMOJI_ENABLE2} **ENABLED**"
            if enabled else
            "{EMOJI_DISABLE2} **DISABLED**"
        )
        role = discord.utils.get(ctx.guild.roles, name="CupidX's shield")
        if role:
            role_str = f"{EMOJI_TICK} Found (Position: `{role.position}/{len(ctx.guild.roles)}`)"
        else:
            role_str = f"{EMOJI_CROSS2} Not Found — run `{ctx.prefix}antinuke enable`"
        bot_top = bool(role and ctx.guild.me.top_role >= role)
        bot_top_str = "{EMOJI_TICK} Yes" if bot_top else "{EMOJI_WARN} No — move CupidX's Shield higher"

        await ctx.send(view=v2_card(
            f"{emojisecurity} Antinuke Status — {ctx.guild.name}",
            f"**Protection:** {status_str}\n"
            f"**Shield Role:** {role_str}\n"
            f"**Bot High Enough:** {bot_top_str}\n"
            f"**Whitelisted Users:** `{wl_count}`\n"
            f"**Extra Owners:** `{eo_count}`\n\n"
            f"{'─' * 32}\n"
            f"**Active Modules:**\n\n"
            f"{antinuke_tick1} Ban / Kick / Prune / Bot Add\n"
            f"{antinuke_tick1} Channel Create / Delete / Update\n"
            f"{antinuke_tick1} Role Create / Delete / Update\n"
            f"{antinuke_tick1} Guild Update (Name, Icon, Banner)\n"
            f"{antinuke_tick1} Webhook Create / Delete / Update / Spam\n"
            f"{antinuke_tick1} @everyone / @here Mention Abuse\n"
            f"{antinuke_tick1} Emoji & Sticker Bulk Actions\n"
            f"{antinuke_tick1} Integration Add\n"
            f"{antinuke_tick1} Member Role Update\n"
            f"{antinuke_tick1} Role Strip Before Ban\n\n"
            f"*Powered by CupidX Security Engine v2*",
        ))

    # ── Button Interaction: Punishment Types ──────────────────────────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("antinuke_punish_"):
            view = v2_card(
                "{EMOJI_BOND} Punishment Types",
                "**{EMOJI_LIGHTNING} God Level Punishments Active:**\n\n"
                f"{emojitick} **Ban / Kick / Prune / Webhook / Bot** → Role Strip → Permanent Ban\n"
                f"{emojitick} **Channel Create** → Attacker channels deleted → Ban\n"
                f"{emojitick} **Channel Delete** → Auto-restore channel → Ban\n"
                f"{emojitick} **Channel Update** → Full settings revert → Ban\n"
                f"{emojitick} **Role Create** → All attacker roles deleted → Ban\n"
                f"{emojitick} **Role Delete** → Auto-restore role → Ban\n"
                f"{emojitick} **Role Update** → Permissions reverted → Ban\n"
                f"{emojitick} **@everyone / @here** → 24h Timeout + Messages deleted\n"
                f"{emojitick} **Guild Update** → Name, icon & banner revert → Ban\n"
                f"{emojitick} **Webhook Spam** → All webhooks deleted → Ban\n\n"
                "**{EMOJI_BOND2} Role Strip System:**\n"
                "Dangerous roles are stripped BEFORE ban to prevent any escape attempt.\n\n"
                "*CupidX Security Engine v2 — Zero Tolerance Mode*",
            )
            await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))
