from __future__ import annotations
from discord.ext import commands
import discord
import aiohttp
import json
import jishaku
import asyncio
import typing
from typing import List
import aiosqlite
from utils.config import OWNER_IDS
from utils import getConfig, updateConfig
from .Context import Context
from discord.ext import commands, tasks
from colorama import Fore, Style, init
import importlib
import inspect

init(autoreset=True)

# ✅ Add your Music cog here
extensions: List[str] = [
    "cogs.commands.Management",
    # <-- THIS LINE ADDED
]

GUILD_ID = 1417679651236614208

class cupidx(commands.Bot):

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.all()
        super().__init__(command_prefix=self.get_prefix,
                         case_insensitive=True,
                         intents=intents,
                         status=discord.Status.online,
                         strip_after_prefix=True,
                         owner_ids=OWNER_IDS,
                         allowed_mentions=discord.AllowedMentions(
                             everyone=False, replied_user=False, roles=False),
                         sync_commands_debug=False,
                         sync_commands=False)

    async def setup_hook(self):
        await self.load_extensions()

        try:
            synced = await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            print(f"{Fore.YELLOW}{Style.BRIGHT} ✦ {Fore.WHITE}Synced {len(synced)} commands to guild.")
        except Exception as e:
            print(f"{Fore.RED}{Style.BRIGHT} ✖ Failed to sync commands: {e}")

    async def load_extensions(self):
        print(f"{Fore.MAGENTA}{Style.BRIGHT} ❯ {Fore.WHITE}Loading Extensions...")
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(f"{Fore.CYAN}{Style.BRIGHT}  ✔ {Fore.WHITE}Loaded: {Fore.GREEN}{extension}")
            except Exception as e:
                print(f"{Fore.RED}{Style.BRIGHT}  ✘ Failed: {Fore.WHITE}{extension} | {Fore.YELLOW}{e}")
        print(f"{Fore.MAGENTA}{Style.BRIGHT} {'=' * 30}")

    async def on_connect(self):
        await self.change_presence(status=discord.Status.dnd,
                                   activity=discord.Activity(
                                       type=discord.ActivityType.playing,
                                       name='$help | $invite '))

    async def send_raw(self, channel_id: int, content: str,
                       **kwargs) -> typing.Optional[discord.Message]:
        await self.http.send_message(channel_id, content, **kwargs)

    async def invoke_help_command(self, ctx: Context) -> None:
        return await ctx.send_help(ctx.command)

    async def fetch_message_by_channel(
            self, channel: discord.TextChannel,
            messageID: int) -> typing.Optional[discord.Message]:
        async for msg in channel.history(
                limit=1,
                before=discord.Object(messageID + 1),
                after=discord.Object(messageID - 1),
        ):
            return msg

    async def get_prefix(self, message: discord.Message):
        if not message.guild:
            return commands.when_mentioned_or('-')(self, message)

        guild_id = message.guild.id
        data = await getConfig(guild_id)
        prefix = data["prefix"]

        async with aiosqlite.connect('db/np.db') as db:
            async with db.execute("SELECT id FROM np WHERE id = ?", (message.author.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return commands.when_mentioned_or(prefix, '')(self, message)
                else:
                    return commands.when_mentioned_or(prefix)(self, message)

    async def on_message_edit(self, before, after):
        ctx: Context = await self.get_context(after, cls=Context)
        if before.content != after.content:
            if after.guild is None or after.author.bot:
                return
            if ctx.command is None:
                return
            if isinstance(ctx.channel, discord.Thread):
                return
            await self.invoke(ctx)
        else:
            return


def setup_bot():
    intents = discord.Intents.all()
    bot = cupidx(intents=intents)
    return bot