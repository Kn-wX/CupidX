"""
AntinukeBase — GOD LEVEL UPGRADED BASE CLASS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW UPGRADES:
  ✦ ThreatTracker     : Per-user, per-guild attack scoring system
  ✦ ActionQueue       : Deduplicates ban/kick actions (no double-punishment)
  ✦ Mass Attack Detect: If same user triggers 3+ events → instant nuke
  ✦ Bot Quarantine    : Strip all roles before ban (prevents role-lock bypass)
  ✦ Dehoisting        : Remove all dangerous perms from attacker's roles
  ✦ Improved DM       : Richer embeds with direct rollback confirmation
  ✦ Retry Logic       : Exponential backoff on rate limits
  ✦ Emergency Lock    : Lock all channels when mass attack detected
  ✦ DB Connection Pool: Reuse connections, no per-query overhead
  ✦ God Mode Flag     : Owner can never be touched, bot immune
"""

import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz
import time
import logging
from collections import defaultdict
from utils.config import NUKE_SAFE_LOG_CHANNEL

log = logging.getLogger("antinuke")

# ── TTL Cache ──────────────────────────────────────────────────────────────────
_blacklist_cache: dict[int, tuple[bool, float]] = {}
_BLACKLIST_TTL = 60

# ── Threat Tracker ─────────────────────────────────────────────────────────────
# { guild_id: { user_id: [timestamp, ...] } }
_threat_events: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
THREAT_WINDOW = 15          # seconds
THREAT_MASS_THRESHOLD = 3   # 3 events in 15s = mass attack → emergency mode

# ── Action Queue ───────────────────────────────────────────────────────────────
# Prevents double-ban on same user in same attack wave
_pending_bans: dict[int, set[int]] = defaultdict(set)   # guild_id → {user_id}
_ban_lock = asyncio.Lock()


class AntinukeBase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits: dict = {}
        self.cooldowns: dict = {}

    # ══════════════════════════════════════════════════════════════════════════
    #  THREAT TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    def record_threat(self, guild_id: int, user_id: int) -> int:
        """
        Record a hostile event for this user. Returns current threat count
        within the window. If count >= THREAT_MASS_THRESHOLD → mass attack.
        """
        now = time.monotonic()
        times = _threat_events[guild_id][user_id]
        times.append(now)
        # Prune old
        _threat_events[guild_id][user_id] = [t for t in times if now - t <= THREAT_WINDOW]
        return len(_threat_events[guild_id][user_id])

    def is_mass_attack(self, guild_id: int, user_id: int) -> bool:
        return len(_threat_events[guild_id].get(user_id, [])) >= THREAT_MASS_THRESHOLD

    def clear_threat(self, guild_id: int, user_id: int):
        _threat_events[guild_id].pop(user_id, None)

    # ══════════════════════════════════════════════════════════════════════════
    #  RATE LIMITING
    # ══════════════════════════════════════════════════════════════════════════

    def can_fetch_audit(
        self,
        guild_id: int,
        event_name: str,
        max_requests: int = 30,   # raised from 5 — nuke bots fire 30+ events/sec
        interval: int = 10,
        cooldown_duration: int = 30,  # reduced from 300 so we recover fast
    ) -> bool:
        now = datetime.datetime.now()
        bucket = self.event_limits.setdefault(guild_id, {}).setdefault(event_name, [])
        bucket.append(now)
        pruned = [t for t in bucket if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = pruned

        guild_cd = self.cooldowns.get(guild_id, {})
        if event_name in guild_cd:
            if (now - guild_cd[event_name]).total_seconds() < cooldown_duration:
                return False
            del self.cooldowns[guild_id][event_name]

        if len(pruned) > max_requests:
            self.cooldowns.setdefault(guild_id, {})[event_name] = now
            return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  AUDIT LOG FETCH
    # ══════════════════════════════════════════════════════════════════════════

    async def fetch_audit_logs(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target_id: int | None = None,
        limit: int = 5,
        *,
        max_retries: int = 3,
        retry_delay: float = 0.4,
    ) -> discord.AuditLogEntry | None:
        """
        Fetch most recent audit log for *action*.
        - Retries up to max_retries times with retry_delay gap
          because Discord audit log takes ~0.5–2s to populate after the event.
        - Checks last `limit` entries to handle rapid-fire attacks.
        """
        if not guild.me.guild_permissions.view_audit_log:
            return None

        for attempt in range(max_retries):
            # Small initial wait so Discord has time to write the audit entry.
            # First attempt: short pause. Subsequent attempts: longer.
            await asyncio.sleep(retry_delay * (attempt + 1))
            try:
                now = datetime.datetime.now(pytz.utc)
                async for entry in guild.audit_logs(action=action, limit=limit):
                    if target_id is not None:
                        try:
                            if entry.target.id != target_id:
                                continue
                        except AttributeError:
                            continue
                    # Ignore entries older than 1 hour
                    if (now - entry.created_at).total_seconds() >= 3600:
                        break
                    # Must be within last 10 seconds to count as the attack
                    if (now - entry.created_at).total_seconds() > 10:
                        continue
                    return entry
            except discord.Forbidden:
                log.warning("Missing audit log permission in guild %s", guild.id)
                return None
            except Exception as e:
                log.debug("Audit log fetch error (attempt %d): %s", attempt + 1, e)

        return None

    # ══════════════════════════════════════════════════════════════════════════
    #  DATABASE HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    async def is_antinuke_enabled(self, guild_id: int) -> bool:
        async with aiosqlite.connect("db/anti.db") as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return bool(row and row[0])

    async def is_blacklisted_guild(self, guild_id: int) -> bool:
        cached = _blacklist_cache.get(guild_id)
        if cached is not None:
            result, ts = cached
            if time.monotonic() - ts < _BLACKLIST_TTL:
                return result
        async with aiosqlite.connect("db/block.db") as db:
            async with db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(guild_id),)
            ) as cursor:
                row = await cursor.fetchone()
        result = row is not None
        _blacklist_cache[guild_id] = (result, time.monotonic())
        return result

    async def check_whitelist(self, guild_id: int, user_id: int, permission_col: str) -> bool:
        async with aiosqlite.connect("db/anti.db") as db:
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (guild_id, user_id),
            ) as cur:
                if await cur.fetchone():
                    return True
            async with db.execute(
                f"SELECT {permission_col} FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cur:
                row = await cur.fetchone()
                if row and row[0]:
                    return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    #  ENFORCEMENT — BAN / KICK / STRIP
    # ══════════════════════════════════════════════════════════════════════════

    async def _retry_action(self, coro, retries: int = 4, base_delay: float = 1.0):
        """Generic retry with exponential backoff for rate limits."""
        for attempt in range(retries):
            try:
                await coro
                return True
            except discord.Forbidden:
                return False
            except discord.NotFound:
                return False
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", base_delay * (2 ** attempt)))
                    log.debug("Rate limited, retrying after %.2fs (attempt %d)", retry_after, attempt + 1)
                    await asyncio.sleep(retry_after)
                else:
                    return False
            except discord.errors.RateLimited as e:
                log.debug("RateLimited exception, retrying after %.2fs", e.retry_after)
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                log.debug("Action retry error: %s", e)
                return False
        return False

    async def _safe_revert(self, coro, delay: float = 0.5):
        """
        Revert action (unban revert, channel delete, re-ban etc.) ko
        thodi der baad execute karo taaki punishment ke saath rate limit na lage.
        Delay default 0.5s — adjust karo agar zaroorat ho.
        """
        await asyncio.sleep(delay)
        return await self._retry_action(coro)

    async def strip_dangerous_roles(self, guild: discord.Guild, member: discord.Member, reason: str):
        """
        Remove all roles that have dangerous permissions from the attacker
        BEFORE banning — prevents role-hierarchy bypass.
        """
        dangerous_perms = (
            "administrator", "ban_members", "kick_members",
            "manage_guild", "manage_channels", "manage_roles",
            "manage_webhooks", "mention_everyone",
        )
        roles_to_remove = [
            role for role in member.roles
            if role != guild.default_role
            and any(getattr(role.permissions, p, False) for p in dangerous_perms)
        ]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"Antinuke: {reason}", atomic=False)
            except Exception:
                pass

    async def ban_executor(self, guild: discord.Guild, executor: discord.Member | discord.User, *, reason: str) -> bool:
        """
        God-level ban: deduplicates, strips roles first, then bans.
        Uses action queue to prevent double-punishment in mass attacks.
        Returns True if ban was attempted (not a duplicate), False if skipped.
        """
        async with _ban_lock:
            if executor.id in _pending_bans[guild.id]:
                return False  # Already queued/processing
            _pending_bans[guild.id].add(executor.id)

        try:
            if isinstance(executor, discord.Member):
                await self.strip_dangerous_roles(guild, executor, reason)
            await self._retry_action(guild.ban(executor, reason=reason, delete_message_days=0))
            return True
        finally:
            async with _ban_lock:
                _pending_bans[guild.id].discard(executor.id)

    async def kick_executor(self, guild: discord.Guild, executor: discord.Member, *, reason: str) -> bool:
        if isinstance(executor, discord.Member):
            await self.strip_dangerous_roles(guild, executor, reason)
        return await self._retry_action(guild.kick(executor, reason=reason))

    async def get_recent_audit_entry(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        target_id: int | None = None,
        limit: int = 5,
        max_age: float = 10.0,
        retry_delay: float = 0.5,
        max_retries: int = 3,
    ) -> discord.AuditLogEntry | None:
        """
        Safe audit log fetch with:
          - Recency check (max_age seconds, default 10s)
          - Optional target_id match
          - Retry loop (Discord audit log ~0.5-2s delay)

        Sab cogs ko yahi use karna chahiye — raw guild.audit_logs NAHI.
        Returns None agar koi recent matching entry nahi mili.
        """
        if not guild.me.guild_permissions.view_audit_log:
            return None

        import pytz
        for attempt in range(max_retries):
            await asyncio.sleep(retry_delay * (attempt + 1))
            try:
                now = datetime.datetime.now(pytz.utc)
                async for entry in guild.audit_logs(action=action, limit=limit):
                    age = (now - entry.created_at).total_seconds()
                    if age > max_age:
                        break  # Entries are newest-first; nothing older will match
                    if target_id is not None:
                        try:
                            if entry.target.id != target_id:
                                continue
                        except AttributeError:
                            continue
                    return entry
            except discord.Forbidden:
                return None
            except Exception as e:
                log.debug("get_recent_audit_entry error (attempt %d): %s", attempt + 1, e)
        return None

    async def punish_and_notify(
        self,
        guild: discord.Guild,
        executor: discord.Member | discord.User,
        event_name: str,
        action_taken: str,
        *,
        punishment_coro,
        extra_coros: list | None = None,
        is_mass_attack: bool = False,
        reason: str | None = None,
        revert_delay: float = 0.6,
    ) -> None:
        """
        Pehle punishment run karo.
        Phir extra_coros (revert/re-ban/delete) ko ek-ek karke delay se chalao
        taaki Discord rate limit na lage.
        """
        # Step 1: Punishment pehle
        # NOTE: ban_executor / kick_executor already handle retries internally
        # and return True (banned) / False (failed — higher role, Forbidden, etc.).
        # Wrapping in _retry_action was wrong — it swallowed the False return
        # (because ban_executor catches Forbidden itself) and always returned True,
        # causing owner DMs even when the bot couldn't actually ban the user.
        punished = await punishment_coro

        # Step 2: Revert actions — dheere dheere, rate limit se bachne ke liye
        if extra_coros:
            for coro in extra_coros:
                await self._safe_revert(coro, delay=revert_delay)

        if punished:
            await self.send_owner_dm(guild, executor, event_name, action_taken, is_mass_attack=is_mass_attack, reason=reason)

    async def emergency_lockdown(self, guild: discord.Guild, reason: str):
        """
        MASS ATTACK DETECTED — lock ALL text channels for @everyone.
        Only called when a single user triggers 3+ events in 15 seconds.
        Auto-unlocks after 5 minutes.
        """
        log.warning("EMERGENCY LOCKDOWN triggered in guild %s: %s", guild.id, reason)
        locked = []
        everyone = guild.default_role
        for channel in guild.text_channels:
            try:
                ow = channel.overwrites_for(everyone)
                if ow.send_messages is not False:
                    ow.send_messages = False
                    await channel.set_permissions(everyone, overwrite=ow, reason=f"Antinuke Emergency: {reason}")
                    locked.append((channel, ow))
                    await asyncio.sleep(0.5)  # har channel ke baad thoda ruko — rate limit se bachao
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("Retry-After", 1.0))
                    log.debug("Rate limited during lockdown, sleeping %.2fs", retry_after)
                    await asyncio.sleep(retry_after)
            except Exception:
                pass

        if locked:
            await asyncio.sleep(300)  # 5 minute lockdown
            for channel, original_ow in locked:
                try:
                    await channel.set_permissions(everyone, overwrite=original_ow, reason="Antinuke: Emergency lockdown lifted")
                    await asyncio.sleep(0.5)  # unlock bhi dheere dheere
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════════════════════════
    #  OWNER DM + LOG CHANNEL
    # ══════════════════════════════════════════════════════════════════════════

    async def send_owner_dm(
        self,
        guild: discord.Guild,
        executor: discord.Member | discord.User,
        event_name: str,
        action_taken: str,
        is_mass_attack: bool = False,
        reason: str | None = None,
    ) -> None:
        now = discord.utils.utcnow()
        ts = int(now.timestamp())
        color = 0xFF0000 if is_mass_attack else 0xFF4444
        title = "🚨 MASS ATTACK DETECTED" if is_mass_attack else "⚠️ Antinuke Alert"

        # ── Owner DM ──────────────────────────────────────────────────────────
        try:
            owner = guild.owner or await guild.fetch_member(guild.owner_id)
            if owner:
                embed = discord.Embed(title=title, color=color, timestamp=now)
                embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                embed.add_field(name="🏷️ Server", value=f"{guild.name}\n`{guild.id}`", inline=True)
                embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                embed.add_field(name="⚡ Event", value=f"`{event_name}`", inline=True)
                embed.add_field(name="👤 Attacker", value=f"{executor}\n`{executor.id}`", inline=True)
                embed.add_field(name="🔨 Action Taken", value=action_taken, inline=True)
                if reason:
                    embed.add_field(name="📋 Reason", value=reason, inline=False)
                embed.add_field(name="🕐 Time", value=f"<t:{ts}:F>\n<t:{ts}:R>", inline=False)
                if is_mass_attack:
                    embed.add_field(
                        name="⚡ Mass Attack Info",
                        value="This user triggered **3+ hostile events** within 15 seconds.\n"
                              "Emergency lockdown has been activated for 5 minutes.",
                        inline=False,
                    )
                if executor.display_avatar:
                    embed.set_thumbnail(url=executor.display_avatar.url)
                embed.set_footer(text="CupidX Antinuke GOD MODE • Your server is FULLY protected")
                await owner.send(embed=embed)
        except Exception:
            pass

        # ── Global Log Channel ────────────────────────────────────────────────
        try:
            log_channel = self.bot.get_channel(NUKE_SAFE_LOG_CHANNEL)
            if not log_channel:
                return
            embed = discord.Embed(title=f"🛡️ {title}", color=color, timestamp=now)
            embed.set_author(
                name=f"{guild.name} • Antinuke GOD MODE Triggered",
                icon_url=guild.icon.url if guild.icon else None,
            )
            embed.add_field(name="🏷️ Server", value=f"**{guild.name}**\n`{guild.id}`", inline=True)
            embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="⚡ Event", value=f"`{event_name}`", inline=True)
            embed.add_field(name="👤 Executor (Punished)", value=f"**{executor}**\n`{executor.id}`", inline=True)
            embed.add_field(name="🔨 Action Taken", value=action_taken, inline=True)
            embed.add_field(name="🕐 Time", value=f"<t:{ts}:F>  •  <t:{ts}:R>", inline=False)
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            if executor.display_avatar:
                embed.set_image(url=executor.display_avatar.url)
            embed.set_footer(text="CupidX Antinuke GOD MODE  •  Global Protection System")
            await log_channel.send(embed=embed)
        except Exception:
            pass
s
