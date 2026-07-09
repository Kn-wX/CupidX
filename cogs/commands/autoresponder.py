import discord
from discord.ext import commands
import aiosqlite
import os
from discord.ui import LayoutView, Container, TextDisplay, Separator
from utils.Tools import *

DB_PATH = "db/autoresponder.db"

# ========================= EMOJIS & COLORS =========================
emojitick = "<:CupidXtick1:1474369967271968949>"
emojicross = "<:CupidXCross:1473996646873436336>"
emojiwarn  = "<:CupidXWarning:1474348304186867784>"
emojidot   = "<a:CupidXdot:1473986328126558209>"
color_warning = 0xFCD005

# ========================= V2 CARD HELPER =========================
def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    c.add_item(Separator())
    view.add_item(c)
    return view

# ========================= COG =========================
class AutoResponder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        folder = os.path.dirname(DB_PATH)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS autoresponses (
                    guild_id INTEGER,
                    name TEXT,
                    message TEXT,
                    PRIMARY KEY (guild_id, name)
                )
                """
            )
            await db.commit()

    # ========================= COMMAND GROUP =========================

    @commands.group(
        name="autoresponder",
        invoke_without_command=True,
        aliases=["ar"],
        help="Manage autoresponders in this server.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def _ar(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            prefix = ctx.prefix
            body = (
                "Set up simple text triggers that respond automatically.\n\n"
                "**Sub‑commands**\n"
                f"{emojidot} `{prefix}ar create <name> <message>` – create responder\n"
                f"{emojidot} `{prefix}ar edit <name> <message>` – change reply\n"
                f"{emojidot} `{prefix}ar delete <name>` – remove responder\n"
                f"{emojidot} `{prefix}ar config` – list all responders\n\n"
                "Name matching is **exact** and case‑insensitive."
            )
            await ctx.send(view=v2_card("AutoResponder Control", body))
            ctx.command.reset_cooldown(ctx)

    # ========================= CREATE =========================

    @_ar.command(name="create", help="Create a new autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _create(self, ctx: commands.Context, name: str, *, message: str):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM autoresponses WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                count = (await cursor.fetchone())[0]
                if count >= 20:
                    body = (
                        f"{emojiwarn} This server already has **20** autoresponders.\n\n"
                        "Remove one before adding another."
                    )
                    return await ctx.reply(view=v2_card("Limit Reached", body))

            async with db.execute(
                "SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?",
                (ctx.guild.id, name_lower),
            ) as cursor:
                if await cursor.fetchone():
                    body = (
                        f"{emojicross} An autoresponder named `{name}` already exists.\n\n"
                        "Pick a different name or edit the existing one."
                    )
                    return await ctx.reply(view=v2_card("Already Exists", body))

            await db.execute(
                "INSERT INTO autoresponses (guild_id, name, message) VALUES (?, ?, ?)",
                (ctx.guild.id, name_lower, message),
            )
            await db.commit()

        body = (
            f"{emojitick} Created a new autoresponder.\n\n"
            f"**Name:** `{name}`\n"
            f"**Guild:** {ctx.guild.name}\n\n"
            "When someone sends a message that exactly matches this name, "
            "the stored reply will be sent."
        )
        await ctx.reply(view=v2_card("Autoresponder Created", body))

    # ========================= DELETE =========================

    @_ar.command(name="delete", help="Delete an existing autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _delete(self, ctx: commands.Context, name: str):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?",
                (ctx.guild.id, name_lower),
            ) as cursor:
                if not await cursor.fetchone():
                    body = (
                        f"{emojicross} No autoresponder named `{name}` exists "
                        f"in **{ctx.guild.name}**.\n\n"
                        f"Use `{ctx.prefix}ar config` to see what is available."
                    )
                    return await ctx.reply(view=v2_card("Not Found", body))

            await db.execute(
                "DELETE FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?",
                (ctx.guild.id, name_lower),
            )
            await db.commit()

        body = (
            f"{emojitick} Removed autoresponder `{name}` from **{ctx.guild.name}**."
        )
        await ctx.reply(view=v2_card("Autoresponder Deleted", body))

    # ========================= EDIT =========================

    @_ar.command(name="edit", help="Edit an existing autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _edit(self, ctx: commands.Context, name: str, *, message: str):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?",
                (ctx.guild.id, name_lower),
            ) as cursor:
                if not await cursor.fetchone():
                    body = (
                        f"{emojicross} No autoresponder named `{name}` exists "
                        f"in **{ctx.guild.name}**."
                    )
                    return await ctx.reply(view=v2_card("Not Found", body))

            await db.execute(
                "UPDATE autoresponses SET message = ? "
                "WHERE guild_id = ? AND LOWER(name) = ?",
                (message, ctx.guild.id, name_lower),
            )
            await db.commit()

        body = (
            f"{emojitick} Updated autoresponder `{name}`.\n\n"
            "Its reply message has been replaced with your new content."
        )
        await ctx.reply(view=v2_card("Autoresponder Updated", body))

    # ========================= CONFIG / LIST =========================

    @_ar.command(name="config", help="List all autoresponders in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _config(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT name FROM autoresponses WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                autoresponses = await cursor.fetchall()

        if not autoresponses:
            body = f"There are currently **no** autoresponders in **{ctx.guild.name}**."
            return await ctx.reply(view=v2_card("Nothing Configured", body))

        lines = [
            f"{index}. `{name}`"
            for index, (name,) in enumerate(autoresponses, start=1)
        ]
        body = (
            f"Auto‑replies active in **{ctx.guild.name}**:\n\n" + "\n".join(lines)
        )
        await ctx.send(view=v2_card("Autoresponder List", body))

    # ========================= LISTENER =========================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip().lower()
        if not content:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT message FROM autoresponses "
                "WHERE guild_id = ? AND LOWER(name) = ?",
                (message.guild.id, content),
            ) as cursor:
                row = await cursor.fetchone()

        if row:
            try:
                await message.channel.send(row[0])
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
