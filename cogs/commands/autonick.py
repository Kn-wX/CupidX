import discord
from discord.ext import commands
import aiosqlite
from utils.detectfile import *
from discord.ui import LayoutView, Container, TextDisplay, Separator

# ========================= EMOJIS & COLORS =========================
emojitick = EMOJI_TICK
emojicross = EMOJI_BOND
emojiwarn = EMOJI_SIGN
emojidot = EMOJI_BUTTON

color_primary = 0x134E5E
color_warning = 0xFCD005

DB_PATH = "db/autonick.db"

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
class AutoNick(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.init_db())

    async def init_db(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS autonick (
                    guild_id INTEGER PRIMARY KEY,
                    template TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def set_template(self, guild_id: int, template: str) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO autonick (guild_id, template) VALUES (?, ?)",
                (guild_id, template),
            )
            await db.commit()

    async def get_template(self, guild_id: int) -> str | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT template FROM autonick WHERE guild_id = ?", (guild_id,)
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def clear_template(self, guild_id: int) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM autonick WHERE guild_id = ?", (guild_id,))
            await db.commit()

    # ========================= COMMANDS =========================

    @commands.hybrid_group(
        name="autonick",
        aliases=["anick", "autonickname"],
        invoke_without_command=True,
        help="Auto nickname system for new members.",
    )
    @commands.guild_only()
    async def autonick(self, ctx: commands.Context):
        prefix = ctx.prefix
        body = (
            "Automatically style nicknames for new members in this server.\n\n"
            "**Sub‑commands**\n"
            f"{emojidot} `{prefix}autonick setup <template>` – set the pattern\n"
            f"{emojidot} `{prefix}autonick config` – view current template\n"
            f"{emojidot} `{prefix}autonick reset` – turn it off\n\n"
            "Use `{member}` inside the template where the username should appear.\n"
            "Example: `★ {member}` → `★ Nextra`"
        )
        await ctx.send(view=v2_card("AutoNick Panel", body))

    @autonick.command(name="setup")
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    async def setup_autonick(self, ctx: commands.Context, *, nickname_template: str):
        if "{member}" not in nickname_template:
            body = (
                f"{emojiwarn} The template must include `{{member}}`.\n\n"
                "That placeholder will be replaced with the member's username.\n"
                "Example: `☆ {member}` or `[{member}]`."
            )
            return await ctx.send(view=v2_card("Invalid Template", body))

        await self.set_template(ctx.guild.id, nickname_template)
        preview = nickname_template.replace("{member}", ctx.author.name)
        body = (
            f"{emojitick} AutoNick is now active for **{ctx.guild.name}**.\n\n"
            f"**Template:** `{nickname_template}`\n"
            f"**Preview:** `{preview}`\n\n"
            "New members will receive nicknames following this pattern as they join."
        )
        await ctx.send(view=v2_card("AutoNick Enabled", body))

    @autonick.command(name="config")
    @commands.guild_only()
    async def config_autonick(self, ctx: commands.Context):
        template = await self.get_template(ctx.guild.id)
        if not template:
            body = (
                f"{emojicross} AutoNick is currently **disabled** here.\n\n"
                f"Use `{ctx.prefix}autonick setup <template>` to turn it on."
            )
            return await ctx.send(view=v2_card("No Configuration", body))

        preview = template.replace("{member}", ctx.author.name)
        body = (
            f"**Template:** `{template}`\n"
            f"**Preview:** `{preview}`\n\n"
            "Nicknames are applied when members join and the bot has permission "
            "to manage nicknames."
        )
        await ctx.send(view=v2_card("Current AutoNick", body))

    @autonick.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    async def reset_autonick(self, ctx: commands.Context):
        template = await self.get_template(ctx.guild.id)
        if not template:
            body = (
                f"{emojiwarn} There is no AutoNick template saved for this server.\n\n"
                f"Use `{ctx.prefix}autonick setup <template>` to create one."
            )
            return await ctx.send(view=v2_card("Nothing To Reset", body))

        await self.clear_template(ctx.guild.id)
        body = (
            f"{emojitick} AutoNick has been turned **off** for **{ctx.guild.name}**.\n\n"
            "New members will keep their default usernames when joining."
        )
        await ctx.send(view=v2_card("AutoNick Reset", body))

    # ========================= LISTENER =========================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild.me.guild_permissions.manage_nicknames:
            return

        template = await self.get_template(member.guild.id)
        if not template:
            return

        try:
            new_nick = template.replace("{member}", member.name)
            # Discord limit
            new_nick = new_nick[:32]
            await member.edit(nick=new_nick, reason="AutoNick")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoNick(bot))
