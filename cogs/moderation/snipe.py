import discord
import aiosqlite
import json
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from utils.Tools import *

DB_PATH = "snipes.db"
SEVEN_DAYS = 7 * 24 * 60 * 60  # seconds

# ===============================
#          EMOJI CATEGORY
# ===============================
class Emojis:
    DELETE = "<:CupidXdelete:1474795676251459748>"
    FORWARD = "<:CupidXforward:1476584372143656961>"
    REWIND = "<:CupidXrewind:1476584244607193108>"
    USER = "<:CupidXuser:1475151935379341382>"
    DOT = "<a:CupidXdot:1473986328126558209>"
    MENTION = "<:CupidXmention:1476575411247906897>"
    ATTACH = "<:CupidXInvite:1479528690332336270>"
    IMAGE = "<:CupidXfile:1479528347506835556>"
    STICKER = "<a:CupidXdot:1473986328126558209>"


class SnipeView(discord.ui.View):
    def __init__(self, bot, snipes, user_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.snipes = snipes
        self.index = 0
        self.user_id = user_id
        self.update_buttons()

    def update_buttons(self):
        self.first_button.disabled = self.index == 0 or len(self.snipes) == 1
        self.prev_button.disabled = self.index == 0 or len(self.snipes) == 1
        self.next_button.disabled = self.index == len(self.snipes) - 1 or len(self.snipes) == 1
        self.last_button.disabled = self.index == len(self.snipes) - 1 or len(self.snipes) == 1

    async def send_snipe_embed(self, interaction: discord.Interaction):

        snipe = self.snipes[self.index]

        embed = discord.Embed(color=0x000000)

        embed.set_author(
            name=f"Deleted Message {self.index+1}/{len(self.snipes)}",
            icon_url=snipe['author_avatar']
        )

        uid = snipe['author_id']
        name = snipe['author_name']
        deleted_ts = snipe['deleted_at']

        # Calculate days ago
        now_ts = int(datetime.now(timezone.utc).timestamp())
        days_ago = (now_ts - deleted_ts) // 86400
        if days_ago == 0:
            age_label = "Today"
        elif days_ago == 1:
            age_label = "1 day ago"
        else:
            age_label = f"{days_ago} days ago"

        embed.description = (
            f"**{Emojis.USER} Author:** **[{name}](https://discord.com/users/{uid})**\n"
            f"**{Emojis.DOT} Author ID:** `{uid}`\n"
            f"**{Emojis.MENTION} Mention:** <@{uid}>\n"
            f"**{Emojis.DELETE} Deleted:** <t:{deleted_ts}:R> ({age_label})\n"
        )

        content = snipe['content'] or "*No text content*"
        embed.add_field(
            name=f"{Emojis.DELETE} Content",
            value=content,
            inline=False
        )

        # Attachments clickable link
        if snipe["attachments"]:
            links = []
            for a in snipe["attachments"]:
                links.append(f"[{a['name']}]({a['url']})")
            embed.add_field(
                name=f"{Emojis.ATTACH} Attachments",
                value="\n".join(links),
                inline=False
            )

        if snipe['stickers']:
            embed.add_field(
                name=f"{Emojis.STICKER} Stickers",
                value="\n".join(snipe['stickers']),
                inline=False
            )

        embed.set_footer(
            text=f"Total Deleted Messages: {len(self.snipes)} | Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user_id

    @discord.ui.button(emoji=Emojis.FORWARD, style=discord.ButtonStyle.secondary)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = 0
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji=Emojis.REWIND, style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji=Emojis.DELETE, style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(emoji=Emojis.FORWARD, style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.snipes) - 1:
            self.index += 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji=Emojis.REWIND, style=discord.ButtonStyle.secondary)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = len(self.snipes) - 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)


class Snipe(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cleanup_old_snipes.start()

    async def cog_load(self):
        await self._init_db()

    async def cog_unload(self):
        self.cleanup_old_snipes.cancel()

    # ─── DB SETUP ───────────────────────────────────────────────
    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS snipes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id  INTEGER NOT NULL,
                    author_name TEXT,
                    author_avatar TEXT,
                    author_id   INTEGER,
                    content     TEXT,
                    deleted_at  INTEGER,
                    attachments TEXT,
                    stickers    TEXT,
                    image       TEXT
                )
            """)
            await db.commit()

    # ─── AUTO CLEANUP EVERY 12 HOURS ────────────────────────────
    @tasks.loop(hours=12)
    async def cleanup_old_snipes(self):
        cutoff = int(datetime.now(timezone.utc).timestamp()) - SEVEN_DAYS
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM snipes WHERE deleted_at < ?", (cutoff,))
            await db.commit()

    @cleanup_old_snipes.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # ─── SAVE SNIPE ─────────────────────────────────────────────
    async def save_snipe(self, message):
        attachments = []
        image = None

        for a in message.attachments:
            attachments.append({"name": a.filename, "url": a.url})
            if a.filename.lower().endswith(("png", "jpg", "jpeg", "gif", "webp")):
                image = a.url

        stickers = [s.name for s in message.stickers] if message.stickers else []

        deleted_at = int(datetime.now(timezone.utc).timestamp())

        async with aiosqlite.connect(DB_PATH) as db:
            # Keep max 50 per channel
            async with db.execute(
                "SELECT COUNT(*) FROM snipes WHERE channel_id = ?",
                (message.channel.id,)
            ) as cur:
                count = (await cur.fetchone())[0]

            if count >= 50:
                # Delete oldest excess
                await db.execute("""
                    DELETE FROM snipes WHERE id IN (
                        SELECT id FROM snipes WHERE channel_id = ?
                        ORDER BY deleted_at ASC LIMIT ?
                    )
                """, (message.channel.id, count - 49))

            await db.execute("""
                INSERT INTO snipes
                    (channel_id, author_name, author_avatar, author_id,
                     content, deleted_at, attachments, stickers, image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.channel.id,
                message.author.name,
                str(message.author.display_avatar.url),
                message.author.id,
                message.content,
                deleted_at,
                json.dumps(attachments),
                json.dumps(stickers),
                image
            ))
            await db.commit()

    # ─── FETCH SNIPES ───────────────────────────────────────────
    async def get_snipes(self, channel_id: int):
        cutoff = int(datetime.now(timezone.utc).timestamp()) - SEVEN_DAYS
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT author_name, author_avatar, author_id,
                       content, deleted_at, attachments, stickers, image
                FROM snipes
                WHERE channel_id = ? AND deleted_at >= ?
                ORDER BY deleted_at DESC
            """, (channel_id, cutoff)) as cur:
                rows = await cur.fetchall()

        result = []
        for row in rows:
            result.append({
                "author_name":   row[0],
                "author_avatar": row[1],
                "author_id":     row[2],
                "content":       row[3],
                "deleted_at":    row[4],
                "attachments":   json.loads(row[5]),
                "stickers":      json.loads(row[6]),
                "image":         row[7],
            })
        return result

    # ─── LISTENERS ──────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        await self.save_snipe(message)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        for message in messages:
            if not message.guild or message.author.bot:
                continue
            await self.save_snipe(message)

    # ─── COMMAND ────────────────────────────────────────────────
    @commands.hybrid_command(name="snipe")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):

        channel_snipes = await self.get_snipes(ctx.channel.id)

        if not channel_snipes:
            await ctx.send("No deleted messages found in this channel (last 7 days).")
            return

        view = SnipeView(self.bot, channel_snipes, ctx.author.id)

        first = channel_snipes[0]

        embed = discord.Embed(color=0x000000)

        embed.set_author(
            name="Last Deleted Message",
            icon_url=first['author_avatar']
        )

        uid = first['author_id']
        name = first['author_name']
        deleted_ts = first['deleted_at']

        now_ts = int(datetime.now(timezone.utc).timestamp())
        days_ago = (now_ts - deleted_ts) // 86400
        if days_ago == 0:
            age_label = "Today"
        elif days_ago == 1:
            age_label = "1 day ago"
        else:
            age_label = f"{days_ago} days ago"

        embed.description = (
            f"**{Emojis.USER} Author:** **[{name}](https://discord.com/users/{uid})**\n"
            f"**{Emojis.DOT} Author ID:** `{uid}`\n"
            f"**{Emojis.MENTION} Mention:** <@{uid}>\n"
            f"**{Emojis.DELETE} Deleted:** <t:{deleted_ts}:R> ({age_label})\n"
        )

        content = first['content'] or "*No text content*"

        embed.add_field(
            name=f"{Emojis.DELETE} Content",
            value=content,
            inline=False
        )

        if first["attachments"]:
            links = [f"[{a['name']}]({a['url']})" for a in first["attachments"]]
            embed.add_field(
                name=f"{Emojis.ATTACH} Attachments",
                value="\n".join(links),
                inline=False
            )

        if first["stickers"]:
            embed.add_field(
                name=f"{Emojis.STICKER} Stickers",
                value="\n".join(first["stickers"]),
                inline=False
            )

        embed.set_footer(
            text=f"Total Deleted Messages: {len(channel_snipes)} | Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        msg = await ctx.send(embed=embed, view=view)
        view.message = msg


async def setup(bot):
    await bot.add_cog(Snipe(bot))
