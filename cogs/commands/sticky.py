import discord
import aiosqlite
from discord.ext import commands

DB_PATH = "db/sticky.db"


class Sticky(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        # In-memory cache: channel_id → message_content
        # Loaded from DB on cog load so restarts/reloads are safe
        self.sticky_messages: dict[int, str] = {}

    # ── DB setup + cache load on cog ready ────────────────────
    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sticky (
                    channel_id INTEGER PRIMARY KEY,
                    content    TEXT NOT NULL
                )
            """)
            await db.commit()
            # Load all existing sticky messages into memory cache
            async with db.execute("SELECT channel_id, content FROM sticky") as cur:
                rows = await cur.fetchall()
            for channel_id, content in rows:
                self.sticky_messages[channel_id] = content

    # ── DB helpers ─────────────────────────────────────────────
    async def _db_set(self, channel_id: int, content: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sticky (channel_id, content) VALUES (?, ?)",
                (channel_id, content),
            )
            await db.commit()

    async def _db_delete(self, channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM sticky WHERE channel_id = ?", (channel_id,)
            )
            await db.commit()

    async def _db_clear(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sticky")
            await db.commit()

    # ── Commands ───────────────────────────────────────────────
    @commands.group(name="sticky", aliases=["stick"], invoke_without_command=True)
    async def sticky(self, ctx):
        embed = discord.Embed(
            title="📌 Sticky Commands",
            description=(
                "Setup and manage sticky messages for channels.\n\n"
                "**Subcommands:**\n"
                "`sticky add <message>` - Set a sticky message for this channel\n"
                "`sticky remove` - Remove the sticky message\n"
                "`sticky list` - List all sticky channels\n"
                "`sticky reset` - Clear all sticky data"
            ),
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    @sticky.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def add_sticky(self, ctx, *, message: str):
        self.sticky_messages[ctx.channel.id] = message
        await self._db_set(ctx.channel.id, message)
        await ctx.send(f"✅ Sticky message set for {ctx.channel.mention}!")

    @sticky.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def remove_sticky(self, ctx):
        if ctx.channel.id in self.sticky_messages:
            del self.sticky_messages[ctx.channel.id]
            await self._db_delete(ctx.channel.id)
            await ctx.send("🗑️ Sticky message removed for this channel.")
        else:
            await ctx.send("⚠️ No sticky message set for this channel.")

    @sticky.command(name="list")
    async def list_sticky(self, ctx):
        if not self.sticky_messages:
            await ctx.send("📭 No sticky messages configured.")
            return
        msg = "\n".join(
            [f"<#{ch}> - {txt}" for ch, txt in self.sticky_messages.items()]
        )
        embed = discord.Embed(
            title="📋 Sticky Message List",
            description=msg,
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

    @sticky.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_sticky(self, ctx):
        self.sticky_messages.clear()
        await self._db_clear()
        await ctx.send("♻️ All sticky messages have been reset.")

    # ── Listener ───────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        if channel_id not in self.sticky_messages:
            return

        content = self.sticky_messages[channel_id]

        try:
            # Delete previous sticky message from bot
            async for msg in message.channel.history(limit=10):
                if msg.author == self.bot.user and content in msg.content:
                    await msg.delete()
                    break
            # Re-send sticky message at bottom
            await message.channel.send(content)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(Sticky(bot))
