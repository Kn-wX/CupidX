import discord
from discord.ext import commands, tasks
from utils.ui_v2 import v2_card
import asyncio
import datetime
import re
from typing import *
from utils.Tools import *
from discord.ui import Button, View
from typing import Union, Optional
from io import BytesIO
import requests
import aiohttp
import time
from utils.detectfile import *
from datetime import datetime, timezone, timedelta
from collections import Counter

# CupidX Signature Color
# CUPIDX_COLOR imported from utils.detectfile

time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}

def convert(argument):
  args = argument.lower()
  matches = re.findall(time_regex, args)
  time = 0
  for key, value in matches:
    try:
      time += time_dict[value] * float(key)
    except KeyError:
      raise commands.BadArgument(
        f"{value} is an invalid time key! h|m|s|d are valid arguments")
    except ValueError:
      raise commands.BadArgument(f"{key} is not a number!")
  return round(time)

async def do_removal(ctx, limit, predicate, *, before=None, after=None):
  if limit > 2000:
      return await ctx.error(f"Too many messages to search given ({limit}/2000)")

  if before is None:
      before = ctx.message
  else:
      before = discord.Object(id=before)

  if after is not None:
      after = discord.Object(id=after)

  try:
      deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
  except discord.Forbidden as e:
      return await ctx.error("I do not have permissions to delete messages.")
  except discord.HTTPException as e:
      return await ctx.error(f"Error: {e} (try a smaller search?)")

  spammers = Counter(m.author.display_name for m in deleted)
  num_deleted = len(deleted)
  
  # --- EMBED LOGIC START ---
  desc = f"**{num_deleted}** message{' was' if num_deleted == 1 else 's were'} removed."
  
  if num_deleted:
      spammers_list = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
      if spammers_list:
          desc += "\n\n" + "\n".join(f"**{name}**: {count}" for name, count in spammers_list)

  view = v2_card("Purge Successful <:CupidXtick1:1474369967271968949>", desc)
  # --- EMBED LOGIC END ---

  await ctx.send(view=view, delete_after=7)
    

class Message(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = CUPIDX_COLOR


  @commands.group(invoke_without_command=True, aliases=["purge"], help="Clears the messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def clear(self, ctx, Choice: Union[discord.Member, int, str] = None, Amount: int = None):
        """Main purge command help menu"""
        
        # If no arguments are provided, show the Help Embed
        if Choice is None:
            commands_list = (
                f"`{ctx.prefix}purge [amount]` - Clears any messages.\n"
                f"`{ctx.prefix}purge bots` - Clears bot messages.\n"
                f"`{ctx.prefix}purge embeds` - Clears messages with embeds.\n"
                f"`{ctx.prefix}purge files` - Clears messages with files.\n"
                f"`{ctx.prefix}purge images` - Clears messages with images/embeds.\n"
                f"`{ctx.prefix}purge user [member]` - Clears a specific member's messages.\n"
                f"`{ctx.prefix}purge contains [text]` - Clears messages containing text.\n"
                f"`{ctx.prefix}purge emoji` - Clears messages with emojis.\n"
                f"`{ctx.prefix}purge reactions` - Clears reactions from messages."
            )
            
            body = (
                f"Delete messages in bulk using various filters.\n\n"
                f"**Available Commands**\n{commands_list}\n\n"
                f"**Examples**\n`{ctx.prefix}purge 10`\n`{ctx.prefix}purge user @User 50`"
            )
            
            view = v2_card(f"{self.bot.user.name} Purge System", body)
            return await ctx.reply(view=view)

        await ctx.message.delete()

        if isinstance(Choice, discord.Member):
            search = Amount or 5
            return await do_removal(ctx, search, lambda e: e.author == Choice)

        elif isinstance(Choice, int):
            return await do_removal(ctx, Choice, lambda e: True)


  @clear.command(help="Clears the messages having embeds")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def embeds(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds))


  @clear.command(help="Clears the messages having files")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def files(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.attachments))

  @clear.command(help="Clears the messages having images")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def images(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))


  @clear.command(name="all", help="Clears all messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _remove_all(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: True)

  @clear.command(help="Clears the messages of a specific user")
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def user(self, ctx, member: discord.Member = commands.parameter(description="The member to purge messages from"), search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)



  @clear.command(help="Clears the messages containing a specifix string")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def contains(self, ctx, *, string: str = commands.parameter(description="The string to search for")):

        await ctx.message.delete()
        if len(string) < 3:
            await ctx.error("The substring length must be at least 3 characters.")
        else:
            await do_removal(ctx, 100, lambda e: string in e.content)

  @clear.command(name="bot", aliases=["bots","b"], help="Clears the messages sent by bot")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _bot(self, ctx, prefix: str = commands.parameter(description="Also delete messages with this prefix", default=None), search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await do_removal(ctx, search, predicate)

  @clear.command(name="emoji", aliases=["emojis"], help="Clears the messages having emojis")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)

  async def _emoji(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return custom_emoji.search(m.content)

        await do_removal(ctx, search, predicate)

  @clear.command(name="reactions", help="Clears the reaction from the messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _reactions(self, ctx, search: int = commands.parameter(description="Number of messages to search", default=100)):

        await ctx.message.delete()

        if search > 2000:
            embed_err = discord.Embed(description=f"Too many messages to search for ({search}/2000)", color=discord.Color.red())
            return await ctx.send(embed=embed_err)

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        embed_success = discord.Embed(description=f"<:CupidXtick1:1474369967271968949> | Successfully removed {total_reactions} reactions.", color=CUPIDX_COLOR)
        await ctx.send(embed=embed_success)
            



  @commands.command(name="purgebots",
                    aliases=["cleanup", "pb", "clearbot", "clearbots"],
                    help="Clear recently bot messages in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _purgebot(self, ctx, prefix: str = commands.parameter(description="Also delete messages with this prefix", default=None), search: int = commands.parameter(description="Number of messages to search", default=100)):

    await ctx.message.delete()

    def predicate(m):
        return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))
      
    await do_removal(ctx, search, predicate)


  @commands.command(name="purgeuser",
                    aliases=["pu", "cu", "clearuser"],
                    help="Clear recent messages of a user in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purguser(self, ctx, member: discord.Member = commands.parameter(description="The member to purge messages from"), search: int = commands.parameter(description="Number of messages to search", default=100)):
      
      await ctx.message.delete()
      await do_removal(ctx, search, lambda e: e.author == member)
