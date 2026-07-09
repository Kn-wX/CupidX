import discord
from discord.ext import commands
import aiosqlite
import re
from discord.ui import LayoutView, Container, TextDisplay, Separator
from utils.Tools import *

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
class AutoReaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "db/autoreact.db"
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS autoreact (
                    guild_id INTEGER,
                    trigger TEXT,
                    emojis TEXT
                )
                """
            )
            await db.commit()

    async def get_triggers(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT trigger, emojis FROM autoreact WHERE guild_id = ?",
                (guild_id,),
            )
            return await cursor.fetchall()

    async def trigger_exists(self, guild_id: int, trigger: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM autoreact WHERE guild_id = ? AND trigger = ?",
                (guild_id, trigger),
            )
            return await cursor.fetchone() is not None

    # ========================= COMMAND GROUP =========================

    @commands.group(
        name="react",
        aliases=["autoreact"],
        help="Configure automatic emoji reactions for specific words.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def react(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            prefix = ctx.prefix
            body = (
                "Wire up emojis that fire automatically whenever certain words appear.\n\n"
                "**Sub‑commands**\n"
                f"{emojidot} `{prefix}react add <word> <emojis>` – add a trigger\n"
                f"{emojidot} `{prefix}react remove <word>` – delete a trigger\n"
                f"{emojidot} `{prefix}react list` – show current triggers\n"
                f"{emojidot} `{prefix}react reset` – wipe everything\n\n"
                "• Triggers are **single words**.\n"
                "• Each trigger can have up to **1** emojis.\n"
                "• A server can store up to **10** triggers."
            )
            await ctx.send(view=v2_card("AutoReaction Control", body))
            ctx.command.reset_cooldown(ctx)

    # ========================= ADD TRIGGER =========================

    @react.command(
        name="add",
        aliases=["set", "create"],
        help="Add an auto-reaction trigger with one or more emojis.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx: commands.Context, trigger: str, *, emojis: str):
        if len(trigger.split()) > 1:
            body = (
                f"{emojicross} Triggers must be a **single word**.\n\n"
                "Example: `react add hello 😄 👍`"
            )
            return await ctx.reply(view=v2_card("Invalid Trigger", body))

        emoji_list = re.findall(r"<a?:\w+:\d+>|[\u263a-\U0001f645]", emojis)
        if not emoji_list:
            body = (
                f"{emojiwarn} No valid emojis were detected.\n\n"
                "Use either custom emojis (`<:name:id>`) or standard Unicode emojis."
            )
            return await ctx.reply(view=v2_card("No Emojis Found", body))

        if len(emoji_list) > 10:
            body = (
                f"{emojicross} Too many emojis.\n\n"
                "You can attach **up to 10** emojis per trigger."
            )
            return await ctx.reply(view=v2_card("Limit Reached", body))

        triggers = await self.get_triggers(ctx.guild.id)
        if len(triggers) >= 10:
            body = (
                f"{emojiwarn} This server has reached the **10 trigger** cap.\n\n"
                "Remove an existing trigger before adding a new one."
            )
            return await ctx.reply(view=v2_card("Trigger Cap Reached", body))

        if await self.trigger_exists(ctx.guild.id, trigger):
            body = (
                f"{emojiwarn} The trigger `{trigger}` already exists.\n\n"
                f"Use `{ctx.prefix}react remove {trigger}` first if you want to redefine it."
            )
            return await ctx.reply(view=v2_card("Trigger Exists", body))

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO autoreact (guild_id, trigger, emojis) VALUES (?, ?, ?)",
                (ctx.guild.id, trigger, " ".join(emoji_list)),
            )
            await db.commit()

        body = (
            f"{emojitick} New trigger created.\n\n"
            f"**Word:** `{trigger}`\n"
            f"**Emojis:** {' '.join(emoji_list)}\n\n"
            "Whenever someone sends a message containing this word, "
            "CupidX will react with the configured emojis."
        )
        await ctx.reply(view=v2_card("Trigger Added", body))

    # ========================= REMOVE TRIGGER =========================

    @react.command(
        name="remove",
        aliases=["clear", "delete"],
        help="Remove an auto-reaction trigger.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx: commands.Context, trigger: str):
        if not await self.trigger_exists(ctx.guild.id, trigger):
            body = (
                f"{emojicross} The trigger `{trigger}` does not exist on this server.\n\n"
                f"Use `{ctx.prefix}react list` to see active triggers."
            )
            return await ctx.reply(view=v2_card("Trigger Not Found", body))

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM autoreact WHERE guild_id = ? AND trigger = ?",
                (ctx.guild.id, trigger),
            )
            await db.commit()

        body = (
            f"{emojitick} Trigger removed.\n\n"
            f"Auto-reactions for `{trigger}` have been cleared."
        )
        await ctx.reply(view=v2_card("Trigger Removed", body))

    # ========================= LIST TRIGGERS =========================

    @react.command(
        name="list",
        aliases=["show", "config"],
        help="Show all auto-reaction triggers for this server.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def list(self, ctx: commands.Context):
        triggers = await self.get_triggers(ctx.guild.id)
        if not triggers:
            body = (
                "There are currently **no** auto-reaction triggers configured "
                "for this server.\n\n"
                f"Use `{ctx.prefix}react add <word> <emojis>` to start."
            )
            return await ctx.reply(view=v2_card("No Triggers Set", body))

        lines = [f"• `{t}` → {e}" for t, e in triggers]
        body = (
            "Below are all words currently hooked to automatic reactions:\n\n"
            + "\n".join(lines)
        )
        await ctx.reply(view=v2_card("Active Auto-Reactions", body))

    # ========================= RESET ALL =========================

    @react.command(
        name="reset",
        help="Remove all auto-reaction triggers for this server.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx: commands.Context):
        triggers = await self.get_triggers(ctx.guild.id)
        if not triggers:
            body = (
                f"{emojicross} There is nothing to reset.\n\n"
                "No auto-reaction triggers have been configured yet."
            )
            return await ctx.reply(view=v2_card("No Triggers", body))

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM autoreact WHERE guild_id = ?", (ctx.guild.id,)
            )
            await db.commit()

        body = (
            f"{emojitick} All triggers have been cleared.\n\n"
            "Auto-reactions are now fully reset for this server."
        )
        await ctx.reply(view=v2_card("AutoReaction Reset", body))


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReaction(bot))
