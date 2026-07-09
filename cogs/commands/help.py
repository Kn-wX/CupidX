import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import datetime
from utils.config import OWNER_IDS, WEBSITE, SUPPORT_SERVER, BOT_INVITE
from utils.detectfile import *

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# BANNER_URL imported from utils.detectfile
BOT_COLOR  = 0x000000

# ══════════════════════════════════════════════════════════════════════════════
#  EMOJIS
# ══════════════════════════════════════════════════════════════════════════════
E = {
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "premium":  EMOJI_DIAMOND,
    "tick":     EMOJI_TICK,
    "cross":    EMOJI_CROSS,
    "shield":   EMOJI_SHIELD,
    "settings": "<:cog:1487152125069889677>",
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "fire":     EMOJI_FIRE,
    "bot":      EMOJI_ROBOT,
    "user":     EMOJI_USER,
    "link":     EMOJI_BOND2,
    "timer":    EMOJI_TIMER2,
    "loading":  EMOJI_LOADING,
    "gift":     EMOJI_GIFT,
    "lock":     EMOJI_KEY,
    "chat":     EMOJI_APP2,
    "home":     EMOJI_UTILITY4B,
}

# ══════════════════════════════════════════════════════════════════════════════
#  MODULES — Each module = one page
#  Format per command: ("command_name", "short description")
# ══════════════════════════════════════════════════════════════════════════════
MODULES = [
    {
        "key":   "security",
        "emoji": EMOJI_SHIELD,
        "name":  "Security",
        "desc":  "Antinuke, whitelist & emergency tools",
        "info":  "Real-time protection against nukes, raids and unauthorized admin actions.",
        "commands": [
            ("antinuke",               "Show antinuke panel & current settings"),
            ("antinuke enable",        "Enable full server antinuke protection"),
            ("antinuke disable",       "Disable antinuke protection"),
            ("whitelist",              "Show whitelist panel"),
            ("whitelist add",          "Add a user to the whitelist"),
            ("whitelist remove",       "Remove a user from whitelist"),
            ("whitelisted",            "View all whitelisted users"),
            ("whitelistreset",         "Reset & clear the entire whitelist"),
            ("unwhitelist",            "Quickly unwhitelist a user"),
            ("extraowner",             "Grant owner-level trust to a user"),
            ("nightmode",              "Auto-lock server during off-hours"),
            ("emergency",              "Show emergency panel"),
            ("emergency enable",       "Enable emergency lockdown mode"),
            ("emergency disable",      "Disable emergency lockdown mode"),
            ("emergency authorise",    "Authorise a user during emergency"),
            ("emergency role add",     "Add a role to emergency access"),
            ("emergency role remove",  "Remove a role from emergency access"),
            ("emergencysituation",     "Trigger an emergency situation manually"),
            ("emergencyrestore",       "Restore server after emergency"),
            ("blacklist user add",     "Blacklist a user from using the bot"),
            ("blacklist user remove",  "Remove a user from blacklist"),
            ("blacklist guild add",    "Blacklist an entire guild"),
            ("blacklist guild remove", "Remove a guild from blacklist"),
            ("dangerperms",            "Show all members with dangerous permissions"),
        ],
    },
    {
        "key":   "automod",
        "emoji": EMOJI_HEADPHONE,
        "name":  "Automod",
        "desc":  "Auto-moderate spam, links and banned words",
        "info":  "Automatically detect & punish spam, links, mass mentions and blacklisted words.",
        "commands": [
            ("automod",                     "Show automod panel & status"),
            ("automod enable",              "Enable the automod system"),
            ("automod disable",             "Disable the automod system"),
            ("automod punishment",          "Set the punishment (warn/mute/ban)"),
            ("automod logging",             "Set log channel for violations"),
            ("automod config",              "View full automod configuration"),
            ("automod ignore channel",      "Exclude a channel from automod"),
            ("automod ignore role",         "Exclude a role from automod"),
            ("automod unignore channel",    "Re-enable automod in a channel"),
            ("automod unignore role",       "Re-enable automod for a role"),
            ("blacklistword add",           "Add a word to the blacklist filter"),
            ("blacklistword remove",        "Remove a word from blacklist filter"),
            ("blacklistword reset",         "Clear all blacklisted words"),
            ("blacklistword config",        "View blacklisted words list"),
            ("blacklistword bypass add",    "Allow a user to bypass word filter"),
            ("blacklistword bypass remove", "Remove a user's bypass permission"),
        ],
    },
    {
        "key":   "moderation",
        "emoji": EMOJI_PROFILE,
        "name":  "Moderation",
        "desc":  "Ban, kick, mute, warn & more",
        "info":  "Full moderation suite with ban, kick, mute, warn and message management.",
        "commands": [
            ("ban",              "Ban a member from the server"),
            ("unban",            "Unban a previously banned user"),
            ("unbanall",         "Unban all banned users at once"),
            ("kick",             "Kick a member from the server"),
            ("mute",             "Mute a member (timeout)"),
            ("unmute",           "Unmute/remove timeout from member"),
            ("warn",             "Warn a member and log it"),
            ("clearwarns",       "Clear all warnings for a member"),
            ("role",             "Add/remove a role from a member"),
            ("role temp",        "Temporarily assign a role with timer"),
            ("role create",      "Create a new role"),
            ("role delete",      "Delete an existing role"),
            ("role rename",      "Rename an existing role"),
            ("role humans",      "Give a role to all human members"),
            ("role bots",        "Give a role to all bots"),
            ("role all",         "Give a role to everyone"),
            ("role unverified",  "Give a role to unverified members"),
            ("removerole humans","Remove a role from all humans"),
            ("removerole bots",  "Remove a role from all bots"),
            ("removerole all",   "Remove a role from everyone"),
            ("nick",             "Change a member's nickname"),
            ("clear",            "Delete recent messages in channel"),
            ("clear all",        "Clear all messages in channel"),
            ("clear user",       "Clear messages from a specific user"),
            ("clear bot",        "Clear bot messages only"),
            ("clear embeds",     "Clear messages with embeds only"),
            ("clear files",      "Clear messages with files only"),
            ("clear images",     "Clear messages with images only"),
            ("clear contains",   "Clear messages containing a word"),
            ("purgebots",        "Purge all bot messages in channel"),
            ("purgeuser",        "Purge messages from a specific user"),
            ("snipe",            "Show last deleted message"),
            ("esnipe",           "Show last edited message in channel"),
            ("audit",            "View recent audit log entries"),
            ("steal",            "Steal an emoji from another server"),
            ("delemoji",         "Delete an emoji from server"),
            ("delsticker",       "Delete a sticker from server"),
            ("roleicon",         "Set an icon for a role"),
            ("topcheck",         "Show topcheck panel"),
            ("topcheck enable",  "Enable top role permission check"),
            ("topcheck disable", "Disable top role permission check"),
        ],
    },
    {
        "key":   "extra_mod",
        "emoji": EMOJI_USE,
        "name":  "Extra Mod",
        "desc":  "Locks, hides, nuke, clone & extras",
        "info":  "Channel control — locks, hides, nuke, clone, slowmode, jail and more.",
        "commands": [
            ("lock",        "Lock a channel — no one can send messages"),
            ("unlock",      "Unlock a previously locked channel"),
            ("lockall",     "Lock all channels in the server"),
            ("unlockall",   "Unlock all channels in the server"),
            ("hide",        "Hide a channel from everyone"),
            ("unhide",      "Unhide a hidden channel"),
            ("hideall",     "Hide all channels in the server"),
            ("unhideall",   "Unhide all channels in the server"),
            ("nuke",        "Delete & instantly recreate the channel"),
            ("clone",       "Clone/copy a channel with same settings"),
            ("slowmode",    "Set slowmode delay in a channel"),
            ("unslowmode",  "Remove slowmode from a channel"),
            ("jail",        "Jail a member (restrict to jail channel)"),
            ("unjail",      "Release a member from jail"),
            ("jailsetup",   "Setup the jail channel & role"),
            ("jailhistory", "View jail history of a member"),
            ("prefix",      "Change the bot's command prefix"),
            ("enlarge",     "Enlarge an emoji as full image"),
            ("embed",       "Send a custom embed message"),
            ("rejoinrole",        "Show rejoin role panel"),
            ("rejoinrole add",    "Add a role to give members on rejoin"),
            ("rejoinrole remove", "Remove a role from rejoin list"),
            ("rejoinrole show",   "Show all configured rejoin roles"),
        ],
    },
    {
        "key":   "rolesystem",
        "emoji": EMOJI_ROLE,
        "name":  "Role System",
        "desc":  "Autorole, reaction & custom roles",
        "info":  "Autorole, reaction roles, custom roles, vanity roles and auto-nick.",
        "commands": [
            ("autorole",               "Show autorole panel"),
            ("autorole config",        "View autorole configuration"),
            ("autorole reset",         "Reset all autorole settings"),
            ("autorole humans add",    "Add autorole for human members"),
            ("autorole humans remove", "Remove autorole for human members"),
            ("autorole bots add",      "Add autorole for bots"),
            ("autorole bots remove",   "Remove autorole for bots"),
            ("autorole all",           "Add autorole for everyone"),
            ("react add",              "Add a reaction role to a message"),
            ("react remove",           "Remove a reaction role"),
            ("react list",             "List all reaction roles"),
            ("react reset",            "Reset all reaction roles"),
            ("createrr",               "Create a reaction role panel"),
            ("dmrr",                   "DM a reaction role panel to a user"),
            ("setup staff",            "Setup the staff role"),
            ("setup girl",             "Setup the girl role"),
            ("setup vip",              "Setup the VIP role"),
            ("setup guest",            "Setup the guest role"),
            ("setup friend",           "Setup the friend role"),
            ("customrole setup",       "Setup custom role system"),
            ("customrole config",      "View custom role configuration"),
            ("customrole create",      "Create a personal custom role"),
            ("customrole delete",      "Delete a personal custom role"),
            ("customrole list",        "List all custom roles"),
            ("customrole reset",       "Reset all custom roles"),
            ("vanityroles",            "Show vanity roles panel"),
            ("vanityroles setup",      "Setup vanity role with a keyword"),
            ("vanityroles show",       "Show all vanity role setups"),
            ("vanityroles reset",      "Reset all vanity roles"),
            ("reqrole",                "Require a role to use the bot"),
            ("autonick",               "Show autonick panel"),
            ("autonick setup",         "Setup auto-nickname for members"),
            ("autonick config",        "View autonick configuration"),
            ("autonick reset",         "Reset all autonick settings"),
        ],
    },
    {
        "key":   "logging",
        "emoji": EMOJI_SHUFFLE,
        "name":  "Logging",
        "desc":  "Track all server events",
        "info":  "Log every server event — bans, kicks, edits, role changes and more.",
        "commands": [
            ("loggingsetup", "Configure log channels for all server events"),
            ("removelogs",   "Remove & clear all logging configuration"),
        ],
    },
    {
        "key":   "giveaways",
        "emoji": EMOJI_STARS,
        "name":  "Giveaways",
        "desc":  "Create & manage giveaways",
        "info":  "Create, manage, schedule and reroll giveaways with ease.",
        "commands": [
            ("gstart",    "Start a new giveaway"),
            ("gend",      "End a giveaway early"),
            ("greroll",   "Reroll a giveaway winner"),
            ("glist",     "List all active giveaways"),
            ("gschedule", "Schedule a giveaway for later — Premium"),
            ("gsgend",    "End a scheduled giveaway — Premium"),
            ("gsreroll",  "Reroll a scheduled giveaway — Premium"),
            ("glstart",   "Start a cross-server global giveaway — Premium"),
        ],
    },
    {
        "key":   "verification",
        "emoji": EMOJI_UTILITY8,
        "name":  "Verification",
        "desc":  "Member verification system",
        "info":  "Protect your server from bots with button or CAPTCHA verification.",
        "commands": [
            ("verification",         "Show verification panel & status"),
            ("verification enable",  "Enable the verification system"),
            ("verification disable", "Disable the verification system"),
            ("verification message", "Set the verification message"),
            ("verification button",  "Customise the verify button text/style"),
            ("verification stats",   "View verified member count & stats"),
        ],
    },
    {
        "key":   "voice",
        "emoji": EMOJI_ANNOUNCE,
        "name":  "Voice",
        "desc":  "Full voice channel management",
        "info":  "Full voice channel management — complete VC control.",
        "commands": [
            ("voice kick",        "Kick a member from voice channel"),
            ("voice kickall",     "Kick all members from voice channel"),
            ("voice mute",        "Mute a member in voice channel"),
            ("voice unmute",      "Unmute a member in voice channel"),
            ("voice muteall",     "Mute everyone in the voice channel"),
            ("voice unmuteall",   "Unmute everyone in the voice channel"),
            ("voice deafen",      "Deafen a member in voice channel"),
            ("voice undeafen",    "Undeafen a member in voice channel"),
            ("voice deafenall",   "Deafen all members in voice channel"),
            ("voice undeafenall", "Undeafen all members in voice channel"),
            ("voice move",        "Move a member to another VC"),
            ("voice moveall",     "Move all members to another VC"),
            ("voice pull",        "Pull a member into your VC"),
            ("voice pullall",     "Pull all members into your VC"),
            ("voice lock",        "Lock voice channel — no new joins"),
            ("voice unlock",      "Unlock the voice channel"),
            ("voice private",     "Make voice channel private"),
            ("voice unprivate",   "Make voice channel public again"),
            ("vcrole",            "Auto-assign role on VC join"),
        ],
    },
    {
        "key":   "voice_roles",
        "emoji": EMOJI_SYSTEM,
        "name":  "Voice Roles",
        "desc":  "Roles on voice join/leave",
        "info":  "Automatically assign/remove roles when members join or leave voice channels.",
        "commands": [
            ("voicerole bot add",      "Add role for bots when joining VC"),
            ("voicerole bot remove",   "Remove bot voice role"),
            ("voicerole bot list",     "List all bot voice roles"),
            ("voicerole human add",    "Add role for humans when joining VC"),
            ("voicerole human remove", "Remove human voice role"),
            ("voicerole human list",   "List all human voice roles"),
            ("voicerole reset",        "Reset all voice role settings"),
        ],
    },
    {
        "key":   "autorespond",
        "emoji": EMOJI_ROBOT2,
        "name":  "AR / React",
        "desc":  "Automated responses & reactions",
        "info":  "Auto-responses, auto-reactions and fast-greet for specific trigger words.",
        "commands": [
            ("autoresponder create", "Create a new auto-response trigger"),
            ("autoresponder delete", "Delete an auto-response trigger"),
            ("autoresponder edit",   "Edit an existing auto-response"),
            ("autoresponder config", "View all auto-response configurations"),
            ("autoreact add",        "Add an auto-reaction to a trigger"),
            ("autoreact remove",     "Remove an auto-reaction"),
            ("autoreact list",       "List all auto-reactions"),
            ("autoreact reset",      "Reset all auto-reactions"),
            ("fastgreet add",        "Add a fast-greet for a member on join"),
            ("fastgreet remove",     "Remove a fast-greet"),
            ("fastgreet list",       "List all fast-greet setups"),
        ],
    },
    {
        "key":   "invite_tracker",
        "emoji": EMOJI_ADD,
        "name":  "Invite Tracker",
        "desc":  "Track invites & leaderboard",
        "info":  "Track who invited whom, manage invite counts and view a leaderboard.",
        "commands": [
            ("inviteenable",       "Enable invite tracking"),
            ("invitedisable",      "Disable invite tracking"),
            ("invites",            "View a member's invite count"),
            ("inviteleaderboard",  "Show top inviters leaderboard"),
            ("resetinvites",       "Reset invites for a member"),
            ("resetserverinvites", "Reset all server invite counts"),
            ("addinvites",         "Manually add invites to a member"),
            ("removeinvites",      "Manually remove invites from a member"),
        ],
    },
    {
        "key":   "general",
        "emoji": EMOJI_USE,
        "name":  "General",
        "desc":  "Server info, user info & utilities",
        "info":  "Server info, user info, stats and everyday utility commands.",
        "commands": [
            ("botinfo",      "Show bot information & stats"),
            ("stats",        "Show detailed bot statistics"),
            ("ping",         "Check bot latency / ping"),
            ("uptime",       "Show how long bot has been online"),
            ("serverinfo",   "Show detailed server information"),
            ("servericon",   "Show server icon in full size"),
            ("serverbanner", "Show server banner in full size"),
            ("userinfo",     "Show detailed info about a user"),
            ("avatar",       "Show a user's avatar in full size"),
            ("userbanner",   "Show a user's banner in full size"),
            ("roleinfo",     "Show detailed info about a role"),
            ("channelinfo",  "Show detailed info about a channel"),
            ("vcinfo",       "Show info about a voice channel"),
            ("membercount",  "Show total member count"),
            ("boostcount",   "Show total server boost count"),
            ("boosters",     "List all server boosters"),
            ("badges",       "Show badges of a user"),
            ("banner",       "Show bot banner"),
            ("invite",       "Get bot invite link"),
            ("poll",         "Create a poll in a channel"),
            ("permissions",  "Check a member's permissions"),
            ("joined-at",    "Show when a member joined the server"),
            ("inrole",       "List all members with a specific role"),
            ("roles",        "List all server roles"),
            ("bots",         "List all bots in the server"),
            ("admins",       "List all admins in the server"),
            ("moderators",   "List all moderators in the server"),
            ("emojis",       "List all server emojis"),
            ("bans",         "List all banned members"),
            ("reminder",     "Set a reminder — bot will DM you"),
            ("timer",        "Start a countdown timer"),
        ],
    },
    {
        "key":   "utility",
        "emoji": EMOJI_WARN2,
        "name":  "Utility",
        "desc":  "Extra utility tools & info commands",
        "info":  "Extra utility tools — translate, QR, AFK, ship, notify and no-prefix.",
        "commands": [
            ("translate",           "Translate text to another language"),
            ("hinglish",            "Convert English text to Hinglish"),
            ("qr",                  "Generate a QR code for any text/URL"),
            ("map",                 "Search a location on map"),
            ("urban",               "Search Urban Dictionary"),
            ("search",              "Search the web"),
            ("google",              "Google search within Discord"),
            ("github",              "Search GitHub repos & users"),
            ("afk",                 "Set AFK status with a message"),
            ("ship",                "Check compatibility between two users"),
            ("shiphelp",            "Show ship command help"),
            ("broadcast",           "Broadcast a message to all servers"),
            ("np add",              "Add a no-prefix user"),
            ("np remove",           "Remove a no-prefix user"),
            ("np list",             "List all no-prefix users"),
            ("np status",           "Check no-prefix status"),
            ("autonp guild add",    "Add auto no-prefix for a guild"),
            ("autonp guild remove", "Remove auto no-prefix for a guild"),
            ("autonp guild list",   "List guilds with auto no-prefix"),
            ("npclaim",             "Claim no-prefix in a server"),
            ("notify",              "Show notify panel"),
            ("notify twitch",       "Set Twitch stream notification"),
            ("notify youtube",      "Set YouTube upload notification"),
            ("notify list",         "List all notifications set"),
            ("notify reset",        "Reset all notification settings"),
            ("report",              "Report a bug or issue to developers"),
            ("birthday",            "Show birthday system panel"),
            ("birthday set",        "Set your birthday (DD/MM format)"),
            ("birthday remove",     "Remove your birthday from server"),
            ("birthday list",       "List all server birthdays"),
            ("birthday config",     "Set announce channel & optional role"),
        ],
    },
    {
        "key":   "counting",
        "emoji": EMOJI_TIMER2,
        "name":  "Counting",
        "desc":  "Counting channel with rewards",
        "info":  "Counting channel with milestones, leaderboard and role rewards.",
        "commands": [
            ("count setchannel",    "Set the counting channel"),
            ("count enable",        "Enable the counting system"),
            ("count disable",       "Disable the counting system"),
            ("count setstart",      "Set the starting number"),
            ("count reset",         "Reset the count back to start"),
            ("count status",        "Show current count status"),
            ("count reward add",    "Add a role reward at a milestone"),
            ("count reward remove", "Remove a milestone role reward"),
            ("count reward list",   "List all milestone rewards"),
            ("count leaderboard",   "Show top counters leaderboard"),
            ("count logs",          "View counting log history"),
            ("count fix",           "Fix a broken counting channel"),
        ],
    },
    {
        "key":   "autopfp",
        "emoji": EMOJI_USER,
        "name":  "AutoPFP / Sticky",
        "desc":  "Auto profile pictures & sticky msgs",
        "info":  "Auto-rotate bot profile picture and sticky messages in channels.",
        "commands": [
            ("autopfp enable",   "Enable auto profile picture rotation"),
            ("autopfp disable",  "Disable auto profile picture rotation"),
            ("autopfp interval", "Set how often the pfp rotates"),
            ("sticky",           "Set a sticky message in a channel"),
        ],
    },
    {
        "key":   "fun",
        "emoji": EMOJI_LIGHT,
        "name":  "Fun",
        "desc":  "Social, memes & entertainment",
        "info":  "Social actions, memes, random facts and entertainment commands.",
        "commands": [
            ("hug",          "Send a hug to a member"),
            ("kiss",         "Send a kiss to a member"),
            ("pat",          "Pat a member"),
            ("cuddle",       "Cuddle a member"),
            ("slap",         "Slap a member"),
            ("tickle",       "Tickle a member"),
            ("spank",        "Spank a member"),
            ("kill",         "Virtually kill a member"),
            ("howgay",       "Check how gay someone is (fun)"),
            ("lesbian",      "Check lesbian percentage (fun)"),
            ("chutiya",      "Rate someone (fun)"),
            ("tharki",       "Check tharki level (fun)"),
            ("horny",        "Check horny level (fun)"),
            ("cute",         "Check cuteness level (fun)"),
            ("intelligence", "Check intelligence level (fun)"),
            ("8ball",        "Ask the magic 8-ball a question"),
            ("truth",        "Get a random truth question"),
            ("dare",         "Get a random dare challenge"),
            ("meme",         "Get a random meme"),
            ("joke",         "Get a random joke"),
            ("quote",        "Get a random quote"),
            ("roast",        "Roast a member"),
            ("fact",         "Get a random interesting fact"),
            ("flip",         "Flip a coin — heads or tails"),
            ("emojify",      "Convert text to emoji letters"),
            ("ascii",        "Convert text to ASCII art"),
            ("shout",        "SHOUT a message in big letters"),
            ("love",         "Check love % between two users"),
            ("horoscope",    "Get today's horoscope for a sign"),
            ("mydog",        "Get a random dog image"),
            ("gif",          "Search and send a GIF"),
            ("image",        "Search and send an image"),
            ("boy",          "Send a random boy anime image"),
            ("girl",         "Send a random girl anime image"),
            ("couple",       "Send a random couple image"),
            ("anime",        "Send a random anime image"),
            ("imagine",      "Generate an AI image"),
            ("iplookup",     "Look up info on an IP address"),
            ("weather",      "Get weather info for a location"),
            ("fakeban",      "Fake ban someone (prank embed)"),
            ("hack",         "Fake hack someone (prank embed)"),
            ("token",        "Generate a fake token (fun)"),
            ("wizz",         "Wizz a member (fun)"),
            ("rickroll",     "Rickroll a member with a link"),
            ("hash",         "Hash a text with MD5/SHA"),
        ],
    },
    {
        "key":   "games",
        "emoji": EMOJI_MIC,
        "name":  "Games",
        "desc":  "Chess, wordle, 2048 & more",
        "info":  "Play classic and modern games directly in Discord.",
        "commands": [
            ("blackjack",       "Play blackjack card game"),
            ("chess",           "Play chess against someone"),
            ("tic-tac-toe",     "Play tic-tac-toe with a member"),
            ("rps",             "Play rock paper scissors"),
            ("wordle",          "Guess the 5-letter word — Wordle"),
            ("2048",            "Play 2048 sliding puzzle game"),
            ("memory-game",     "Play emoji memory matching game"),
            ("number-slider",   "Play the number sliding puzzle"),
            ("battleship",      "Play battleship with a member"),
            ("country-guesser", "Guess the country from a clue"),
            ("connectfour",     "Play Connect Four with a member"),
            ("lights-out",      "Play the lights-out puzzle game"),
            ("slots",           "Play the slot machine"),
        ],
    },
    {
        "key":   "media",
        "emoji": EMOJI_STAR,
        "name":  "Media",
        "desc":  "Media-only channel setup",
        "info":  "Restrict channels to media-only with auto-delete for non-media messages.",
        "commands": [
            ("media setup",         "Set a channel as media-only"),
            ("media remove",        "Remove media-only restriction"),
            ("media config",        "View media channel configuration"),
            ("media bypass add",    "Allow a user/role to bypass media filter"),
            ("media bypass remove", "Remove bypass permission"),
            ("media bypass show",   "Show all bypass permissions"),
        ],
    },
    {
        "key":   "j2c",
        "emoji": EMOJI_FREEZE,
        "name":  "J2C",
        "desc":  "Dynamic voice channel creation",
        "info":  "Members auto-create temporary voice channels on joining a trigger VC.",
        "commands": [
            ("j2c setup",  "Configure the Join-to-Create system"),
            ("j2c reset",  "Clear all J2C settings"),
            ("j2c config", "View & edit J2C configuration"),
        ],
    },
    {
        "key":   "ignore",
        "emoji": EMOJI_UTILITY5,
        "name":  "Ignore",
        "desc":  "Ignore commands in channels/users",
        "info":  "Exclude commands, channels or users from bot responses completely.",
        "commands": [
            ("ignore command add",    "Disable a specific command"),
            ("ignore command remove", "Re-enable a disabled command"),
            ("ignore command show",   "Show all disabled commands"),
            ("ignore channel add",    "Ignore all commands in a channel"),
            ("ignore channel remove", "Stop ignoring a channel"),
            ("ignore channel show",   "List all ignored channels"),
            ("ignore user add",       "Ignore all commands from a user"),
            ("ignore user remove",    "Stop ignoring a user"),
            ("ignore user show",      "List all ignored users"),
            ("ignore bypass add",     "Allow a user to bypass ignores"),
            ("ignore bypass remove",  "Remove bypass permission"),
            ("ignore bypass show",    "List all bypass users"),
        ],
    },
    {
        "key":   "tickets",
        "emoji": EMOJI_UTILITY2,
        "name":  "Tickets",
        "desc":  "Ticket panel & support system",
        "info":  "Full ticket system with panels, management and HTML transcripts.",
        "commands": [
            ("ticket setup",      "Setup the ticket system panel"),
            ("ticket close",      "Close the current ticket"),
            ("ticket lock",       "Lock a ticket — stop new messages"),
            ("ticket unlock",     "Unlock a closed ticket"),
            ("ticket claim",      "Claim a ticket as your own"),
            ("ticket transcript", "Save ticket as an HTML transcript"),
        ],
    },
    {
        "key":   "welcomer",
        "emoji": EMOJI_TELESCOPE2,
        "name":  "Welcomer",
        "desc":  "Welcome messages for new members",
        "info":  "Greet new members with custom messages, images and auto-delete.",
        "commands": [
            ("greet setup",      "Configure the welcome message"),
            ("greet reset",      "Reset all welcomer settings"),
            ("greet channel",    "Set the welcome channel"),
            ("greet test",       "Preview your welcome message"),
            ("greet config",     "View welcomer configuration"),
            ("greet autodelete", "Set auto-delete timer for welcome msg"),
            ("greet edit",       "Edit the welcome message content"),
        ],
    },
    {
        "key":   "leave",
        "emoji": EMOJI_TELESCOPE,
        "name":  "Leave",
        "desc":  "Goodbye messages for leaving members",
        "info":  "Send goodbye messages when members leave your server.",
        "commands": [
            ("leave setup",      "Configure the leave/goodbye message"),
            ("leave reset",      "Reset all leave message settings"),
            ("leave channel",    "Set the leave message channel"),
            ("leave test",       "Preview your leave message"),
            ("leave config",     "View leave message configuration"),
            ("leave autodelete", "Set auto-delete timer for leave msg"),
            ("leave edit",       "Edit the leave message content"),
        ],
    },
    {
        "key":   "chatai",
        "emoji": EMOJI_STAR2,
        "name":  "Chat AI",
        "desc":  "AI chat assistant",
        "info":  "AI chat assistant with memory, auto-channels, DM support and model selection.",
        "commands": [
            ("chat",             "Talk to the AI directly"),
            ("ai toggle",        "Toggle AI chat on/off"),
            ("ai model list",    "List all available AI models"),
            ("ai model set",     "Set a specific AI model to use"),
            ("ai model current", "Show currently active AI model"),
            ("ai auto add",      "Add an auto-chat channel"),
            ("ai auto remove",   "Remove an auto-chat channel"),
            ("ai auto list",     "List all auto-chat channels"),
            ("ai dm toggle",     "Toggle AI in DMs on/off"),
            ("ai memory show",   "Show AI's memory for you"),
            ("ai memory clear",  "Clear AI's memory for you"),
            ("ai stats",         "Show AI usage statistics"),
            ("ai errors",        "Show recent AI errors"),
            ("ai logs",          "Show AI conversation logs"),
        ],
    },
    {
        "key":   "music",
        "emoji": EMOJI_STAR,
        "name":  "Music",
        "desc":  "Play music from YouTube & Spotify",
        "info":  "Full music system — play from YouTube/Spotify, queue management, filters and more.",
        "commands": [
            ("music join",       "Make bot join your voice channel"),
            ("music leave",      "Make bot leave the voice channel"),
            ("music play",       "Play a song or playlist"),
            ("music skip",       "Skip to the next song"),
            ("music stop",       "Stop music and clear the queue"),
            ("music pause",      "Pause the current song"),
            ("music volume",     "Set the playback volume"),
            ("music queue",      "View the current music queue"),
            ("music nowplaying", "Show currently playing song"),
            ("music shuffle",    "Shuffle the music queue"),
            ("music loop",       "Loop the current song or queue"),
            ("music filter",     "Apply audio filter (bass/nightcore etc)"),
            ("music autoplay",   "Auto-queue related songs — Premium"),
            ("music 247",        "Keep bot in VC 24/7 — Premium"),
        ],
    },
    {
        "key":   "trusted",
        "emoji": EMOJI_CROWN,
        "name":  "Trusted",
        "desc":  "Grant elevated permissions to staff",
        "info":  "Grant elevated bot permissions to trusted staff members of your server.",
        "commands": [
            ("trusted add",    "Add a member to the trusted list"),
            ("trusted remove", "Remove a member from trusted list"),
            ("trusted show",   "List all trusted members"),
            ("trusted reset",  "Remove all trusted members"),
        ],
    },
    {
        "key":   "antibot",
        "emoji": EMOJI_ROBOT2,
        "name":  "Antibot",
        "desc":  "Auto-delete bot messages in channels",
        "info":  "Auto-delete bot messages in protected channels. Whitelist safe bots to exclude them.",
        "commands": [
            ("antibot channel add",      "Protect a channel from bot messages"),
            ("antibot channel remove",   "Remove channel protection"),
            ("antibot channel show",     "List all protected channels"),
            ("antibot channel reset",    "Remove all channel protections"),
            ("antibot whitelist add",    "Whitelist a safe bot to allow it"),
            ("antibot whitelist remove", "Remove a bot from whitelist"),
            ("antibot whitelist show",   "Show all whitelisted bots"),
            ("antibot whitelist reset",  "Reset all whitelisted bots"),
        ],
    },
    {
        "key":   "lockrole",
        "emoji": EMOJI_KEY,
        "name":  "Lock Role",
        "desc":  "Lock roles — only WL users can assign",
        "info":  "💎 Premium — Lock any role so only whitelisted users can assign it.",
        "commands": [
            ("lockrole add",            "Lock a role from being assigned"),
            ("lockrole remove",         "Unlock a previously locked role"),
            ("lockrole list",           "List all locked roles"),
            ("lockrole reset",          "Unlock all locked roles"),
            ("lockrole wl add",         "Whitelist a user to assign a locked role"),
            ("lockrole wl remove",      "Remove whitelist for a user/role"),
            ("lockrole wl list",        "List all whitelisted users for a role"),
            ("lockrole punishment set", "Set punishment for violators"),
            ("lockrole logging setup",  "Set log channel for violations"),
            ("lockrole config",         "View full lockrole configuration"),
        ],
    },
    {
        "key":   "premium",
        "emoji": EMOJI_DIAMOND,
        "name":  "Premium",
        "desc":  "Exclusive premium features",
        "info":  "💎 Exclusive premium features — backup, scan, music extras, lockrole, custom profile & more.",
        "commands": [
            ("premium status",          "Check your premium status"),
            ("premium redeem",          "Redeem a premium code"),
            ("premium codes",           "View available premium codes"),
            ("backup create",           "Create a full server backup"),
            ("backup restore",          "Restore server from a backup"),
            ("backup list",             "List all your backups"),
            ("backup delete",           "Delete a saved backup"),
            ("serverhealth",            "Deep scan of server health"),
            ("scan",                    "Scan server for threats"),
            ("ghostaudit",              "Audit ghost/hidden permissions"),
            ("messages",                "View your message count"),
            ("msgleaderboard",          "Show message count leaderboard"),
            ("addmessages",             "Manually add messages to a user"),
            ("removemessages",          "Manually remove messages from user"),
            ("clearmessages",           "Clear message count for a user"),
            ("say",                     "Make bot say a custom message"),
            ("stock",                   "Check stock prices"),
            ("customprofile avatar",    "Set bot's custom avatar"),
            ("customprofile banner",    "Set bot's custom banner"),
            ("customprofile reset",     "Reset custom profile"),
            ("customised greet/leave",  "Use custom greet/leave templates"),
            ("applytemplate",           "Apply a server template"),
            ("antiraid",                "Toggle anti-raid auto-lockdown"),
            ("serverlock",              "Lock the entire server"),
            ("serverunlock",            "Unlock the entire server"),
            ("fakepermit",              "Send fake permission granted (prank)"),
            ("embedbuilder",            "Interactive no-code embed creator"),
            ("reminder",                "Set a DM reminder (10m/2h/1d etc)"),
            ("shadowban",               "Silently delete a user's messages"),
            ("shadowunban",             "Remove shadowban from a user"),
            ("shadowlist",              "List all shadowbanned users"),
            ("massdm",                  "DM all members or a specific role"),
        ],
    },
]

# ══════════════════════════════════════════════════════════════════════════════
#  SPLIT — Module 1 = first 13, Module 2 = rest  (max 25 each)
# ══════════════════════════════════════════════════════════════════════════════
SPLIT = 13

# ══════════════════════════════════════════════════════════════════════════════
#  OWNER MODULES
# ══════════════════════════════════════════════════════════════════════════════
OWNER_MODULES = [
    {
        "key":   "owner1",
        "emoji": "<:nex_Tick:1422411439049674815>",
        "name":  "Owner 1",
        "desc":  "Staff management & utilities",
        "info":  "Staff management, bans, broadcasting and owner utilities.",
        "commands": [
            ("staff_add",           "Add a staff member to the bot"),
            ("staff_remove",        "Remove a staff member"),
            ("staff_list",          "List all staff members"),
            ("slist",               "Shortened staff list"),
            ("staffrules",          "Show staff rules"),
            ("staffr",              "Short alias for staffrules"),
            ("mutuals",             "Show mutual servers with a user"),
            ("getinvite",           "Get invite link for a guild"),
            ("$restart",            "Restart the bot"),
            ("$sync",               "Sync slash commands globally"),
            ("owners",              "List all bot owners"),
            ("dm",                  "DM any user via bot"),
            ("ownerdm",             "DM another owner"),
            ("nickname",            "Change bot's nickname in a guild"),
            ("ownerban",            "Ban a user globally"),
            ("ownerunban",          "Unban a user globally"),
            ("globalunban",         "Unban user from all servers"),
            ("guildban",            "Ban a user from a specific guild"),
            ("guildunban",          "Unban user from a specific guild"),
            ("leaveguild",          "Make bot leave a guild"),
            ("guildinfo",           "Get info about any guild"),
            ("servertour",          "Tour a server's channels"),
            ("bdg add",             "Add a badge to a user"),
            ("bdg remove",          "Remove a badge from a user"),
            ("forcepurgebots",      "Force purge bot messages in a guild"),
            ("forcepurgeuser",      "Force purge user messages in a guild"),
            ("badges",              "Show badges of any user"),
            ("broadcast",           "Broadcast message to all guilds"),
            ("np add",              "Add a global no-prefix user"),
            ("np remove",           "Remove a global no-prefix user"),
            ("np status",           "Check a user's no-prefix status"),
            ("np list",             "List all global no-prefix users"),
            ("np reset",            "Reset all no-prefix users"),
            ("autonp guild add",    "Add auto no-prefix for a guild"),
            ("autonp guild remove", "Remove auto no-prefix for a guild"),
            ("autonp guild list",   "List guilds with auto no-prefix"),
            ("npclaim",             "Claim no-prefix in a server"),
        ],
    },
    {
        "key":   "owner2",
        "emoji": "<:nextra_cross:1422411673544822905>",
        "name":  "Owner 2",
        "desc":  "Global moderation & blacklist tools",
        "info":  "Global moderation tools and blacklist management.",
        "commands": [
            ("global kick",            "Kick a user from all mutual guilds"),
            ("global timeout",         "Timeout a user globally"),
            ("global nick",            "Change a user's nick everywhere"),
            ("global clearnick",       "Clear a user's nick everywhere"),
            ("global freezenick",      "Freeze a user's nickname globally"),
            ("global unfreezenick",    "Unfreeze a user's nickname globally"),
            ("freezenick",             "Freeze a user's nick in a guild"),
            ("unfreezenick",           "Unfreeze a user's nick in a guild"),
            ("GB",                     "Global ban a user from all guilds"),
            ("bugfix",                 "Apply a bug fix patch"),
            ("blacklist user add",     "Blacklist a user from the bot"),
            ("blacklist user remove",  "Remove a user from blacklist"),
            ("blacklist user show",    "Show all blacklisted users"),
            ("blacklist guild add",    "Blacklist a guild from the bot"),
            ("blacklist guild remove", "Remove a guild from blacklist"),
            ("blacklist guild show",   "Show all blacklisted guilds"),
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  EMBED BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def _footer_text(user, page, total):
    return f"Page {page} of {total}  •  {user.name}"


def build_home(bot, user, prefix, total) -> discord.Embed:
    total_cmds = sum(len(m["commands"]) for m in MODULES)
    ping_ms    = round(bot.latency * 1000)

    em = discord.Embed(
        title=f"{E['shield']}  **CupidX**  Help Center",
        description=(
            f"-# *Your all-in-one Discord moderation & utility bot.*\n"
            f"Browse using **Module 1** or **Module 2** dropdowns below.\n"
            f"Or run `{prefix}help <module>` to jump directly.\n\u200b"
        ),
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name=f"Requested by {user.name}", icon_url=user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)
    em.add_field(
        name=f"{E['bot']}  Bot Stats",
        value=(
            f"{E['arrow']} **Prefix:** `{prefix}`\n"
            f"{E['arrow']} **Ping:** `{ping_ms}ms`\n"
            f"{E['arrow']} **Commands:** `{total_cmds}`\n"
            f"{E['arrow']} **Modules:** `{len(MODULES)}`"
        ),
        inline=True,
    )
    em.add_field(name="\u200b", value="\u200b", inline=False)
    em.add_field(
        name=f"{E['shield']}  Security & Moderation",
        value=(
            f"{E['dot']} `Antinuke` `Whitelist` `Emergency`\n"
            f"{E['dot']} `Ban` `Kick` `Mute` `Warn` `Roles`\n"
            f"{E['dot']} `Lock` `Hide` `Jail` `Automod`"
        ),
        inline=True,
    )
    em.add_field(
        name=f"{E['settings']}  Server & Utility",
        value=(
            f"{E['dot']} `Welcomer` `Logging` `Tickets`\n"
            f"{E['dot']} `Giveaways` `Counting` `AutoPFP`\n"
            f"{E['dot']} `Trusted` `Antibot` `Verification`"
        ),
        inline=True,
    )
    em.add_field(
        name=f"{E['fire']}  Fun & Extra",
        value=(
            f"{E['dot']} `Games` `Fun Commands`\n"
            f"{E['dot']} `Invite Tracker` `Voice` `Media`\n"
            f"{E['dot']} `Music` `Premium` & more"
        ),
        inline=True,
    )
    em.add_field(
        name=f"{E['link']}  Quick Links",
        value=(
            f"[{E['bot']} Invite CupidX]({BOT_INVITE})  •  "
            f"[{E['shield']} Support Server]({SUPPORT_SERVER})"
        ),
        inline=False,
    )
    em.set_image(url=BANNER_URL)
    em.set_footer(text=_footer_text(user, 1, total), icon_url=bot.user.display_avatar.url)
    return em


def build_module_page(bot, user, mod: dict, page: int, total: int) -> discord.Embed:
    """One embed per module — each command on its own line with description."""
    em = discord.Embed(
        title=f"{mod['emoji']}  {mod['name']}",
        description=f"-# {mod['info']}\n\u200b",
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name="CupidX Help Center", icon_url=bot.user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)

    # Split commands into chunks of 10 per field
    CHUNK = 10
    cmds  = mod["commands"]
    for i in range(0, len(cmds), CHUNK):
        chunk = cmds[i:i + CHUNK]
        lines = "\n".join(
            f"{E['dot']} `{cmd}` — {desc}"
            for cmd, desc in chunk
        )
        label = f"{E['settings']}  Commands" if i == 0 else f"{E['settings']}  Commands (cont.)"
        em.add_field(name=label, value=lines, inline=False)

    em.set_footer(text=_footer_text(user, page, total), icon_url=bot.user.display_avatar.url)
    return em


def build_owner_home(bot, user, total) -> discord.Embed:
    em = discord.Embed(
        title=f"{E['crown']}  CupidX — Owner Control Panel",
        description=(
            f"> *Confidential commands for bot developers only.*\n"
            f"> Unauthorized access is strictly prohibited.\n\u200b"
        ),
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name="CupidX Developer Panel", icon_url=bot.user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)
    em.add_field(
        name=f"{E['shield']}  Access Level",
        value=f"{E['tick']} **Bot Owner Only** — Restricted to verified developers.",
        inline=False,
    )
    em.add_field(
        name=f"{E['settings']}  Sections",
        value=(
            f"{E['dot']} **Owner 1** — Staff management, bans, broadcasting & utilities\n"
            f"{E['dot']} **Owner 2** — Global moderation & blacklist tools"
        ),
        inline=False,
    )
    em.set_image(url=BANNER_URL)
    em.set_footer(text=_footer_text(user, 1, total), icon_url=user.display_avatar.url)
    return em


def build_owner_module_page(bot, user, mod: dict, page: int, total: int) -> discord.Embed:
    em = discord.Embed(
        title=f"{mod['emoji']}  {mod['name']}  — Owner Commands",
        description=f"> {mod['info']}\n> Use with extreme caution.\n\u200b",
        color=BOT_COLOR,
        timestamp=datetime.datetime.utcnow(),
    )
    em.set_author(name="CupidX Developer Panel", icon_url=bot.user.display_avatar.url)
    em.set_thumbnail(url=bot.user.display_avatar.url)

    CHUNK = 10
    for i in range(0, len(mod["commands"]), CHUNK):
        chunk = mod["commands"][i:i + CHUNK]
        lines = "\n".join(f"{E['dot']} `{cmd}` — {desc}" for cmd, desc in chunk)
        label = f"{E['settings']}  Commands" if i == 0 else f"{E['settings']}  Commands (cont.)"
        em.add_field(name=label, value=lines, inline=False)

    em.set_footer(text=_footer_text(user, page, total), icon_url=user.display_avatar.url)
    return em


# ══════════════════════════════════════════════════════════════════════════════
#  DROPDOWN
# ══════════════════════════════════════════════════════════════════════════════
import re as _re

def _parse_emoji(raw):
    if not raw:
        return None
    m = _re.match(r"<(a?):([\w]+):([0-9]+)>", str(raw))
    if m:
        try:
            return discord.PartialEmoji(name=m.group(2), id=int(m.group(3)), animated=bool(m.group(1)))
        except Exception:
            return None
    cleaned = str(raw).replace("\ufe0f", "").replace("\ufe0e", "")
    return cleaned if cleaned else None


class ModuleDropdown(Select):
    def __init__(self, user, module_slice: list, page_start: int, placeholder: str, row: int):
        options = [
            discord.SelectOption(
                label=mod["name"],
                value=str(page_start + i),
                description=mod["desc"][:50],
                emoji=_parse_emoji(mod["emoji"]),
            )
            for i, mod in enumerate(module_slice[:25])
        ]
        super().__init__(placeholder=placeholder, options=options, row=row)
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                f"{E['cross']} This menu belongs to someone else!", ephemeral=True
            )
        self.view.current_page = int(self.values[0])
        await self.view.refresh(interaction)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN VIEW
# ══════════════════════════════════════════════════════════════════════════════
class HelpView(View):
    def __init__(self, bot, user, pages: list, mod1: list, mod2: list, mod1_start: int, mod2_start: int):
        super().__init__(timeout=180)
        self.bot          = bot
        self.user         = user
        self.pages        = pages
        self.current_page = 0
        self.message      = None

        # Row 0 — Navigation buttons
        self.btn_first = Button(label="Home",   style=discord.ButtonStyle.secondary, row=0)
        self.btn_back  = Button(label="◀ Back", style=discord.ButtonStyle.secondary, row=0)
        self.btn_close = Button(emoji=EMOJI_TRASH, style=discord.ButtonStyle.danger, row=0)
        self.btn_next  = Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
        self.btn_last  = Button(label="Last",   style=discord.ButtonStyle.secondary, row=0)

        self.btn_first.callback = self.go_first
        self.btn_back.callback  = self.go_back
        self.btn_close.callback = self.close_menu
        self.btn_next.callback  = self.go_next
        self.btn_last.callback  = self.go_last

        self.add_item(self.btn_first)
        self.add_item(self.btn_back)
        self.add_item(self.btn_close)
        self.add_item(self.btn_next)
        self.add_item(self.btn_last)

        # Row 1 — Module 1 dropdown
        if mod1:
            self.add_item(ModuleDropdown(user, mod1, mod1_start, "📂 Module 1 — Select Category", row=1))

        # Row 2 — Module 2 dropdown
        if mod2:
            self.add_item(ModuleDropdown(user, mod2, mod2_start, "📂 Module 2 — Select Category", row=2))

        self._sync_buttons()

    def _sync_buttons(self):
        last = len(self.pages) - 1
        self.btn_first.disabled = self.current_page == 0
        self.btn_back.disabled  = self.current_page == 0
        self.btn_next.disabled  = self.current_page == last
        self.btn_last.disabled  = self.current_page == last

    async def refresh(self, interaction: discord.Interaction):
        self._sync_buttons()
        embed = self.pages[self.current_page]
        try:
            if interaction.response.is_done():
                await interaction.message.edit(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            pass

    async def _guard(self, interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{E['cross']} Only the command executor can use this. Run `help` yourself!",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        try:
            if self.message:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except Exception:
            pass

    async def go_first(self, interaction):
        if not await self._guard(interaction): return
        self.current_page = 0
        await self.refresh(interaction)

    async def go_back(self, interaction):
        if not await self._guard(interaction): return
        if self.current_page > 0:
            self.current_page -= 1
        await self.refresh(interaction)

    async def close_menu(self, interaction):
        if not await self._guard(interaction): return
        try:
            await interaction.message.delete()
        except Exception:
            await interaction.response.defer()

    async def go_next(self, interaction):
        if not await self._guard(interaction): return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        await self.refresh(interaction)

    async def go_last(self, interaction):
        if not await self._guard(interaction): return
        self.current_page = len(self.pages) - 1
        await self.refresh(interaction)


# ══════════════════════════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════════════════════════
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["h"])
    async def help_cmd(self, ctx, *, category: str = None):
        prefix = ctx.prefix or "$"
        user   = ctx.author

        total = 1 + len(MODULES)
        pages = [build_home(self.bot, user, prefix, total)]

        for idx, mod in enumerate(MODULES):
            pages.append(build_module_page(self.bot, user, mod, idx + 2, total))

        mod1 = MODULES[:SPLIT]
        mod2 = MODULES[SPLIT:]
        mod1_start = 1
        mod2_start = 1 + SPLIT

        # Handle optional category arg
        target = 0
        if category:
            q = category.lower()
            for idx, mod in enumerate(MODULES):
                if q in mod["name"].lower() or q in mod["key"].lower():
                    target = idx + 1
                    break

        # Loading
        loading_em = discord.Embed(
            description=f"{E['loading']}  Loading Help Menu...",
            color=BOT_COLOR,
        )
        msg = await ctx.reply(embed=loading_em, mention_author=False)
        await asyncio.sleep(1)

        view = HelpView(self.bot, user, pages, mod1, mod2, mod1_start, mod2_start)
        view.current_page = target
        view._sync_buttons()
        await msg.edit(embed=pages[target], view=view)
        view.message = msg

    @commands.command(name="ownerhelp", aliases=["owh", "ownh"])
    async def owner_help_cmd(self, ctx):
        if ctx.author.id not in OWNER_IDS:
            em = discord.Embed(
                title=f"{E['cross']}  Access Denied",
                description="This command is restricted to **Bot Owners** only.",
                color=0xFF4444,
            )
            return await ctx.reply(embed=em, mention_author=False)

        user  = ctx.author
        total = 1 + len(OWNER_MODULES)

        pages = [build_owner_home(self.bot, user, total)]
        for idx, mod in enumerate(OWNER_MODULES):
            pages.append(build_owner_module_page(self.bot, user, mod, idx + 2, total))

        view = HelpView(
            self.bot, user, pages,
            mod1=OWNER_MODULES, mod2=[],
            mod1_start=1, mod2_start=0,
        )
        view._sync_buttons()
        msg = await ctx.reply(embed=pages[0], view=view, mention_author=False)
        view.message = msg


async def setup(bot):
    await bot.add_cog(Help(bot))
