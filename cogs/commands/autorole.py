from __future__ import annotations

import logging
from typing import List, Dict

import aiosqlite
import discord
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check
from utils.detectfile import *

# ====================== LOGGING & CONSTANTS ======================

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)

DATABASE_PATH = "db/autorole.db"

EMOJI_TICK = "<:CupidXtick1:1474369967271968949>"
EMOJI_CROSS = "<:CupidXCross:1473996646873436336>"
EMOJI_WARN = "<:CupidXWarning:1474348304186867784>"
EMOJI_DOT = "<a:CupidXdot:1473986328126558209>"

OWNER_IDS = [1378341015181856768]

from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button


# ====================== V2 CARD HELPERS ======================

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view


# ====================== COG ======================

class AutoRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_table())

    # ---------- DB SETUP ----------

    async def create_table(self) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS autorole (
                    guild_id INTEGER PRIMARY KEY,
                    bots     TEXT NOT NULL,
                    humans   TEXT NOT NULL
                )
                """
            )
            await db.commit()

    # ---------- DB HELPERS ----------

    async def get_autorole(self, guild_id: int) -> Dict[str, List[int]]:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT bots, humans FROM autorole WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return {"bots": [], "humans": []}

        bots_raw, humans_raw = row

        def parse_ids(raw: str) -> List[int]:
            if not raw:
                return []
            raw = raw.replace("[", "").replace("]", "").replace(" ", "")
            if not raw:
                return []
            return [int(x) for x in raw.split(",") if x]

        return {
            "bots": parse_ids(bots_raw),
            "humans": parse_ids(humans_raw),
        }

    # ====================== ROOT GROUP ======================

    @commands.group(
        name="autorole",
        invoke_without_command=True,
        help="Configure automatic roles for new members (humans & bots).",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_root(self, ctx: commands.Context) -> None:
        body = (
            "Configure which roles are given automatically to new members.\n\n"
            "**Sub‑commands**\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole config` – show current config\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole humans add/remove` – manage human roles\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole bots add/remove` – manage bot roles\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole reset humans/bots/all` – clear config"
        )
        await ctx.reply(view=v2_card("Autorole – Overview", body))

    # ====================== CONFIG ======================

    @autorole_root.command(
        name="config",
        help="Show current autorole configuration.",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def autorole_config(self, ctx: commands.Context) -> None:
        data = await self.get_autorole(ctx.guild.id)

        humans_roles = [
            ctx.guild.get_role(rid) for rid in data["humans"] if ctx.guild.get_role(rid)
        ]
        bots_roles = [
            ctx.guild.get_role(rid) for rid in data["bots"] if ctx.guild.get_role(rid)
        ]

        hums = "\n".join(f"{EMOJI_DOT} {r.mention}" for r in humans_roles) or "`None`"
        bos = "\n".join(f"{EMOJI_DOT} {r.mention}" for r in bots_roles) or "`None`"

        body = (
            f"**Server:** {ctx.guild.name}\n\n"
            f"**Humans autoroles**\n{hums}\n\n"
            f"**Bots autoroles**\n{bos}"
        )
        await ctx.reply(view=v2_card("Autorole – Configuration", body))

    # ====================== RESET GROUP ======================

    @autorole_root.group(
        name="reset",
        invoke_without_command=True,
        help="Reset autorole configuration.",
    )
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def autorole_reset_root(self, ctx: commands.Context) -> None:
        body = (
            "Choose what to clear from autorole settings.\n\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole reset humans`\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole reset bots`\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole reset all`"
        )
        await ctx.reply(view=v2_card("Autorole – Reset", body))

    @autorole_reset_root.command(name="humans", help="Clear autorole for humans.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def autorole_reset_humans(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT humans FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data and data[0]:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "UPDATE autorole SET humans = ? WHERE guild_id = ?",
                    ("[]", ctx.guild.id),
                )
                await db.commit()
            body = f"{EMOJI_TICK} Cleared all **human** autoroles in this server."
        else:
            body = f"{EMOJI_WARN} No autoroles are set for humans in this server."

        await ctx.reply(view=v2_card("Autorole – Reset Humans", body))

    @autorole_reset_root.command(name="bots", help="Clear autorole for bots.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def autorole_reset_bots(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT bots FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data and data[0]:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "UPDATE autorole SET bots = ? WHERE guild_id = ?",
                    ("[]", ctx.guild.id),
                )
                await db.commit()
            body = f"{EMOJI_TICK} Cleared all **bot** autoroles in this server."
        else:
            body = f"{EMOJI_CROSS} No autoroles are set for bots in this server."

        await ctx.reply(view=v2_card("Autorole – Reset Bots", body))

    @autorole_reset_root.command(name="all", help="Clear all autorole configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_reset_all(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT humans, bots FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data and (data[0] or data[1]):
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "UPDATE autorole SET humans = ?, bots = ? WHERE guild_id = ?",
                    ("[]", "[]", ctx.guild.id),
                )
                await db.commit()
            body = f"{EMOJI_TICK} Cleared **all** autoroles in this server."
        else:
            body = f"{EMOJI_CROSS} No autoroles are configured in this server."

        await ctx.reply(view=v2_card("Autorole – Reset All", body))

    # ====================== HUMANS GROUP ======================

    @autorole_root.group(
        name="humans",
        invoke_without_command=True,
        help="Manage autoroles applied to humans.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_humans_root(self, ctx: commands.Context) -> None:
        body = (
            f"{EMOJI_DOT} `{ctx.prefix}autorole humans add @role`\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole humans remove @role`"
        )
        await ctx.reply(view=v2_card("Autorole – Humans", body))

    @autorole_humans_root.command(
        name="add",
        help="Add a role to human autoroles.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_humans_add(self, ctx: commands.Context, *, role: discord.Role) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT humans FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data:
            humans = eval(data[0])
            if role.id in humans:
                body = f"{EMOJI_WARN} {role.mention} is already in human autoroles."
            elif len(humans) >= 10:
                body = f"{EMOJI_WARN} You can only have up to **10** human autoroles."
            else:
                humans.append(role.id)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute(
                        "UPDATE autorole SET humans = ? WHERE guild_id = ?",
                        (str(humans), ctx.guild.id),
                    )
                    await db.commit()
                body = f"{EMOJI_TICK} {role.mention} has been added to human autoroles."
        else:
            humans = [role.id]
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "INSERT INTO autorole (guild_id, humans, bots) VALUES (?, ?, ?)",
                    (ctx.guild.id, str(humans), "[]"),
                )
                await db.commit()
            body = f"{EMOJI_TICK} {role.mention} has been added to human autoroles."

        await ctx.reply(view=v2_card("Autorole – Humans Add", body))

    @autorole_humans_root.command(
        name="remove",
        help="Remove a role from human autoroles.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_humans_remove(self, ctx: commands.Context, *, role: discord.Role) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT humans FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data:
            humans = eval(data[0])
            if role.id not in humans:
                body = f"{EMOJI_CROSS} {role.mention} is not in human autoroles."
            else:
                humans.remove(role.id)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute(
                        "UPDATE autorole SET humans = ? WHERE guild_id = ?",
                        (str(humans), ctx.guild.id),
                    )
                    await db.commit()
                body = f"{EMOJI_TICK} {role.mention} has been removed from human autoroles."
        else:
            body = f"{EMOJI_CROSS} No autoroles are set for humans in this server."

        await ctx.reply(view=v2_card("Autorole – Humans Remove", body))

    # ====================== BOTS GROUP ======================

    @autorole_root.group(
        name="bots",
        invoke_without_command=True,
        help="Manage autoroles applied to bots.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_bots_root(self, ctx: commands.Context) -> None:
        body = (
            f"{EMOJI_DOT} `{ctx.prefix}autorole bots add @role`\n"
            f"{EMOJI_DOT} `{ctx.prefix}autorole bots remove @role`"
        )
        await ctx.reply(view=v2_card("Autorole – Bots", body))

    @autorole_bots_root.command(
        name="add",
        help="Add a role to bot autoroles.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_bots_add(self, ctx: commands.Context, *, role: discord.Role) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT bots FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data:
            bots = eval(data[0])
            if role.id in bots:
                body = f"{EMOJI_WARN} {role.mention} is already in bot autoroles."
            elif len(bots) >= 10:
                body = f"{EMOJI_WARN} You can only have up to **10** bot autoroles."
            else:
                bots.append(role.id)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute(
                        "UPDATE autorole SET bots = ? WHERE guild_id = ?",
                        (str(bots), ctx.guild.id),
                    )
                    await db.commit()
                body = f"{EMOJI_TICK} {role.mention} has been added to bot autoroles."
        else:
            bots = [role.id]
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "INSERT INTO autorole (guild_id, humans, bots) VALUES (?, ?, ?)",
                    (ctx.guild.id, "[]", str(bots)),
                )
                await db.commit()
            body = f"{EMOJI_TICK} {role.mention} has been added to bot autoroles."

        await ctx.reply(view=v2_card("Autorole – Bots Add", body))

    @autorole_bots_root.command(
        name="remove",
        help="Remove a role from bot autoroles.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autorole_bots_remove(self, ctx: commands.Context, *, role: discord.Role) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT bots FROM autorole WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                data = await cursor.fetchone()

        if data:
            bots = eval(data[0])
            if role.id not in bots:
                body = f"{EMOJI_CROSS} {role.mention} is not in bot autoroles."
            else:
                bots.remove(role.id)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute(
                        "UPDATE autorole SET bots = ? WHERE guild_id = ?",
                        (str(bots), ctx.guild.id),
                    )
                    await db.commit()
                body = f"{EMOJI_TICK} {role.mention} has been removed from bot autoroles."
        else:
            body = f"{EMOJI_CROSS} No autoroles are set for bots in this server."

        await ctx.reply(view=v2_card("Autorole – Bots Remove", body))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRole(bot))
