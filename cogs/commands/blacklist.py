from __future__ import annotations
import discord
from discord.ext import commands
import aiosqlite
import os
from utils.Tools import *
from typing import Union, List
from utils import Paginator, DescriptionEmbedPaginator

EMOJI_TICK = "<:CupidXtick1:1474369967271968949>"
EMOJI_CROSS = "<:CupidXCross:1473996646873436336>"
EMOJI_DOT = "<a:CupidXdot:1473986328126558209>"

DB_PATH = "db/blword.db"

# ---------- EMBED HELPER ----------
def cupidx_embed(title: str, description: str = None, color: int = 0x134E5E):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name="CupidX Help Center")
    embed.set_footer(text="cupidx HQ • cupidx")
    return embed

async def create_blacklist_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id TEXT,
                word TEXT,
                PRIMARY KEY (guild_id, word)
            )
        """)
        await db.commit()

async def create_bypass_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bypass (
                guild_id TEXT,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await db.commit()

async def create_bypass_roles_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bypass_roles (
                guild_id TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
        await db.commit()

class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(create_blacklist_table())
        self.bot.loop.create_task(create_bypass_table())
        self.bot.loop.create_task(create_bypass_roles_table())
        
    ############ DATABASE FUNCTIONS ############
    async def is_word_blacklisted(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM blacklist WHERE guild_id = ? AND word = ?", (guild_id, word)) as cursor:
                return await cursor.fetchone() is not None

    async def add_word_to_blacklist(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO blacklist (guild_id, word) VALUES (?, ?)", (guild_id, word))
            await db.commit()

    async def remove_word_from_blacklist(self, guild_id, word):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM blacklist WHERE guild_id = ? AND word = ?", (guild_id, word))
            await db.commit()

    async def get_blacklisted_words(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT word FROM blacklist WHERE guild_id = ?", (guild_id,)) as cursor:
                return [row[0] async for row in cursor]

    async def is_user_bypassed(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM bypass WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
                return await cursor.fetchone() is not None

    async def add_user_to_bypass(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO bypass (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
            await db.commit()

    async def remove_user_from_bypass(self, guild_id, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM bypass WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    async def get_bypassed_users(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM bypass WHERE guild_id = ?", (guild_id,)) as cursor:
                return [row[0] async for row in cursor]

    async def is_role_bypassed(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM bypass_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id)) as cursor:
                return await cursor.fetchone() is not None

    async def add_role_to_bypass(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO bypass_roles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()

    async def remove_role_from_bypass(self, guild_id, role_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM bypass_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))
            await db.commit()

    async def get_bypassed_roles(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM bypass_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return [row[0] async for row in cursor]

    async def remove_all_words_from_blacklist(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM blacklist WHERE guild_id = ?", (guild_id,))
            await db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        words = await self.get_blacklisted_words(guild_id)
        bypassed_users = await self.get_bypassed_users(guild_id)
        bypassed_roles = await self.get_bypassed_roles(guild_id)

        if message.author.guild_permissions.administrator or message.author.id in bypassed_users:
            return

        for role in message.author.roles:
            if role.id in bypassed_roles:
                return

        for word in words:
            if word in message.content.lower():
                await message.delete()
                warning = await message.channel.send(
                    f"{EMOJI_CROSS} **{message.author.mention}**, language detected. Keep it clean."
                )
                await warning.delete(delay=4)
                break

    @commands.group(name="blacklistword", aliases=["blword"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def blacklistword(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = cupidx_embed(
                "🔒 Blacklist Manager",
                "Prevent specific words from being used in your server."
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            
            sub_cmds = (
                f"`{ctx.prefix}blword add <word>` - Block specific words\n"
                f"`{ctx.prefix}blword remove <word>` - Unblock words\n"
                f"`{ctx.prefix}blword reset` - Clear entire list\n"
                f"`{ctx.prefix}blword config` - View blocked words\n"
                f"`{ctx.prefix}blword bypass` - Manage exceptions"
            )
            embed.add_field(name="Subcommands", value=sub_cmds, inline=False)
            embed.set_footer(text="Powered by CupidX HQ", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)

    @blacklistword.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, word: str):
        guild_id = str(ctx.guild.id)
        if len(await self.get_blacklisted_words(guild_id)) >= 30:
            embed = cupidx_embed("<:CupidXWarning:1474348304186867784> Limit Reached", "Maximum 30 words allowed.")
            await ctx.reply(embed=embed)
            return
        if await self.is_word_blacklisted(guild_id, word.lower()):
            embed = cupidx_embed("<:CupidXCross:1473996646873436336> Already Blocked", f"`{word}` is already blocked.")
            await ctx.reply(embed=embed)
            return

        await self.add_word_to_blacklist(guild_id, word.lower())
        embed = cupidx_embed("<:CupidXtick1:1474369967271968949> Word Blocked", f"`{word}` added to blacklist.")
        await ctx.reply(embed=embed)

    @blacklistword.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, word: str):
        guild_id = str(ctx.guild.id)
        if not await self.is_word_blacklisted(guild_id, word.lower()):
            embed = cupidx_embed("<:CupidXCross:1473996646873436336> Not Found", f"`{word}` is not blocked.")
            await ctx.reply(embed=embed)
            return

        await self.remove_word_from_blacklist(guild_id, word.lower())
        embed = cupidx_embed("<:CupidXtick1:1474369967271968949> Word Unblocked", f"`{word}` removed from blacklist.")
        await ctx.reply(embed=embed)

    @blacklistword.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        guild_id = str(ctx.guild.id)
        words = await self.get_blacklisted_words(guild_id)

        if not words:
            embed = cupidx_embed("📭 Empty List", "No words currently blocked.")
            await ctx.reply(embed=embed)
            return

        await self.remove_all_words_from_blacklist(guild_id)
        embed = cupidx_embed("🧹 List Cleared", "All blocked words removed.")
        await ctx.reply(embed=embed)

    @blacklistword.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        guild_id = str(ctx.guild.id)
        words = await self.get_blacklisted_words(guild_id)
        if not words:
            embed = cupidx_embed("📭 No Blocks", "No words currently blocked.")
            await ctx.reply(embed=embed)
            return

        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=[f"`{word}`" for word in words],
            title=f"Current Blacklist [{len(words)}]",
            description="",
            per_page=10,
            color=0x134E5E),
            ctx=ctx)
        await paginator.paginate()

    @blacklistword.group(name="bypass", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = cupidx_embed(
                "🚫 Bypass Manager",
                "Grant users or roles exceptions to the word filter."
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            
            sub_cmds = (
                f"`{ctx.prefix}blword bypass add <@user/@role>` - Grant exception\n"
                f"`{ctx.prefix}blword bypass remove <@user/@role>` - Remove exception\n"
                f"`{ctx.prefix}blword bypass list` - View exceptions"
            )
            embed.add_field(name="Subcommands", value=sub_cmds, inline=False)
            embed.set_footer(text="cupidx HQ • cupidx", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)

    @bypass.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_add(self, ctx, target: Union[discord.Member, discord.Role]):
        guild_id = str(ctx.guild.id)
        if isinstance(target, discord.Member):
            if len(await self.get_bypassed_users(guild_id)) >= 30:
                embed = cupidx_embed("<:CupidXWarning:1474348304186867784> User Limit", "Maximum 30 user exceptions.")
                await ctx.reply(embed=embed)
                return
            if await self.is_user_bypassed(guild_id, target.id):
                embed = cupidx_embed("<:CupidXCross:1473996646873436336> Already Exempt", f"`{target}` is already bypassed.")
                await ctx.reply(embed=embed)
                return
            await self.add_user_to_bypass(guild_id, target.id)
            embed = cupidx_embed("<:CupidXtick1:1474369967271968949> User Exempted", f"`{target}` can now use blocked words.")
            await ctx.reply(embed=embed)

        elif isinstance(target, discord.Role):
            if len(await self.get_bypassed_roles(guild_id)) >= 30:
                embed = cupidx_embed("<:CupidXWarning:1474348304186867784> Role Limit", "Maximum 30 role exceptions.")
                await ctx.reply(embed=embed)
                return
            if await self.is_role_bypassed(guild_id, target.id):
                embed = cupidx_embed("<:CupidXCross:1473996646873436336> Already Exempt", f"`{target}` is already bypassed.")
                await ctx.reply(embed=embed)
                return
            await self.add_role_to_bypass(guild_id, target.id)
            embed = cupidx_embed("<:CupidXtick1:1474369967271968949> Role Exempted", f"`{target}` members can use blocked words.")
            await ctx.reply(embed=embed)

    @bypass.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_remove(self, ctx, target: Union[discord.Member, discord.Role]):
        guild_id = str(ctx.guild.id)
        if isinstance(target, discord.Member):
            if not await self.is_user_bypassed(guild_id, target.id):
                embed = cupidx_embed("<:CupidXCross:1473996646873436336> Not Exempt", f"`{target}` is not bypassed.")
                await ctx.reply(embed=embed)
                return
            await self.remove_user_from_bypass(guild_id, target.id)
            embed = cupidx_embed("<:CupidXtick1:1474369967271968949> Exemption Removed", f"`{target}` no longer bypassed.")
            await ctx.reply(embed=embed)

        elif isinstance(target, discord.Role):
            if not await self.is_role_bypassed(guild_id, target.id):
                embed = cupidx_embed("<:CupidXCross:1473996646873436336> Not Exempt", f"`{target}` is not bypassed.")
                await ctx.reply(embed=embed)
                return
            await self.remove_role_from_bypass(guild_id, target.id)
            embed = cupidx_embed("<:CupidXtick1:1474369967271968949> Exemption Removed", f"`{target}` no longer bypassed.")
            await ctx.reply(embed=embed)

    @bypass.command(name="list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_list(self, ctx):
        guild_id = str(ctx.guild.id)
        users = await self.get_bypassed_users(guild_id)
        roles = await self.get_bypassed_roles(guild_id)

        if not users and not roles:
            embed = cupidx_embed("📭 No Exemptions", "No users or roles are bypassed.")
            await ctx.reply(embed=embed)
            return

        content = []
        for uid in users:
            content.append(f"👤 User ID: `{uid}`")
        for rid in roles:
            content.append(f"🎭 Role ID: `{rid}`")
        
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=content,
            title=f"Current Exemptions [{len(content)}]",
            description="",
            per_page=10,
            color=0x134E5E),
            ctx=ctx)
        await paginator.paginate()

    @add.error
    @remove.error
    @reset.error
    @config.error
    @bypass_add.error
    @bypass_remove.error
    async def command_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            if not isinstance(error, commands.CommandOnCooldown):
                embed = cupidx_embed("<:CupidXCross:1473996646873436336> Permission Error", "Requires **Administrator** permissions.")
                await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Blacklist(bot))
