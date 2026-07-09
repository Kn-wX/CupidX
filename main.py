import os
import asyncio

import aiohttp
import discord
from discord.ext import commands

from core import Context
from core.Cog import Cog
from core.cupidx import cupidx
from utils.Tools import *
from utils.config import *
from colorama import Fore, Style, init
import logging

logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.http').setLevel(logging.ERROR)
logging.getLogger('discord.client').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('wavelink').setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s: %(message)s'
)

init(autoreset=True)

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_IDS = os.getenv("OWNER_IDS")

client = cupidx()

if OWNER_IDS:
    client.owner_ids = {
        int(x.strip())
        for x in OWNER_IDS.split(",")
        if x.strip().isdigit()
    }
else:
    client.owner_ids = {1378341015181856768, 1086563807314313266}

tree = client.tree
client.remove_command("help")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 1: on_ready baar baar fire hota hai reconnect pe
#         _ready_done flag se sirf pehli baar kaam hoga
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ready_done = False


@client.event
async def on_ready():
    global _ready_done
    if _ready_done:
        print(f"{Fore.YELLOW}{Style.BRIGHT}  🔁 Reconnected to Discord (skipping re-sync)")
        return
    _ready_done = True
    
    from utils.emoji_sync import run_sync
    run_sync(TOKEN)

    banner = f"""{Fore.RED}{Style.BRIGHT}
  ██████╗██╗   ██╗██████╗ ██╗██████╗ ██╗  ██╗
 ██╔════╝██║   ██║██╔══██╗██║██╔══██╗╚██╗██╔╝
 ██║     ██║   ██║██████╔╝██║██║  ██║ ╚███╔╝ 
 ██║     ██║   ██║██╔═══╝ ██║██║  ██║ ██╔██╗ 
 ╚██████╗╚██████╔╝██║     ██║██████╔╝██╔╝ ██╗
  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝
{Fore.YELLOW}                  Made by Mr.X
    """
    print(banner)
    print(f"{Fore.RED}{Style.BRIGHT} {'═' * 50}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}  ✨ {Fore.WHITE}CupidX is Online & Ready!")
    print(f"{Fore.RED}{Style.BRIGHT} {'═' * 50}")
    print(f"{Fore.RED}{Style.BRIGHT}  👤 {Fore.WHITE}Bot User: {Fore.GREEN}{client.user}")
    print(f"{Fore.RED}{Style.BRIGHT}  🆔 {Fore.WHITE}Bot ID:   {Fore.GREEN}{client.user.id}")
    print(f"{Fore.RED}{Style.BRIGHT}  🌐 {Fore.WHITE}Guilds:   {Fore.GREEN}{len(client.guilds)}")
    print(f"{Fore.RED}{Style.BRIGHT}  👥 {Fore.WHITE}Users:    {Fore.GREEN}{len(client.users)}")
    print(f"{Fore.RED}{Style.BRIGHT}  🎧 {Fore.WHITE}Intents:  {Fore.GREEN}Voice: {client.intents.voice_states}, Members: {client.intents.members}, Presence: {client.intents.presences}")
    try:
        import nacl
        print(f"{Fore.RED}{Style.BRIGHT}  🛡️ {Fore.WHITE}PyNaCl:   {Fore.GREEN}Installed & Found")
    except ImportError:
        print(f"{Fore.RED}{Style.BRIGHT}  ❌ {Fore.WHITE}PyNaCl:   {Fore.RED}NOT FOUND (CRITICAL FOR VOICE)")
    print(f"{Fore.RED}{Style.BRIGHT} {'═' * 50}")

    print(f"\n{Fore.RED}{Style.BRIGHT} {'╔' + '═' * 48 + '╗'}")
    print(f"{Fore.RED}{Style.BRIGHT} ║{Fore.YELLOW}{Style.BRIGHT}  📦 LOADED MODULES & COMMANDS{' ' * 17}{Fore.RED}║")
    print(f"{Fore.RED}{Style.BRIGHT} {'╚' + '═' * 48 + '╝'}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIX 2: walk_commands() ek baar — result list mein store
    #         Pehle baar baar loop hota tha — ab nahi hoga
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    all_commands = list(client.walk_commands())
    total_cogs = len(client.cogs)
    total_commands = len(all_commands)

    print(f"\n{Fore.RED}{Style.BRIGHT}  📊 {Fore.WHITE}Statistics:")
    print(f"{Fore.RED}{Style.BRIGHT}     ├─ {Fore.WHITE}Total Cogs:     {Fore.GREEN}{total_cogs}")
    print(f"{Fore.RED}{Style.BRIGHT}     └─ {Fore.WHITE}Total Commands: {Fore.GREEN}{total_commands}")

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}  ⭐ {Fore.WHITE}New Modules Created Today:")
    new_modules = [
        ("Backup",  "Server backup & restore system"),
        ("Premium", "Premium features management"),
        ("Music",   "Enhanced music commands"),
        ("Owner",   "Updated owner commands")
    ]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIX 3: Har cog ke get_commands() ka result cache karo
    #         Pehle har print pe naya loop chalta tha
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    cog_cmd_cache = {
        name: list(cog.get_commands())
        for name, cog in client.cogs.items()
    }

    for module_name, description in new_modules:
        if module_name in cog_cmd_cache:
            cmd_count = len(cog_cmd_cache[module_name])
            print(f"{Fore.GREEN}{Style.BRIGHT}     ✓ {Fore.RED}{module_name:<15} {Fore.WHITE}{description:<30} {Fore.YELLOW}[{cmd_count} cmds]")
        else:
            print(f"{Fore.RED}{Style.BRIGHT}     ✗ {Fore.RED}{module_name:<15} {Fore.WHITE}{description}")

    print(f"\n{Fore.RED}{Style.BRIGHT}  📚 {Fore.WHITE}All Loaded Cogs:")

    categories = {
        "🛡️ Moderation":    ["Moderation", "Ban", "Unban", "Mute", "Unmute", "Kick", "Warn", "Lock", "Unlock", "Hide", "Unhide"],
        "🔒 Security":       ["Antinuke", "Whitelist", "Unwhitelist", "Emergency", "Blacklist", "Block"],
        "🤖 Automation":     ["AutoRole", "AutoPFP", "AutoNick", "AutoReaction", "AutoResponder", "AutoReactListener"],
        "💎 Premium":        ["Premium", "Backup"],
        "🎮 Fun & Games":    ["Fun", "Games", "Slots", "Blackjack", "Ship"],
        "⚙️ Utility":        ["General", "Help", "Extra", "Timer", "Translate", "QR", "Stats"],
        "👋 Welcome System": ["Welcomer", "FastGreet", "greet"],
        "🎁 Giveaway":       ["Giveaway"],
        "🎫 Tickets":        ["TicketSystem"],
        "👑 Owner":          ["Owner", "Badges", "Global", "Extraowner"],
    }

    categorized_cogs = set()
    for category, cog_names in categories.items():
        loaded_in_category = [name for name in cog_names if name in cog_cmd_cache]
        if loaded_in_category:
            categorized_cogs.update(loaded_in_category)
            print(f"\n{Fore.RED}{Style.BRIGHT}  {category}")
            for cog_name in loaded_in_category:
                cmd_count = len(cog_cmd_cache[cog_name])
                print(f"{Fore.GREEN}{Style.BRIGHT}     ├─ {Fore.RED}{cog_name:<20} {Fore.YELLOW}[{cmd_count} commands]")

    uncategorized = [name for name in client.cogs.keys() if name not in categorized_cogs]
    if uncategorized:
        print(f"\n{Fore.RED}{Style.BRIGHT}  🔧 Other")
        for cog_name in sorted(uncategorized):
            cmd_count = len(cog_cmd_cache.get(cog_name, []))
            print(f"{Fore.GREEN}{Style.BRIGHT}     ├─ {Fore.RED}{cog_name:<20} {Fore.YELLOW}[{cmd_count} commands]")

    print(f"\n{Fore.RED}{Style.BRIGHT} {'═' * 50}")
    print(f"{Fore.GREEN}{Style.BRIGHT}  ✅ {Fore.WHITE}All systems operational!")
    print(f"{Fore.RED}{Style.BRIGHT} {'═' * 50}\n")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIX 4: Sync se pehle 3 sec delay — SABSE BADA FIX
    #         Discord startup pe already heavily loaded hota hai
    #         Bina delay ke sync = guaranteed 429
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    await asyncio.sleep(3)
    try:
        synced = await client.tree.sync()
        print(f"{Fore.GREEN}{Style.BRIGHT}  🔄 {Fore.WHITE}Slash Commands Synced: {Fore.GREEN}{len(synced)} commands globally")
    except discord.HTTPException as e:
        print(f"{Fore.RED}{Style.BRIGHT}  ❌ {Fore.WHITE}Slash Sync Failed (HTTP {e.status}): {Fore.RED}{e.text}")
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}  ❌ {Fore.WHITE}Slash Sync Failed: {Fore.RED}{e}")


# ── Prefix sync command ──────────────────────────────────────────────────────
@client.command(name="sync")
@commands.is_owner()
async def sync_cmd(ctx: commands.Context, scope: str = "global"):
    """
    Sync slash commands.
      !sync          — sync globally
      !sync guild    — sync to this guild instantly (testing)
      !sync clear    — clear all global slash commands
    """
    if scope == "guild":
        if ctx.guild is None:
            return await ctx.send("Run this in a server to do a guild sync.")
        client.tree.copy_global_to(guild=ctx.guild)
        synced = await client.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Guild-synced {len(synced)} slash commands to **{ctx.guild.name}** (instant).")
    elif scope == "clear":
        client.tree.clear_commands(guild=None)
        await client.tree.sync()
        await ctx.send("🗑️ Cleared all global slash commands.")
    else:
        synced = await client.tree.sync()
        await ctx.send(f"✅ Globally synced {len(synced)} slash commands (may take up to 1 hour).")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 5: Webhook log — pehle har command pe naya
#         aiohttp.ClientSession khulta aur band hota tha
#         Ye bahut expensive + rate limit friendly nahi tha
#         Ab ek shared session use hoga poore bot ke liye
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_webhook_session: aiohttp.ClientSession | None = None


async def get_webhook_session() -> aiohttp.ClientSession:
    global _webhook_session
    if _webhook_session is None or _webhook_session.closed:
        _webhook_session = aiohttp.ClientSession()
    return _webhook_session


@client.event
async def on_command_completion(context: commands.Context):
    if context.author.bot:
        return

    webhook_url = os.getenv("COMMAND_LOG_WEBHOOK")
    if not webhook_url:
        return

    command_name = context.command.qualified_name
    user    = context.author
    guild   = context.guild
    channel = context.channel

    avatar_url   = user.display_avatar.url
    user_link    = f"https://discord.com/users/{user.id}"
    channel_link = f"https://discord.com/channels/{guild.id}/{channel.id}" if guild else "N/A"
    server_link  = f"https://discord.com/channels/{guild.id}" if guild else "N/A"

    embed = discord.Embed(
        title="<a:CupidXloading:1474386958741536891> CupidX Log System",
        color=0x000000
    )
    embed.set_author(name=str(user), icon_url=avatar_url)
    embed.add_field(name="<a:emojisetting:1476854070412316713> Command", value=f"`{command_name}`", inline=False)
    embed.add_field(name="<:CupidXuser:1475151935379341382> User",        value=f"[{user}]({user_link})\n`ID: {user.id}`", inline=False)
    embed.add_field(name="<:CupidXBots:1475367184854290584> Server",      value=f"[{guild.name}]({server_link})\n`ID: {guild.id}`" if guild else "DM", inline=False)
    embed.add_field(name="<:CupidXCommands:1475152376737566722> Channel", value=f"[Jump to Channel]({channel_link})", inline=False)
    embed.set_thumbnail(url=avatar_url)
    embed.timestamp = discord.utils.utcnow()

    try:
        session = await get_webhook_session()
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        await webhook.send(embed=embed)
    except Exception:
        pass


# ── Main entry ────────────────────────────────────────────
async def main():
    async with client:
        os.system("cls" if os.name == "nt" else "clear")

        print(f"{Fore.RED}{Style.BRIGHT} ❯ {Fore.WHITE}Starting CupidX...")
        print(f"{Fore.RED}{Style.BRIGHT} ❯ {Fore.WHITE}discord.py version: {Fore.GREEN}{discord.__version__}")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # FIX 6: JSK load ke baad 1 sec ruko
        #         Fir cogs load ke baad aur 1 sec ruko
        #         Phir connect — ye startup burst avoid karta hai
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            await client.load_extension("jishaku")
            print(f"{Fore.GREEN}JSK Loaded Successfully")
        except Exception as e:
            print(f"{Fore.RED}JSK Load Failed: {e}")

        await asyncio.sleep(1)

        print(f"{Fore.RED}{Style.BRIGHT} ❯ {Fore.WHITE}Loading Extensions...")
        if "cogs" not in client.extensions:
            try:
                await client.load_extension("cogs")
            except Exception as e:
                print(f"{Fore.RED} ❌ Cogs Load Failed: {e}")
        else:
            print(f"{Fore.YELLOW} ⚠️ Cogs already loaded — skipping.")

        await asyncio.sleep(1)

        if not TOKEN:
            print(f"{Fore.RED}{Style.BRIGHT} ❌ TOKEN not found in .env! Bot cannot start.")
            return

        try:
            await client.start(TOKEN)
        except discord.LoginFailure:
            print(f"{Fore.RED}{Style.BRIGHT} ❌ Invalid TOKEN — check your .env file.")
        except Exception as e:
            print(f"\n{Fore.RED}{Style.BRIGHT} {'═' * 20} STARTUP FAILURE {'═' * 20}")
            print(f"{Fore.YELLOW}Reason: {Fore.RED}{e}")
            print(f"{Fore.RED}{Style.BRIGHT} {'═' * 55}\n")
        finally:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # FIX 7: Bot band hone pe shared webhook session close karo
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if _webhook_session and not _webhook_session.closed:
                await _webhook_session.close()


if __name__ == "__main__":
    asyncio.run(main())
))
