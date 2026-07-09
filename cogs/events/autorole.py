import discord
import aiohttp
import aiosqlite
import asyncio
import logging
from discord.ext import commands
from core import cupidx, Cog

DATABASE_PATH = 'db/autorole.db'
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  DANGEROUS PERMISSIONS — bot will NEVER auto-assign roles with these
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


def has_dangerous_permissions(role: discord.Role) -> bool:
    """Returns True if the role has any dangerous permission."""
    perms = role.permissions
    return any(getattr(perms, perm, False) for perm in DANGEROUS_PERMS)


class Autorole2(Cog):
    def __init__(self, bot: cupidx):
        self.bot = bot
        self.headers = {"Authorization": f"Bot {self.bot.http.token}"}

    async def get_autorole(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT bots, humans FROM autorole WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    bots, humans = row
                    bots = [int(role_id) for role_id in bots.replace('[', '').replace(']', '').replace(' ', '').split(',') if role_id]
                    humans = [int(role_id) for role_id in humans.replace('[', '').replace(']', '').replace(' ', '').split(',') if role_id]
                    return {"bots": bots, "humans": humans}
                else:
                    return {"bots": [], "humans": []}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = await self.get_autorole(member.guild.id)
        bot_roles = data["bots"]
        human_roles = data["humans"]

        roles_to_add = bot_roles if member.bot else human_roles

        for role_id in roles_to_add:
            role = member.guild.get_role(role_id)
            if not role:
                continue

            # Skip roles with dangerous permissions — never auto-assign them
            if has_dangerous_permissions(role):
                logger.warning(
                    f"[Autorole] Skipped role '{role.name}' (ID: {role.id}) in guild '{member.guild.name}' "
                    f"(ID: {member.guild.id}) — contains dangerous permissions."
                )
                continue

            try:
                await member.add_roles(role, reason="CupidX Autoroles")
            except discord.Forbidden:
                logger.warning(f"[Autorole] Missing permissions to add role '{role.name}' in guild '{member.guild.name}'.")
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        retry_after = float(retry_after)
                        logger.warning(f"[Autorole] Rate limited. Retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        try:
                            await member.add_roles(role, reason="CupidX Autoroles")
                        except Exception as retry_err:
                            logger.error(f"[Autorole] Retry failed for role '{role.name}': {retry_err}")
            except discord.errors.RateLimited as e:
                logger.warning(f"[Autorole] RateLimited. Retrying in {e.retry_after}s.")
                await asyncio.sleep(e.retry_after)
                try:
                    await member.add_roles(role, reason="CupidX Autoroles")
                except Exception as retry_err:
                    logger.error(f"[Autorole] Retry failed for role '{role.name}': {retry_err}")
            except Exception as e:
                logger.error(f"[Autorole] Unexpected error adding role '{role.name}': {e}")
")
