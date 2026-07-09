import discord
from discord.ext import commands
import aiosqlite
import asyncio
import os
import re
from collections import defaultdict, deque
from utils.Tools import *
from utils.detectfile import *

# ================================================
#  EMOJI CONFIG
# ================================================

class E:
    # Status
    ENABLED      = EMOJI_ENABLE
    DISABLED     = EMOJI_DISABLE
    LOADING      = EMOJI_LOADING
    TIMER        = EMOJI_TIMER

    # Music Actions
    PLAY         = EMOJI_ENABLE2
    PAUSE        = EMOJI_SWITCH
    STOP         = EMOJI_DISABLE2
    SKIP         = EMOJI_ARROW
    QUEUE        = EMOJI_QUEUE
    SHUFFLE      = EMOJI_SHUFFLE
    LOOP         = EMOJI_LOOP
    VOLUME       = EMOJI_VOLUME
    MUTE         = EMOJI_MUTE
    JOIN         = EMOJI_USER
    LEAVE        = EMOJI_TRASH
    MUSIC        = EMOJI_MUSIC
    NOTES        = EMOJI_NOTES
    HEADPHONES   = EMOJI_HEADPHONE
    MICROPHONE   = EMOJI_MIC
    AUTOPLAY     = EMOJI_ROBOT
    TWENTYFOUR   = EMOJI_TIMER2
    FILTER       = EMOJI_SYSTEM
    SPOTIFY      = EMOJI_ENABLE
    YOUTUBE      = EMOJI_FIRE

    # Status indicators
    TICK         = EMOJI_TICK
    TICK1        = EMOJI_ENABLE
    CROSS        = EMOJI_CROSS
    WARNING      = EMOJI_WARN2
    CROWN        = EMOJI_CROWN
    DIAMOND      = EMOJI_DIAMOND
    LOCK         = EMOJI_SHIELD
    SETTINGS     = "<:cog:1487152125069889677>"
    SEARCH       = EMOJI_SIGHT
    LINK         = EMOJI_CLOUD
    CLOCK        = EMOJI_TIMER
    STAR         = EMOJI_STAR4
    FIRE         = EMOJI_FIRE
    INFO         = EMOJI_QUESTION

# ================================================
#  DATABASE PATHS
# ================================================

MUSIC_DB   = "db/music.db"
PREMIUM_DB = "db/premium.db"

# MUSIC_BANNER is imported from utils.detectfile

# ================================================
#  DB HELPERS
# ================================================

async def db_exec(db_path: str, query: str, params: tuple = ()):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetch(db_path: str, query: str, params: tuple = (), one: bool = False):
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone() if one else await cur.fetchall()

# ================================================
#  PREMIUM HELPERS
# ================================================

async def is_premium_guild(guild_id: int) -> bool:
    """
    premium.py ke saath compatible check:
    Table: premium_guilds, column: guild_id, expiry_time (None = lifetime)
    """
    try:
        import datetime
        row = await db_fetch(
            PREMIUM_DB,
            "SELECT expiry_time FROM premium_guilds WHERE guild_id = ?",
            (guild_id,), one=True
        )
        if row is None:
            return False
        expiry_time = row[0]
        if expiry_time is None:
            return True  # Lifetime premium
        # Check if not expired
        expiry_dt = datetime.datetime.fromisoformat(expiry_time)
        return datetime.datetime.utcnow() < expiry_dt
    except Exception:
        return False

# ================================================
#  COMPONENTS V2 HELPERS
# ================================================

def _embed_to_container(embed: discord.Embed, controls=None) -> discord.ui.Container:
    items = []
    if embed.title:
        items.append(discord.ui.TextDisplay(f"## {embed.title}"))
    if embed.description:
        items.append(discord.ui.TextDisplay(embed.description))
    for field in embed.fields:
        items.append(discord.ui.TextDisplay(f"**{field.name}**\n{field.value}"))
    footer_text = getattr(getattr(embed, "footer", None), "text", None)
    if footer_text:
        items.append(discord.ui.TextDisplay(f"-# {footer_text}"))
    if controls:
        if items:
            items.append(discord.ui.Separator())
        for control in controls:
            items.append(control)
    return discord.ui.Container(*items)

def _embed_to_layout(embed: discord.Embed, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=timeout)
    view.add_item(_embed_to_container(embed, controls=controls))
    return view

def _text_to_layout(text: str, controls=None, timeout: float = 180.0) -> discord.ui.LayoutView:
    return _embed_to_layout(discord.Embed(description=text), controls=controls, timeout=timeout)

# ================================================
#  LAVALINK CONFIG
# ================================================
# { "identifier": "Amane & AjieDev - v4", "password": "https://seretia.link/discord"   "host": "lavalinkv4.serenetia.com","port": 443, "secure": true
LAVALINK_HOST     = os.getenv("LAVALINK_HOST", "omega.vexanode.cloud")
LAVALINK_PORT     = int(os.getenv("LAVALINK_PORT", 2031))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "https://discord.vexanode.cloud/")
LAVALINK_SECURE   = os.getenv("LAVALINK_SECURE", "false").lower() == "true"

try:
    import wavelink
    WAVELINK_AVAILABLE = True
except ImportError:
    WAVELINK_AVAILABLE = False

# ================================================
#  GUILD MUSIC STATE
# ================================================

class GuildMusicState:
    """Holds per-guild playback state."""
    def __init__(self):
        self.queue:           deque      = deque()
        self.current:         dict|None  = None
        self.volume:          int        = 100
        self.loop:            bool       = False
        self.loop_queue:      bool       = False
        self.autoplay:        bool       = False
        self.twentyfour:      bool       = False
        self.paused:          bool       = False
        self.filters:         list[str]  = []
        self.ffmpeg_filter:   str        = ""   # active FFmpeg -af filter string
        self.vc:              discord.VoiceClient|None = None
        self.now_playing_msg: discord.Message|None     = None

    def clear(self):
        self.queue.clear()
        self.current = None
        self.paused  = False

# ================================================
#  NOW PLAYING VIEW
# ================================================

class NowPlayingView(discord.ui.LayoutView):
    def __init__(self, cog, guild_id: int, author: discord.Member):
        super().__init__(timeout=300)
        self.cog      = cog
        self.guild_id = guild_id
        self.author   = author

        self.btn_pause   = discord.ui.Button(emoji=discord.PartialEmoji.from_str(EMOJI_SWITCH),  style=discord.ButtonStyle.primary,   label="Pause")
        self.btn_skip    = discord.ui.Button(emoji=discord.PartialEmoji.from_str(EMOJI_ARROW),   style=discord.ButtonStyle.secondary, label="Skip")
        self.btn_stop    = discord.ui.Button(emoji=discord.PartialEmoji.from_str(EMOJI_DISABLE2),style=discord.ButtonStyle.danger,    label="Stop")
        self.btn_loop    = discord.ui.Button(emoji=discord.PartialEmoji.from_str(EMOJI_LOOP),style=discord.ButtonStyle.secondary, label="Loop")
        self.btn_shuffle = discord.ui.Button(emoji=discord.PartialEmoji.from_str(EMOJI_SHUFFLE),  style=discord.ButtonStyle.secondary, label="Shuffle")

        self.btn_pause.callback   = self._pause_cb
        self.btn_skip.callback    = self._skip_cb
        self.btn_stop.callback    = self._stop_cb
        self.btn_loop.callback    = self._loop_cb
        self.btn_shuffle.callback = self._shuffle_cb

        self.add_item(discord.ui.Container(
            discord.ui.ActionRow(self.btn_pause, self.btn_skip, self.btn_stop),
            discord.ui.ActionRow(self.btn_loop, self.btn_shuffle),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or interaction.user.voice.channel != interaction.guild.me.voice.channel:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} You must be in the same voice channel."), ephemeral=True
            )
            return False
        return True

    async def _pause_cb(self, interaction: discord.Interaction):
        state = self.cog._get_state(self.guild_id)
        if state.vc and state.vc.is_playing():
            state.vc.pause()
            state.paused = True
            self.btn_pause.label = "Resume"
            self.btn_pause.emoji = discord.PartialEmoji.from_str(EMOJI_ENABLE2)
        elif state.vc and state.vc.is_paused():
            state.vc.resume()
            state.paused = False
            self.btn_pause.label = "Pause"
            self.btn_pause.emoji = discord.PartialEmoji.from_str(EMOJI_SWITCH)
        await interaction.response.edit_message(view=self)

    async def _skip_cb(self, interaction: discord.Interaction):
        state = self.cog._get_state(self.guild_id)
        if state.vc and (state.vc.is_playing() or state.vc.is_paused()):
            state.vc.stop()
        await interaction.response.defer()

    async def _stop_cb(self, interaction: discord.Interaction):
        state = self.cog._get_state(self.guild_id)
        state.clear()
        if state.vc:
            state.vc.stop()
            if not state.twentyfour:
                await state.vc.disconnect()
                state.vc = None
        embed = discord.Embed(
            title=f"{E.STOP} Stopped",
            description="Music stopped and queue cleared.",
            color=0xED4245
        )
        await interaction.response.edit_message(view=_embed_to_layout(embed))

    async def _loop_cb(self, interaction: discord.Interaction):
        state = self.cog._get_state(self.guild_id)
        state.loop = not state.loop
        self.btn_loop.style = discord.ButtonStyle.success if state.loop else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            view=_text_to_layout(
                f"{E.LOOP} Loop {'**enabled**' if state.loop else '**disabled**'} for current track."
            ),
            ephemeral=True
        )

    async def _shuffle_cb(self, interaction: discord.Interaction):
        import random
        state = self.cog._get_state(self.guild_id)
        q = list(state.queue)
        random.shuffle(q)
        state.queue = deque(q)
        await interaction.response.send_message(
            view=_text_to_layout(f"{E.SHUFFLE} Queue shuffled!"), ephemeral=True
        )

# ================================================
#  FILTER SELECT VIEW
# ================================================

FILTERS = {
    "normal":     "Normal — Remove all filters (default)",
    "bassboost":  "Bass Boost — Deep punchy bass (+8dB low-end)",
    "basscut":    "Bass Cut — Remove heavy bass (fixes moti awaaz)",
    "nightcore":  "Nightcore — Faster tempo + higher pitch",
    "vaporwave":  "Vaporwave — Slower tempo + lower pitch",
    "8d":         "8D Audio — Rotating stereo panning effect",
    "karaoke":    "Karaoke — Reduces vocal frequencies",
    "tremolo":    "Tremolo — Rapid volume fluctuation",
    "vibrato":    "Vibrato — Rapid pitch fluctuation",
    "soft":       "Soft — Gentle highpass + lowpass combo",
    "earrape":    "Earrape — Max distortion (use at own risk)",
}

class FilterView(discord.ui.LayoutView):
    def __init__(self, cog, guild_id: int, author: discord.Member):
        super().__init__(timeout=60)
        self.cog      = cog
        self.guild_id = guild_id
        self.author   = author

        self.select = discord.ui.Select(
            placeholder="Choose an audio filter...",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label=name.title(), value=name, description=desc)
                for name, desc in FILTERS.items()
            ]
        )
        self.select.callback = self._select_cb

        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## {E.FILTER} Audio Filters"),
            discord.ui.TextDisplay("Select a filter to apply.\n`Normal` = no filter (fixes moti awaaz). Works with **FFmpeg** (no Lavalink needed)."),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.select),
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                view=_text_to_layout(f"{E.CROSS} This isn't your filter menu."), ephemeral=True
            )
            return False
        return True

    async def _select_cb(self, interaction: discord.Interaction):
        state  = self.cog._get_state(self.guild_id)
        chosen = self.select.values[0]

        if chosen == "normal":
            state.filters.clear()
            state.ffmpeg_filter = ""
            msg = f"{E.TICK} All filters cleared. Audio is now **normal**."
        else:
            state.filters = [chosen]
            state.ffmpeg_filter = _build_ffmpeg_af(chosen)
            msg = f"{E.FILTER} **{chosen.title()}** filter applied."

        # Wavelink path — apply via wavelink filters
        if WAVELINK_AVAILABLE and state.vc and isinstance(state.vc, wavelink.Player):
            await self.cog._apply_wavelink_filters(state)
        # FFmpeg path — restart playback with new filter if something is playing
        elif state.vc and state.vc.is_playing() and state.current:
            state.vc.stop()  # after() callback will call _play_next → requeues current if loop off
            if not state.loop:
                # Re-insert current track at front so it replays with new filter
                state.queue.appendleft(state.current)
                state.current = None

        embed = discord.Embed(
            title=f"{E.FILTER} Filter Applied",
            description=(
                f"{msg}\n\n"
                f"**Active filter:** `{state.filters[0].title() if state.filters else 'Normal'}`"
            ),
            color=0x5865F2
        )
        await interaction.response.edit_message(view=_embed_to_layout(embed))

# ================================================
#  FFMPEG AUDIO FILTER BUILDER
# ================================================

def _build_ffmpeg_af(filter_name: str) -> str:
    """
    Convert a filter name to an FFmpeg -af filter string.
    Returns empty string for no filter (normal audio).
    """
    _map = {
        # Bass cut — fixes "moti awaaz" by cutting sub-bass and boosting highs slightly
        "basscut":   "equalizer=f=80:width_type=o:width=2:g=-10,equalizer=f=200:width_type=o:width=2:g=-6,equalizer=f=4000:width_type=o:width=2:g=3",
        # Bass boost — punchy low end
        "bassboost": "equalizer=f=40:width_type=o:width=2:g=5,equalizer=f=80:width_type=o:width=2:g=8,equalizer=f=200:width_type=o:width=2:g=4",
        # Nightcore — faster + higher pitch
        "nightcore": "asetrate=48000*1.25,aresample=48000,atempo=1.0",
        # Vaporwave — slower + lower pitch
        "vaporwave": "asetrate=48000*0.8,aresample=48000,atempo=1.0",
        # 8D audio — panning rotation
        "8d":        "apulsator=hz=0.125",
        # Karaoke — reduce center channel (vocals)
        "karaoke":   "pan=stereo|c0=c0-0.5*c1|c1=c1-0.5*c0",
        # Tremolo — volume oscillation
        "tremolo":   "tremolo=f=5:d=0.8",
        # Vibrato — pitch oscillation
        "vibrato":   "vibrato=f=5:d=0.5",
        # Soft — gentle warmth, cuts harsh highs
        "soft":      "lowpass=f=12000,equalizer=f=200:width_type=o:width=2:g=2",
        # Earrape — clipped distortion
        "earrape":   "volume=12,acrusher=level_in=4:level_out=1:bits=4:mode=log",
    }
    return _map.get(filter_name, "")


# ================================================
#  MAIN COG
# ================================================

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self._states: dict[int, GuildMusicState] = {}
