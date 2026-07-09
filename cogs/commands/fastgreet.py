import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
from utils.detectfile import *
from discord.ui import LayoutView, Container, TextDisplay, Separator, View, Button

EMOJI_TICK = EMOJI_TICK
EMOJI_CROSS = EMOJI_SWORD
EMOJI_DOT = EMOJI_DOT

DB_PATH = "./db/fastgreet.db"

# ---------- V2 CARD HELPER ----------
def v2_card(title: str, body: str) -> LayoutView:
    """CupidX style v2 card layout."""
    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(f"# {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    view.add_item(container)
    return view

# ---------- EMBED PAGINATION FOR CHANNEL LIST ----------
class ChannelListView(View):
    def __init__(self, pages: list[str], *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        self.prev_button.disabled = True
        self.next_button.disabled = len(pages) <= 1

    def _get_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            description=self.pages[self.current_page],
            color=0x2B2D31
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} | CupidX FastGreet")
        return embed

    def _update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._get_page_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._get_page_embed(), view=self)

    @discord.ui.button(label="⏹️ Close", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="**👋 Greet channel list closed**", embed=None, view=None)

class FastGreet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("./db", exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS greet_channels (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """)

    @commands.group(name="fastgreet", invoke_without_command=True)
    async def fastgreet(self, ctx):
        """Main fastgreet command - shows all subcommands"""
        body = (
            f"{EMOJI_DOT} `{ctx.prefix}fastgreet add #channel` - Enable fast greets\n"
            f"{EMOJI_DOT} `{ctx.prefix}fastgreet remove #channel` - Disable fast greets\n"
            f"{EMOJI_DOT} `{ctx.prefix}fastgreet list` - View active channels"
        )
        await ctx.reply(view=v2_card("👋 FastGreet Manager", body))

    @fastgreet.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_greet_channel(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM greet_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id)
            )
            if cursor.fetchone():
                await ctx.reply(view=v2_card(
                    "ℹ️ Already Active",
                    f"{channel.mention} is already a greet channel."
                ))
                return
            
            conn.execute("""
                INSERT OR IGNORE INTO greet_channels (guild_id, channel_id)
                VALUES (?, ?)
            """, (ctx.guild.id, channel.id))
            conn.commit()
        
        await ctx.reply(view=v2_card(
            "✅ Greet Channel Added",
            f"{channel.mention} will now receive fast welcome messages."
        ))

    @fastgreet.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_greet_channel(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM greet_channels WHERE guild_id = ? AND channel_id = ?",
                (ctx.guild.id, channel.id)
            )
            if not cursor.fetchone():
                await ctx.reply(view=v2_card(
                    "ℹ️ Not Active",
                    f"{channel.mention} is not a greet channel."
                ))
                return
            
            conn.execute("""
                DELETE FROM greet_channels WHERE guild_id = ? AND channel_id = ?
            """, (ctx.guild.id, channel.id))
            conn.commit()
        
        await ctx.reply(view=v2_card(
            "❌ Greet Channel Removed",
            f"{channel.mention} removed from greet channels."
        ))

    @fastgreet.command(name="list")
    async def list_greet_channels(self, ctx):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM greet_channels WHERE guild_id = ?
            """, (ctx.guild.id,))
            rows = cursor.fetchall()

        if not rows:
            await ctx.reply(view=v2_card(
                "📭 No Greet Channels",
                "No channels configured for fast greetings.\n\nUse `fastgreet add #channel` to start."
            ))
            return

        channels = []
        for row in rows:
            channel = ctx.guild.get_channel(row[0])
            if channel:
                channels.append(channel.mention)

        # Pagination for multiple channels
        pages = []
        for i in range(0, len(channels), 10):
            page_channels = channels[i:i+10]
            page_content = f"**👋 Active Greet Channels ({len(channels)} total)**\n\n" + ", ".join(page_channels)
            pages.append(page_content)
        
        view = ChannelListView(pages)
        await ctx.reply(embed=view._get_page_embed(), view=view)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM greet_channels WHERE guild_id = ?
            """, (member.guild.id,))
            rows = cursor.fetchall()
            channels = [row[0] for row in rows]

        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    msg = await channel.send(f"👋 {member.mention}")
                    await asyncio.sleep(2)
                    await msg.delete()
                except discord.Forbidden:
                    continue  # Missing permissions

async def setup(bot):
    await bot.add_cog(FastGreet(bot))
