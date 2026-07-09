import discord
from discord.ext import commands
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button, ActionRow
import aiosqlite
from utils.Tools import blacklist_check, ignore_check
from utils.detectfile import *

# ========================= EMOJIS =========================
emojitick    = EMOJI_TICK
emojicross   = EMOJI_CROSS2
emojiwarn    = EMOJI_WARN
emojidot     = EMOJI_DOT
emojisec     = EMOJI_SHIELD

DB = "db/anti.db"

# ========================= V2 CARD HELPER =========================
def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(f"## {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())
    view.add_item(container)
    return view


# ========================= CONFIRM VIEW =========================
class ConfirmView(LayoutView):
    def __init__(self, author: discord.Member, body: str):
        super().__init__(timeout=30)
        self.author = author
        self.value  = None
        self.done   = False

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.secondary, emoji=emojitick)
        cancel_btn  = Button(label="Cancel",  style=discord.ButtonStyle.secondary, emoji=emojicross)

        async def confirm_cb(interaction: discord.Interaction):
            self.value = True
            await interaction.response.defer()
            self.stop()

        async def cancel_cb(interaction: discord.Interaction):
            self.value = False
            await interaction.response.defer()
            self.stop()

        confirm_btn.callback = confirm_cb
        cancel_btn.callback  = cancel_cb

        self.add_item(Container(
            TextDisplay(body),
            Separator(),
            ActionRow(confirm_btn, cancel_btn),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                f"{emojicross} This isn't your session!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if not self.done:
            self._children.clear()
            self.add_item(Container(
                TextDisplay(f"## {emojiwarn} Timed Out\n\nConfirmation expired. Run the command again.")
            ))


# ========================= EXTRAOWNER COG =========================
class Extraowner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await self._init_db()

    async def _init_db(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS extraowners (
                    guild_id INTEGER,
                    owner_id INTEGER,
                    PRIMARY KEY (guild_id, owner_id)
                )
            ''')
            await db.commit()

    @commands.hybrid_command(
        name="extraowner",
        aliases=["eo"],
        description="Manage Extra Owners for antinuke system.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @discord.app_commands.describe(
        option="Action: set, remove, view, reset",
        user="Target user (required for set/remove)"
    )
    @discord.app_commands.choices(option=[
        discord.app_commands.Choice(name="set",    value="set"),
        discord.app_commands.Choice(name="remove", value="remove"),
        discord.app_commands.Choice(name="view",   value="view"),
        discord.app_commands.Choice(name="reset",  value="reset"),
    ])
    async def extraowner(self, ctx: commands.Context, option: str = None, user: discord.Member = None):
        """Manage Extra Owners — only Server Owner can use this."""

        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(view=v2_card(
                f"{emojicross} Owner Only",
                "Only the **Server Owner** can manage Extra Owners."
            ))

        pre = ctx.prefix or "/"

        # ── Info panel ──
        if option is None:
            return await ctx.send(view=v2_card(
                f"{emojisec} Extra Owner Manager",
                f"Extra Owners have **full antinuke command access** — same level as server owner.\n"
                f"**Limit:** Max `3` extra owners per server.\n\n"
                f"{emojidot} `{pre}extraowner set @user` — Add extra owner\n"
                f"{emojidot} `{pre}extraowner remove @user` — Remove extra owner\n"
                f"{emojidot} `{pre}extraowner view` — View all extra owners\n"
                f"{emojidot} `{pre}extraowner reset` — Remove ALL extra owners\n"
            ))

        # ── SET ──
        if option.lower() == "set":
            if user is None or user.bot:
                return await ctx.send(view=v2_card(
                    f"{emojicross} Invalid",
                    f"Please mention a **valid non-bot member**.\nUsage: `{pre}extraowner set @user`"
                ))
            if user.id == ctx.guild.owner_id:
                return await ctx.send(view=v2_card(
                    f"{emojicross} Not Needed",
                    "You are already the **Server Owner**."
                ))

            async with aiosqlite.connect(DB) as db:
                async with db.execute(
                    "SELECT owner_id FROM extraowners WHERE guild_id=? AND owner_id=?",
                    (ctx.guild.id, user.id)
                ) as cur:
                    if await cur.fetchone():
                        return await ctx.send(view=v2_card(
                            f"{emojiwarn} Already Added",
                            f"{user.mention} is **already** an Extra Owner."
                        ))
                async with db.execute(
                    "SELECT COUNT(*) FROM extraowners WHERE guild_id=?",
                    (ctx.guild.id,)
                ) as cur:
                    count = (await cur.fetchone())[0]
            if count >= 3:
                return await ctx.send(view=v2_card(
                    f"{emojiwarn} Limit Reached",
                    f"Maximum **3 Extra Owners** allowed.\nUse `{pre}extraowner remove @user` first."
                ))

            confirm = ConfirmView(
                ctx.author,
                f"## {emojiwarn} Confirm Assignment\n\n"
                f"**Target:** {user.mention} (`{user.id}`)\n\n"
                f"{emojidot} They will get full antinuke command access.\n"
                f"{emojidot} Undo with `{pre}extraowner remove @user`."
            )
            msg = await ctx.send(view=confirm)
            await confirm.wait()
            confirm.done = True

            if not confirm.value:
                return await msg.edit(view=v2_card(f"{emojicross} Cancelled", "Assignment was cancelled."))

            async with aiosqlite.connect(DB) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO extraowners (guild_id, owner_id) VALUES (?, ?)",
                    (ctx.guild.id, user.id)
                )
                await db.commit()

            await msg.edit(view=v2_card(
                f"{emojitick} Extra Owner Added",
                f"{user.mention} is now an **Extra Owner**.\nThey have full antinuke command access."
            ))

        # ── REMOVE ──
        elif option.lower() == "remove":
            if user is None:
                return await ctx.send(view=v2_card(
                    f"{emojicross} Invalid",
                    f"Please mention a user.\nUsage: `{pre}extraowner remove @user`"
                ))

            async with aiosqlite.connect(DB) as db:
                async with db.execute(
                    "SELECT owner_id FROM extraowners WHERE guild_id=? AND owner_id=?",
                    (ctx.guild.id, user.id)
                ) as cur:
                    if not await cur.fetchone():
                        return await ctx.send(view=v2_card(
                            f"{emojicross} Not Found",
                            f"{user.mention} is **not** an Extra Owner."
                        ))

            confirm = ConfirmView(
                ctx.author,
                f"## {emojiwarn} Confirm Removal\n\n"
                f"**Target:** {user.mention} (`{user.id}`)\n\n"
                "This will fully revoke their Extra Owner access."
            )
            msg = await ctx.send(view=confirm)
            await confirm.wait()
            confirm.done = True

            if not confirm.value:
                return await msg.edit(view=v2_card(f"{emojicross} Cancelled", "Removal was cancelled."))

            async with aiosqlite.connect(DB) as db:
                await db.execute(
                    "DELETE FROM extraowners WHERE guild_id=? AND owner_id=?",
                    (ctx.guild.id, user.id)
                )
                await db.commit()

            await msg.edit(view=v2_card(
                f"{emojitick} Extra Owner Removed",
                f"{user.mention} is no longer an **Extra Owner**."
            ))

        # ── VIEW ──
        elif option.lower() == "view":
            async with aiosqlite.connect(DB) as db:
                async with db.execute(
                    "SELECT owner_id FROM extraowners WHERE guild_id=?",
                    (ctx.guild.id,)
                ) as cur:
                    rows = await cur.fetchall()

            if not rows:
                return await ctx.send(view=v2_card(
                    f"👑 Extra Owners — {ctx.guild.name}",
                    f"No extra owners set.\n\nUse `{pre}extraowner set @user` to add one."
                ))

            lines = []
            for i, (uid,) in enumerate(rows, 1):
                m = ctx.guild.get_member(uid)
                lines.append(f"{emojidot} **{i}.** {m.mention if m else f'`{uid}`'}")

            await ctx.send(view=v2_card(
                f"👑 Extra Owners — {ctx.guild.name}",
                f"**{len(rows)}/3 Extra Owner(s):**\n\n" + "\n".join(lines)
            ))

        # ── RESET ──
        elif option.lower() == "reset":
            async with aiosqlite.connect(DB) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM extraowners WHERE guild_id=?",
                    (ctx.guild.id,)
                ) as cur:
                    count = (await cur.fetchone())[0]

            if count == 0:
                return await ctx.send(view=v2_card(
                    f"{emojicross} Nothing to Reset",
                    "No extra owners are currently set."
                ))

            confirm = ConfirmView(
                ctx.author,
                f"## {emojiwarn} Confirm Reset\n\n"
                f"This will remove **all {count} Extra Owner(s)** from **{ctx.guild.name}**.\n\n"
                "This action cannot be undone."
            )
            msg = await ctx.send(view=confirm)
            await confirm.wait()
            confirm.done = True

            if not confirm.value:
                return await msg.edit(view=v2_card(f"{emojicross} Cancelled", "Reset was cancelled."))

            async with aiosqlite.connect(DB) as db:
                await db.execute("DELETE FROM extraowners WHERE guild_id=?", (ctx.guild.id,))
                await db.commit()

            await msg.edit(view=v2_card(
                f"{emojitick} Extra Owners Reset",
                f"All extra owners for **{ctx.guild.name}** have been removed."
            ))

        else:
            await ctx.send(view=v2_card(
                f"{emojicross} Invalid Option",
                f"Unknown option: `{option}`\n\nValid: `set`, `remove`, `view`, `reset`"
            ))

    @extraowner.error
    async def extraowner_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(view=v2_card(
                f"{emojiwarn} Cooldown",
                f"Please wait **{round(error.retry_after, 2)}s** before running this again."
            ))
            return
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Extraowner(bot))
