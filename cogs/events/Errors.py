import discord
import json
import aiosqlite
from discord.ext import commands
from utils.config import serverLink
from core import cupidx, Cog, Context
from utils.Tools import get_ignore_data
from utils.ui_v2 import v2_card
from colorama import Fore, Style

class Errors(Cog):
  def __init__(self, client: cupidx):
    self.client = client

  @commands.Cog.listener()
  async def on_command_error(self, ctx: Context, error):
    if ctx.command is None:
      return

    # Sexy terminal log
    if not isinstance(error, (commands.CommandNotFound, commands.CommandOnCooldown, commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
        print(f"\n{Fore.RED}{Style.BRIGHT} {'═' * 20} COMMAND ERROR {'═' * 20}")
        print(f"{Fore.YELLOW}Command:{Fore.WHITE} {ctx.command}")
        print(f"{Fore.YELLOW}User:   {Fore.WHITE} {ctx.author} ({ctx.author.id})")
        print(f"{Fore.YELLOW}Guild:  {Fore.WHITE} {ctx.guild.name if ctx.guild else 'DMs'}")
        print(f"{Fore.YELLOW}Error:  {Fore.RED}{error}")
        print(f"{Fore.RED}{Style.BRIGHT} {'═' * 55}\n")

    if isinstance(error, commands.CommandNotFound):
      return

    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
      help_text = ctx.command.help or "No description provided"
      aliases = "|".join([ctx.command.name] + ctx.command.aliases)
      
      body = f"**{help_text}**\n\n"
      body += "**Usage:**\n"

      _usage = ctx.command.usage or ctx.command.signature or ""
      _cmd = ctx.command.qualified_name
      # Strip command name from usage to avoid duplication like "mute mute <member>"
      if _usage.startswith(_cmd):
          _usage = _usage[len(_cmd):].strip()
      elif _usage.startswith(ctx.command.name):
          _usage = _usage[len(ctx.command.name):].strip()
      body += f"> `{ctx.prefix}{_cmd} {_usage}`\n\n"

      params = []
      for param_name, param in ctx.command.params.items():
          # skip self, ctx, and hidden params
          if param_name in ["self", "ctx", "args", "kwargs"]:
              continue
          desc = param.description or "No description"
          params.append(f"• `{param_name}` – {desc}")
      
      if params:
          body += "**Arguments:**\n"
          body += "\n".join(params)
      
      view = v2_card(f"Command: {ctx.command.name}", body)
      await ctx.send(view=view)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.CheckFailure):
      data = await get_ignore_data(ctx.guild.id)
      ch = data.get("channel", [])
      iuser = data.get("user", [])
      cmd = data.get("command", [])
      buser = data.get("bypassuser", [])

      if str(ctx.author.id) in buser:
        return

      if str(ctx.channel.id) in ch:
        view = v2_card("Access Denied", f"{ctx.author.mention}, this **channel** is on the **ignored** list. Please try my commands in another channel.")
        await ctx.reply(view=view, delete_after=8)
        return

      if str(ctx.author.id) in iuser:
        view = v2_card("Access Denied", f"{ctx.author.mention}, you are set as an **ignored user** in this guild. You cannot use my commands here.")
        await ctx.reply(view=view, delete_after=8)
        return

      if ctx.command.name in cmd or any(alias in cmd for alias in ctx.command.aliases):
        view = v2_card("Access Denied", f"{ctx.author.mention}, this **command is ignored** in this guild.")
        await ctx.reply(view=view, delete_after=8)
        return

    if isinstance(error, commands.NoPrivateMessage):
      view = v2_card("DMs Disabled", "You cannot use my commands in DMs.")
      await ctx.reply(view=view, delete_after=20)
      return

    if isinstance(error, commands.CommandOnCooldown):
      view = v2_card("Cooldown", f"{ctx.author.mention}, whoa, slow down there! You can run the command again in **{error.retry_after:.2f}** seconds.")
      await ctx.reply(view=view, delete_after=10)
      return

    if isinstance(error, commands.MaxConcurrencyReached):
      view = v2_card("Command In Progress", f"{ctx.author.mention}, this command is already in progress. Please let it finish first.")
      await ctx.reply(view=view, delete_after=10)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.MissingPermissions):
      missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
      fmt = "{}, and {}".format(", ".join(missing[:-1]), missing[-1]) if len(missing) > 2 else " and ".join(missing)
      view = v2_card("Missing Permissions", f"You lack the **{fmt}** Permission to run the **{ctx.command.name}** command!")
      await ctx.reply(view=view, delete_after=7)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.BotMissingPermissions):
      missing = ", ".join(error.missing_permissions)
      view = v2_card("Bot Missing Permissions", f"I need the **{missing}** Permission to run the **{ctx.command.qualified_name}** command!")
      await ctx.reply(view=view, delete_after=7)
      return

    if isinstance(error, (discord.HTTPException, commands.CommandInvokeError)):
      return
