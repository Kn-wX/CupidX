import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import os
from utils.detectfile import *

DB_FILE = "db/logging.db"

# ---------------- EMOJIS ---------------- #

EMOJI_DELETE = "<:CupidXdelete:1474795676251459748>"
EMOJI_EDIT = "<:CupidXCommands:1475152376737566722>"
EMOJI_BAN = "<a:CupidXping:1474771697289924721>"
EMOJI_UNBAN = "<a:CupidXdot:1473986328126558209>"
EMOJI_CHANNEL = "<:CupidXfile:1479528347506835556>"
EMOJI_ROLE = "<:CupidXmention:1476575411247906897>"
EMOJI_INVITE = "<:CupidXInvite:1479528690332336270>"
EMOJI_WEBHOOK = EMOJI_CHANNEL
EMOJI_EMOJI = "<:CupidXfun:1472259051868917842>"
EMOJI_BULK = "<:CupidXMail:1475192722578215083>"

LOG_CHANNELS = {
    "channel-logs": "channel",
    "mod-logs": "mod",
    "message-logs": "message",
    "role-logs": "role",
    "guild-logs": "guild",
    "invite-logs": "invite",
    "webhook-logs": "webhook",
    "emoji-logs": "emoji"
}


class Logging(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_FILE
        self.create_table()

    def create_table(self):
        os.makedirs("db", exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id INTEGER,
                log_type TEXT,
                channel_id INTEGER
            )
            """)

    def set_log_channel(self, guild_id, log_type, channel_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "REPLACE INTO log_channels (guild_id, log_type, channel_id) VALUES (?, ?, ?)",
                (guild_id, log_type, channel_id)
            )

    def get_log_channel(self, guild_id, log_type):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT channel_id FROM log_channels WHERE guild_id=? AND log_type=?",
                (guild_id, log_type)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    async def send_log(self, guild, log_type, embed=None, file=None):

        channel_id = self.get_log_channel(guild.id, log_type)

        if not channel_id:
            return

        channel = guild.get_channel(channel_id)

        if not channel:
            return

        if embed:
            embed.timestamp = datetime.utcnow()

        await channel.send(embed=embed, file=file)

# ---------------- TRANSCRIPT CREATOR ---------------- #

    def create_transcript(self, messages):

        os.makedirs("transcripts", exist_ok=True)

        filename = f"transcripts/purge_{int(datetime.utcnow().timestamp())}.html"

        with open(filename, "w", encoding="utf-8") as f:

            f.write("<html><body style='font-family:sans-serif'>")
            f.write("<h2>Deleted Messages</h2><hr>")

            for m in messages:

                author = f"{m.author} ({m.author.id})"
                content = m.content.replace("<", "&lt;").replace(">", "&gt;")

                f.write(
                    f"<p><b>{author}</b> "
                    f"<small>{m.created_at}</small><br>"
                    f"{content}</p><hr>"
                )

            f.write("</body></html>")

        return filename

# ---------------- LOGGING SETUP ---------------- #

    @commands.hybrid_command(name="loggingsetup")
    @commands.has_permissions(administrator=True)
    async def setlogsetup(self, ctx):

        guild = ctx.guild

        category = discord.utils.get(guild.categories, name="CupidX Logs")

        if category:
            return await ctx.send("<:CupidXCross:1473996646873436336> | Logging already setup")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        category = await guild.create_category("CupidX Logs", overwrites=overwrites)

        created = []

        for name, log_type in LOG_CHANNELS.items():

            channel = await guild.create_text_channel(
                name=name,
                category=category,
                overwrites=overwrites
            )

            self.set_log_channel(guild.id, log_type, channel.id)

            created.append(name)

        embed = discord.Embed(
            title="<a:emojisetting:1476854070412316713> | CupidX Logging Setup",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Created Channels",
            value="\n".join(created)
        )

        await ctx.send(embed=embed)

# ---------------- REMOVE LOGS ---------------- #

    @commands.hybrid_command(name="removelogs")
    @commands.has_permissions(administrator=True)
    async def removelogs(self, ctx):

        guild = ctx.guild

        category = discord.utils.get(guild.categories, name="CupidX Logs")

        if not category:
            return await ctx.send("<:CupidXCross:1473996646873436336> | Logging not setup")

        for channel in category.channels:
            await channel.delete()

        await category.delete()

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM log_channels WHERE guild_id=?", (guild.id,))
            conn.commit()

        await ctx.send("<:CupidXdelete:1474795676251459748> | Logging removed")

# ---------------- MESSAGE DELETE ---------------- #

    @commands.Cog.listener()
    async def on_message_delete(self, message):

        if not message.guild or message.author.bot:
            return

        embed = discord.Embed(
            title=f"{EMOJI_DELETE} Message Deleted",
            color=0xFCD005
        )

        embed.add_field(name="User", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)

        content = message.content if message.content else "No content"

        embed.add_field(name="Content", value=content[:1000], inline=False)

        await self.send_log(message.guild, "message", embed)

# ---------------- BULK DELETE ---------------- #

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):

        if not messages:
            return

        guild = messages[0].guild

        filename = self.create_transcript(messages)

        file = discord.File(filename)

        embed = discord.Embed(
            title=f"{EMOJI_BULK} Bulk Messages Deleted",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Channel",
            value=messages[0].channel.mention
        )

        embed.add_field(
            name="Messages Deleted",
            value=str(len(messages))
        )

        embed.set_footer(text="Download transcript for full proof")

        await self.send_log(guild, "message", embed, file)

# ---------------- MESSAGE EDIT ---------------- #

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):

        if not before.guild or before.author.bot:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(
            title=f"{EMOJI_EDIT} Message Edited",
            color=discord.Color.orange()
        )

        embed.add_field(name="User", value=before.author.mention)
        embed.add_field(name="Channel", value=before.channel.mention)

        embed.add_field(name="Before", value=before.content or "None", inline=False)
        embed.add_field(name="After", value=after.content or "None", inline=False)

        await self.send_log(before.guild, "message", embed)

# ---------------- BAN ---------------- #

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):

        embed = discord.Embed(
            title=f"{EMOJI_BAN} Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(name="User", value=str(user))

        await self.send_log(guild, "mod", embed)

# ---------------- UNBAN ---------------- #

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):

        embed = discord.Embed(
            title=f"{EMOJI_UNBAN} Member Unbanned",
            color=discord.Color.green()
        )

        embed.add_field(name="User", value=str(user))

        await self.send_log(guild, "mod", embed)

# ---------------- CHANNEL ---------------- #

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):

        embed = discord.Embed(
            title=f"{EMOJI_CHANNEL} Channel Created",
            color=discord.Color.green()
        )

        embed.add_field(name="Channel", value=channel.name)

        await self.send_log(channel.guild, "channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):

        embed = discord.Embed(
            title=f"{EMOJI_DELETE} Channel Deleted",
            color=discord.Color.red()
        )

        embed.add_field(name="Channel", value=channel.name)

        await self.send_log(channel.guild, "channel", embed)

# ---------------- ROLE ---------------- #

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):

        embed = discord.Embed(
            title=f"{EMOJI_ROLE} Role Created",
            color=discord.Color.green()
        )

        embed.add_field(name="Role", value=role.name)

        await self.send_log(role.guild, "role", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):

        embed = discord.Embed(
            title=f"{EMOJI_DELETE} Role Deleted",
            color=discord.Color.red()
        )

        embed.add_field(name="Role", value=role.name)

        await self.send_log(role.guild, "role", embed)

# ---------------- INVITES ---------------- #

    @commands.Cog.listener()
    async def on_invite_create(self, invite):

        embed = discord.Embed(
            title=f"{EMOJI_INVITE} Invite Created",
            color=discord.Color.green()
        )

        embed.add_field(name="Code", value=invite.code)

        await self.send_log(invite.guild, "invite", embed)

# ---------------- EMOJI ---------------- #

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):

        added = [e for e in after if e not in before]

        for emoji in added:

            embed = discord.Embed(
                title=f"{EMOJI_EMOJI} Emoji Created",
                color=discord.Color.green()
            )

            embed.add_field(name="Name", value=emoji.name)
            embed.set_thumbnail(url=emoji.url)

            await self.send_log(guild, "emoji", embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))