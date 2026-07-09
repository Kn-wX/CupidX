from __future__ import annotations

from core import cupidx

from colorama import Fore, Style, init

init(autoreset=True)

# ---------- Commands ----------
from .commands.vote import Vote
from .commands.autopfp import AutoPFP
from .commands.counting import Counting
from .commands.voicerole import VoiceRole
from .commands.verification import Verification
from .commands.autonick import AutoNick
from .commands.sticky import Sticky
from .commands.youtube import Youtube
from .commands.help import Help
from .commands.join2create import Join2Create
from .commands.general import General
from .commands.automod import Automod
from .commands.welcome import Welcomer
from .commands.fun import Fun
from .commands.fun_extra import FunExtra
from .commands.Games import Games
from .commands.extra import Extra
from .commands.extras import Extras
from .commands.template import Template
from .commands.bugsystem import BugSystem
from .commands.owner import Owner
from .commands.voice import Voice
from .commands.afk import afk
from .commands.ignore import Ignore
from .commands.Media import Media
from .commands.Invc import Invcrole
from .commands.giveaway import Giveaway
from .commands.Embed import Embed
from .commands.steal import Steal
from .commands.ship import Ship
from .commands.timer import Timer
from .commands.blacklist import Blacklist
from .commands.block import Block
from .commands.guildvip import GuildVIP
from .commands.nightmode import Nightmode
from .commands.imagine import AiStuffCog
from .commands.owner import Badges
from .commands.map import Map
from .commands.autoresponder import AutoResponder
from .commands.customrole import Customrole
from .commands.autorole import AutoRole
from .commands.ticket import TicketCog
from .commands.feedback import Feedback
from .commands.logging import Logging
from .commands.translate import TranslateCog
from .commands.jail import Jail
from .commands.antinuke import Antinuke
from .commands.extraown import Extraowner
from .commands.anti_wl import Whitelist
from .commands.anti_unwl import Unwhitelist
from .commands.lockrole import LockRole
from .commands.blackjack import Blackjack
from .commands.autoreact import AutoReaction
from .commands.stats import Stats
from .commands.emergency import Emergency
from .commands.notify import NotifCommands
from .commands.status import Status
from .commands.np import NoPrefix
from .commands.owner2 import Global
from .commands.vanityroles import VanityRoles
from .commands.reactionroles import ReactionRoles
from .commands.np_trial import NPTrial
from .commands.InviteTracker import InviteTracker

from .commands.fastgreet import FastGreet
from .commands.broadcast import Broadcast
from .commands.backup import Backup
from .commands.serverclone import ServerClone
from .commands.premium import Premium
from .commands.healthscan import HealthScan
from .commands.giveaway_schedule import GiveawaySchedule
from .commands.premium_features import PremiumFeatures
from .commands.cmd_logger import CmdLogger
from .commands.modtools import ModTools
from .commands.Music import Music
from .commands.premium_extras import PremiumExtras

# ---------- Events ----------
from .events.autoblacklist import AutoBlacklist
from .events.Errors import Errors
from .events.on_guild import Guild
from .events.autorole import Autorole2
from .events.auto import Autorole
from .events.greet2 import greet
from .events.mention import Mention
from .events.react import React
from .events.autoreact import AutoReactListener
from .events.guild_global_logs import GuildGlobalLogs

# ---------- CupidX Help ----------
from .cupidx.antinuke import _antinuke
from .cupidx.extra import _extra
from .cupidx.general import _general
from .cupidx.automod import _automod
from .cupidx.moderation import _moderation
from .cupidx.fun import _fun
from .cupidx.games import _games
from .cupidx.server import _server
from .cupidx.voice import _voice
from .cupidx.welcome import _welcome
from .cupidx.giveaway import _giveaway
# from .cupidx.ticket import _ticket
from .cupidx.logging import Loggingdrop
from .cupidx.vanity import _vanity
from .cupidx.inviteTracker import _inviteTracker
from .cupidx.join2create import _join2create

# ---------- Antinuke ----------
from .antinuke.anti_member_update import AntiMemberUpdate
from .antinuke.antiban import AntiBan
from .antinuke.antibotadd import AntiBotAdd
from .antinuke.antichcr import AntiChannelCreate
from .antinuke.antichdl import AntiChannelDelete
from .antinuke.antichup import AntiChannelUpdate
from .antinuke.antieveryone import AntiEveryone
from .antinuke.antiguild import AntiGuildUpdate
from .antinuke.antiIntegration import AntiIntegration
from .antinuke.antikick import AntiKick
from .antinuke.antiprune import AntiPrune
from .antinuke.antirlcr import AntiRoleCreate
from .antinuke.antirldl import AntiRoleDelete
from .antinuke.antirlup import AntiRoleUpdate
from .antinuke.antiwebhook import AntiWebhookUpdate
from .antinuke.antiwebhookcr import AntiWebhookCreate
from .antinuke.antiwebhookdl import AntiWebhookDelete
# ⭐ Added missing Antinuke files:
from .antinuke.antiemocr import AntiEmojiCreate
from .antinuke.antiemodl import AntiEmojiDelete
from .antinuke.antiemoup import AntiEmojiUpdate
from .antinuke.antiunban import AntiUnban
from .antinuke.antisticker import AntiSticker
from .antinuke.antiwebhookspam import AntiWebhookSpam

# ---------- Automod ----------
from .automod.antispam import AntiSpam
from .automod.anticaps import AntiCaps
from .automod.antilink import AntiLink
from .automod.anti_invites import AntiInvite
from .automod.anti_mass_mention import AntiMassMention
from .automod.anti_emoji_spam import AntiEmojiSpam

# ---------- Moderation ----------
from .moderation.ban import Ban
from .moderation.unban import Unban
from .moderation.timeout import Mute
from .moderation.unmute import Unmute
from .moderation.lock import Lock
from .moderation.unlock import Unlock
from .moderation.hide import Hide
from .moderation.unhide import Unhide
from .moderation.kick import Kick
from .moderation.warn import Warn
from .moderation.role import Role
from .moderation.message import Message
from .moderation.moderation import Moderation
from .moderation.topcheck import TopCheck
from .moderation.snipe import Snipe


async def setup(bot: cupidx):

    # Commands
    if "Vote" not in bot.cogs:
        await bot.add_cog(Vote(bot))
    if "AutoPFP" not in bot.cogs:
        await bot.add_cog(AutoPFP(bot))
    await bot.add_cog(Counting(bot))
    await bot.add_cog(VoiceRole(bot))
    await bot.add_cog(Verification(bot))
    await bot.add_cog(Sticky(bot))
    await bot.add_cog(AutoNick(bot))
    await bot.add_cog(Youtube(bot))
    await bot.add_cog(Help(bot))  # ensure Help cog is added
    await bot.add_cog(Join2Create(bot))
    await bot.add_cog(General(bot))
    await bot.add_cog(Automod(bot))
    await bot.add_cog(Welcomer(bot))
    await bot.add_cog(Fun(bot))
    await bot.add_cog(FunExtra(bot))
    await bot.add_cog(Games(bot))
    await bot.add_cog(Extra(bot))
    await bot.add_cog(Extras(bot))
    await bot.add_cog(Template(bot))
    await bot.add_cog(BugSystem(bot))
    await bot.add_cog(Voice(bot))
    await bot.add_cog(Owner(bot))
    await bot.add_cog(Customrole(bot))
    await bot.add_cog(afk(bot))
    await bot.add_cog(Embed(bot))
    await bot.add_cog(Media(bot))
    await bot.add_cog(Ignore(bot))
    await bot.add_cog(Invcrole(bot))
    await bot.add_cog(Giveaway(bot))
    await bot.add_cog(Steal(bot))
    await bot.add_cog(Ship(bot))
    await bot.add_cog(Timer(bot))
    await bot.add_cog(Blacklist(bot))
    await bot.add_cog(Block(bot))
    await bot.add_cog(GuildVIP(bot))
    await bot.add_cog(Nightmode(bot))
    await bot.add_cog(Badges(bot))
    await bot.add_cog(AiStuffCog(bot))
    await bot.add_cog(Antinuke(bot))
    await bot.add_cog(Whitelist(bot))
    await bot.add_cog(Unwhitelist(bot))
    await bot.add_cog(LockRole(bot))
    await bot.add_cog(Extraowner(bot))
    await bot.add_cog(Blackjack(bot))
    await bot.add_cog(Stats(bot))
    await bot.add_cog(Emergency(bot))
    await bot.add_cog(Status(bot))
    await bot.add_cog(NoPrefix(bot))
    await bot.add_cog(Global(bot))
    await bot.add_cog(Map(bot))
    await bot.add_cog(TicketCog(bot))
    await bot.add_cog(Feedback(bot))
    await bot.add_cog(Logging(bot))
    await bot.add_cog(VanityRoles(bot))
    await bot.add_cog(InviteTracker(bot))
    await bot.add_cog(ReactionRoles(bot))
    await bot.add_cog(NPTrial(bot))

    await bot.add_cog(TranslateCog(bot))
    await bot.add_cog(FastGreet(bot))
    await bot.add_cog(Jail(bot))
    await bot.add_cog(Broadcast(bot))
    await bot.add_cog(Backup(bot))
    await bot.add_cog(ServerClone(bot))
    await bot.add_cog(Premium(bot))
    await bot.add_cog(HealthScan(bot))
    await bot.add_cog(GiveawaySchedule(bot))
    await bot.add_cog(PremiumFeatures(bot))
    await bot.add_cog(CmdLogger(bot))
    await bot.add_cog(ModTools(bot))
    await bot.add_cog(Music(bot))
    await bot.add_cog(PremiumExtras(bot))


    # CupidX Categories
    await bot.add_cog(_antinuke(bot))
    await bot.add_cog(_extra(bot))
    await bot.add_cog(_general(bot))
    await bot.add_cog(_automod(bot))
    await bot.add_cog(_moderation(bot))
    await bot.add_cog(_fun(bot))
    await bot.add_cog(_games(bot))
    await bot.add_cog(_server(bot))
    await bot.add_cog(_voice(bot))
    await bot.add_cog(_welcome(bot))
    await bot.add_cog(_giveaway(bot))
    # await bot.add_cog(_ticket(bot))
    await bot.add_cog(Loggingdrop(bot))
    await bot.add_cog(_vanity(bot))
    await bot.add_cog(_inviteTracker(bot))
    await bot.add_cog(_join2create(bot))  # ✅ Added missing CupidX cog

    # Events
    await bot.add_cog(AutoBlacklist(bot))
    await bot.add_cog(Guild(bot))
    await bot.add_cog(Errors(bot))
    await bot.add_cog(GuildGlobalLogs(bot))
    await bot.add_cog(Autorole2(bot))
    await bot.add_cog(Autorole(bot))
    await bot.add_cog(greet(bot))
    await bot.add_cog(AutoResponder(bot))
    await bot.add_cog(Mention(bot))
    await bot.add_cog(AutoRole(bot))
    # trash line 
    from .events.react import setup as react_setup
    await react_setup(bot)
    await bot.add_cog(AutoReaction(bot))
    await bot.add_cog(AutoReactListener(bot))
    await bot.add_cog(NotifCommands(bot))

    # ---------- Antinuke ----------
    await bot.add_cog(AntiMemberUpdate(bot))
    await bot.add_cog(AntiBan(bot))
    await bot.add_cog(AntiBotAdd(bot))
    await bot.add_cog(AntiChannelCreate(bot))
    await bot.add_cog(AntiChannelDelete(bot))
    await bot.add_cog(AntiChannelUpdate(bot))
    await bot.add_cog(AntiEveryone(bot))
    await bot.add_cog(AntiGuildUpdate(bot))
    await bot.add_cog(AntiIntegration(bot))
    await bot.add_cog(AntiKick(bot))
    await bot.add_cog(AntiPrune(bot))
    await bot.add_cog(AntiRoleCreate(bot))
    await bot.add_cog(AntiRoleDelete(bot))
    await bot.add_cog(AntiRoleUpdate(bot))
    await bot.add_cog(AntiWebhookUpdate(bot))
    await bot.add_cog(AntiWebhookCreate(bot))
    await bot.add_cog(AntiWebhookDelete(bot))
    # ⭐ Added missing Antinuke files:
    await bot.add_cog(AntiEmojiCreate(bot))
    await bot.add_cog(AntiEmojiDelete(bot))
    await bot.add_cog(AntiEmojiUpdate(bot))
    await bot.add_cog(AntiUnban(bot))
    await bot.add_cog(AntiSticker(bot))
    await bot.add_cog(AntiWebhookSpam(bot))

    # ---------- Automod ----------
    await bot.add_cog(AntiSpam(bot))
    await bot.add_cog(AntiCaps(bot))
    await bot.add_cog(AntiLink(bot))
    await bot.add_cog(AntiInvite(bot))
    await bot.add_cog(AntiMassMention(bot))
    await bot.add_cog(AntiEmojiSpam(bot))

    # ---------- Moderation ----------
    await bot.add_cog(Ban(bot))
    await bot.add_cog(Unban(bot))
    await bot.add_cog(Mute(bot))
    await bot.add_cog(Unmute(bot))
    await bot.add_cog(Lock(bot))
    await bot.add_cog(Unlock(bot))
    await bot.add_cog(Hide(bot))
    await bot.add_cog(Unhide(bot))
    await bot.add_cog(Kick(bot))
    await bot.add_cog(Warn(bot))
    await bot.add_cog(Role(bot))
    await bot.add_cog(Message(bot))
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(TopCheck(bot))
    await bot.add_cog(Snipe(bot))

    print(Fore.BLUE + Style.BRIGHT + "✅ All CupidX Cogs loaded successfully.")
