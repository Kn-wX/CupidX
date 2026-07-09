import asyncio
import discord
from discord.ext import commands
from discord.utils import get
import datetime
import random
import requests
import aiohttp
import re
from discord.ext.commands.errors import BadArgument
from discord.colour import Color
from utils.Tools import *
from utils.config import serverLink, CLIENT_ID, SUPPORT_SERVER, BOT_INVITE, WEBSITE
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button
from discord import ButtonStyle
from typing import Optional, Union
import string
import io
import random as _random
from utils.detectfile import *
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#   EMOJIS
# ══════════════════════════════════════════════
E = {
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "tick":     EMOJI_TICK,
    "cross":    EMOJI_CROSS,
    "shield":   EMOJI_SHIELD,
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "fire":     EMOJI_FIRE,
    "bot":      EMOJI_ROBOT,
    "user":     EMOJI_USER,
    "link":     EMOJI_BOND2,
    "timer":    EMOJI_TIMER2,
    "loading":  EMOJI_LOADING,
    "poll":     EMOJI_UTILITY8,
    "members":  EMOJI_PROFILE,
    "stats":    EMOJI_SYSTEM,
    "globe":    EMOJI_BOND2,
    "guild":    EMOJI_UTILITY4B,
}

# ══════════════════════════════════════════════
#   INVITE IMAGE GENERATOR
# ══════════════════════════════════════════════

_ORANGE = (255, 100, 0)
_IMG_W, _IMG_H = 1100, 430


def _generate_invite_image(avatar_bytes: bytes) -> io.BytesIO:
    W, H = _IMG_W, _IMG_H
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # subtle grid
    for x in range(0, W, 42):
        draw.line([(x, 0), (x, H)], fill=(255, 80, 0, 7), width=1)
    for y in range(0, H, 42):
        draw.line([(0, y), (W, y)], fill=(255, 80, 0, 7), width=1)

    # fonts — DejaVu (always available)
    try:
        f_big    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    58)
        f_med    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    22)
        f_reg    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",         17)
        f_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",         13)
        f_title  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    28)
    except Exception:
        f_big = f_med = f_reg = f_small = f_title = ImageFont.load_default()

    # ── TOP: "Powered By CupidX Development" ──
    tx, ty = 30, 18
    parts = [
        ("Powered By ",   (255, 255, 255, 255)),
        ("Q",             (255, 60,  0,   255)),
        ("y",             (255, 100, 0,   255)),
        ("r",             (255, 150, 10,  255)),
        ("o",             (255, 80,  0,   255)),
        ("n",             (255, 50,  0,   255)),
        (" Development",  (255, 180, 60,  255)),
    ]
    for text, color in parts:
        draw.text((tx, ty), text, font=f_title, fill=color)
        tx += draw.textlength(text, font=f_title)

    # ── LEFT: Bot avatar with orange glow ──
    AV_CX, AV_CY, AV_R = 200, 240, 110

    # layered glow
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    for r_extra, alpha in [(80, 8), (60, 16), (44, 28), (30, 46), (18, 70), (10, 105)]:
        gd.ellipse([AV_CX - AV_R - r_extra, AV_CY - AV_R - r_extra,
                    AV_CX + AV_R + r_extra, AV_CY + AV_R + r_extra],
                   fill=(255, 80, 0, alpha))
    glow_b = glow_layer.filter(ImageFilter.GaussianBlur(radius=20))
    img = Image.alpha_composite(img, glow_b)
    draw = ImageDraw.Draw(img)

    # avatar circle
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AV_R * 2, AV_R * 2), Image.LANCZOS)
            mask = Image.new("L", (AV_R * 2, AV_R * 2), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, AV_R * 2, AV_R * 2], fill=255)
            av.putalpha(mask)
            img.paste(av, (AV_CX - AV_R, AV_CY - AV_R), av)
            draw = ImageDraw.Draw(img)
        except Exception:
            draw.ellipse([AV_CX - AV_R, AV_CY - AV_R, AV_CX + AV_R, AV_CY + AV_R], fill=(18, 18, 18, 255))
    else:
        draw.ellipse([AV_CX - AV_R, AV_CY - AV_R, AV_CX + AV_R, AV_CY + AV_R], fill=(18, 18, 18, 255))

    # glowing ring layers
    for t, a in [(7, 15), (5, 50), (3, 130), (2, 220), (1, 255)]:
        draw.ellipse([AV_CX - AV_R - t, AV_CY - AV_R - t,
                      AV_CX + AV_R + t, AV_CY + AV_R + t],
                     outline=(255, 100, 0, a), width=2)

    # bottom glow pool
    pool = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pool)
    pd.ellipse([AV_CX - 90, AV_CY + AV_R - 5, AV_CX + 90, AV_CY + AV_R + 55],
               fill=(255, 70, 0, 65))
    pool_b = pool.filter(ImageFilter.GaussianBlur(radius=25))
    img = Image.alpha_composite(img, pool_b)
    draw = ImageDraw.Draw(img)

    # online dot
    DX, DY = AV_CX + AV_R - 14, AV_CY + AV_R - 14
    draw.ellipse([DX - 10, DY - 10, DX + 10, DY + 10], fill=(0, 0, 0, 255))
    draw.ellipse([DX - 7,  DY - 7,  DX + 7,  DY + 7],  fill=(255, 100, 0, 255))

    # ── RIGHT: promo text ──
    RX = 360  # right panel start x

    # greeting line
    draw.text((RX, 68), "Hey, you found us!", font=f_med, fill=(200, 200, 200, 255))

    # bot name big
    draw.text((RX, 100), "CupidX", font=f_big, fill=(255, 255, 255, 255))
    name_w = int(draw.textlength("CupidX", font=f_big))
    # orange underline
    draw.rounded_rectangle([RX, 164, RX + name_w, 168], radius=2, fill=_ORANGE + (255,))

    # tagline
    draw.text((RX, 178), "Your all-in-one Discord companion.", font=f_reg, fill=(180, 180, 180, 255))

    # divider
    draw.line([(RX, 214), (W - 40, 214)], fill=(50, 50, 50, 255), width=1)

    # feature list
    features = [
        "* Powerful moderation & automod",
        "* Fun commands your whole server will love",
        "* Security tools to keep your server safe",
        "* Clean, modern design built for Discord",
    ]
    fy = 224
    for feat in features:
        # star bullet in orange
        draw.text((RX, fy), "*", font=f_reg, fill=(255, 100, 0, 255))
        draw.text((RX + 14, fy), feat[2:], font=f_reg, fill=(210, 210, 220, 255))
        fy += 30

    # CTA footer
    draw.line([(RX, fy + 4), (W - 40, fy + 4)], fill=(50, 50, 50, 255), width=1)
    draw.text((RX, fy + 12), "Invite CupidX and level up your server today!", font=f_small, fill=(120, 120, 130, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

lawda = ['8', '3821', '23', '21', '313', '43', '29', '76', '11', '9', '44', '470', '318', '26', '69']

color_primary = 0x000000

# ══════════════════════════════════════════════
#   V2 CARD FACTORIES
# ══════════════════════════════════════════════

def v2_avatar_card(member: discord.Member, user: discord.User, banner_url: str = None) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"🖼️ **Avatar** — {member.display_name}"))
    c.add_item(TextDisplay(f"ID: `{user.id}`"))
    c.add_item(Separator())

    formats = []
    if user.avatar and user.avatar.is_animated():
        formats.append(f"[GIF]({user.avatar.with_format('gif').url})")
    if user.avatar:
        formats.extend([
            f"[PNG]({user.avatar.with_format('png').url})",
            f"[JPG]({user.avatar.with_format('jpg').url})",
            f"[WEBP]({user.avatar.with_format('webp').url})"
        ])
    c.add_item(TextDisplay("**Download:** " + " • ".join(formats)))

    if member.guild_avatar:
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Server Avatar:** [View]({member.guild_avatar.url})"))

    if banner_url:
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Banner:** [View]({banner_url})"))

    view.add_item(c)
    return view


def v2_servericon_card(guild: discord.Guild) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"🖼️ **Server Icon** — {guild.name}"))
    c.add_item(TextDisplay(f"`{guild.member_count:,}` members"))
    c.add_item(Separator())

    fmts = ["PNG", "JPG", "WEBP"]
    if guild.icon and guild.icon.is_animated():
        fmts.append("GIF")
    c.add_item(TextDisplay("**Formats:** " + " • ".join(fmts)))
    if guild.icon:
        c.add_item(TextDisplay(f"[Download]({guild.icon.url})"))

    view.add_item(c)
    return view


def v2_memberstats_card(guild: discord.Guild) -> LayoutView:
    total   = len(guild.members)
    humans  = len([m for m in guild.members if not m.bot])
    bots    = total - humans
    online  = len([m for m in guild.members if m.status == discord.Status.online])
    dnd     = len([m for m in guild.members if m.status == discord.Status.do_not_disturb])
    idle    = len([m for m in guild.members if m.status == discord.Status.idle])
    offline = len([m for m in guild.members if m.status == discord.Status.offline])
    boosters = guild.premium_subscription_count or 0
    boost_tier = guild.premium_tier

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"{E['members']} **Member Count** — {guild.name}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{E['crown']} **Total Members** — `{total:,}`\n"
        f"{E['user']}  **Humans** — `{humans:,}`\n"
        f"{E['bot']}  **Bots** — `{bots:,}`"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"🟢 **Online** `{online:,}`  "
        f"🔴 **DND** `{dnd:,}`  "
        f"🟡 **Idle** `{idle:,}`  "
        f"⚫ **Offline** `{offline:,}`"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{E['star']} **Boost Tier** — `{boost_tier}`  {E['fire']} **Boosters** — `{boosters:,}`"
    ))
    view.add_item(c)
    return view


def v2_poll_card(author: discord.Member, question: str) -> LayoutView:
    now = f"<t:{int(datetime.datetime.utcnow().timestamp())}:R>"
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"{E['poll']} **POLL** — Cast your vote!"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f">>> **{question}**"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{E['arrow']} **Started by:** {author.mention}\n"
        f"{E['timer']} **Posted:** {now}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"✅ — **Yes / Agree**\n"
        f"❌ — **No / Disagree**\n"
        f"-# React below to vote!"
    ))
    view.add_item(c)
    return view


def v2_hack_card(member: discord.Member, email: str, password: str) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"💻 **HACKED** — {member.display_name}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"User: {member.mention}"))
    c.add_item(TextDisplay(f"Email: `{email}`"))
    c.add_item(TextDisplay(f"Password: `{password}`"))
    view.add_item(c)
    return view


def v2_token_card(user: discord.Member, token: str) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"🔑 **TOKEN LEAKED** — {user.display_name}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"`{''.join(token)}`"))
    c.add_item(TextDisplay("⚠️ **DO NOT SHARE THIS TOKEN**"))
    view.add_item(c)
    return view


def v2_users_card(users: int, guilds: int, bot_name: str, bot_user: discord.ClientUser = None) -> LayoutView:
    import datetime as _dt
    now = f"<t:{int(_dt.datetime.utcnow().timestamp())}:R>"
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"{E['stats']} **{bot_name}** — Global Stats"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{E['user']}  **Total Users** — `{users:,}`\n"
        f"{E['guild']} **Total Servers** — `{guilds:,}`\n"
        f"{E['timer']} **Checked** — {now}"
    ))
    c.add_item(Separator())
    avg = users // guilds if guilds else 0
    c.add_item(TextDisplay(
        f"{E['arrow']} **Avg Members/Server** — `{avg:,}`\n"
        f"{E['fire']} **Growing fast across Discord!**"
    ))
    view.add_item(c)
    return view


def v2_wizz_card(guild: discord.Guild) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"⚡ **SERVER WIZZED** — {guild.name}"))
    c.add_item(Separator())
    c.add_item(TextDisplay("Roles deleted ✅"))
    c.add_item(TextDisplay("Channels deleted ✅"))
    c.add_item(TextDisplay("Complete wipe done ✅"))
    view.add_item(c)
    return view


def v2_urban_card(phrase: str, definition: str, example: str, author: str, written_on: str) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"📖 **{phrase}**"))
    c.add_item(Separator())
    c.add_item(TextDisplay("**Definition**"))
    c.add_item(TextDisplay(definition[:150] + "..." if len(definition) > 150 else definition))
    c.add_item(Separator())
    c.add_item(TextDisplay("**Example**"))
    c.add_item(TextDisplay(example[:100] + "..." if len(example) > 100 else example))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"By **{author}** · {written_on[:10]}"))
    view.add_item(c)
    return view




# ══════════════════════════════════════════════
#   INVITE CARD — with user info + loading
# ══════════════════════════════════════════════

def v2_invite_card(member: discord.Member = None) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()

    # Top — Bot info
    c.add_item(TextDisplay("**CupidX**"))
    c.add_item(TextDisplay("Invite CupidX to your server or join the support server."))
    c.add_item(Separator())

    # User info (agar member diya ho)
    if member:
        joined = f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown"
        created = f"<t:{int(member.created_at.timestamp())}:R>"
        c.add_item(TextDisplay(f"Requested by: {member.mention}"))
        c.add_item(TextDisplay(f"Account created: {created}"))
        c.add_item(TextDisplay(f"Server joined: {joined}"))
        c.add_item(Separator())

    # Buttons
    row = ActionRow()
    row.add_item(Button(style=ButtonStyle.link, label="Invite CupidX", url=BOT_INVITE))
    row.add_item(Button(style=ButtonStyle.link, label="Support Server", url=SUPPORT_SERVER))
    c.add_item(row)

    view.add_item(c)
    return view


# ══════════════════════════════════════════════
#   COG
# ══════════════════════════════════════════════

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.aiohttp = aiohttp.ClientSession()
        self._URL_REGEX = r'(?P<url><[^: >]+:\/[^ >]+>|(?:https?|steam):\/\/[^\s<]+[^<.,:;\"\'\\]\s])'

    async def cog_unload(self):
        await self.aiohttp.close()

    # ══════════════════════════════
    #   AVATAR
    # ══════════════════════════════
    @commands.command(name='avatar', aliases=['av'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def avatar(self, ctx, member: Optional[Union[discord.Member, discord.User]] = None):
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)
        banner_url = user.banner.url if user.banner else None

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=color_primary
        )
        embed.set_image(url=user.display_avatar.url)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        links = []
        if user.display_avatar.is_animated():
            links.append(f"[GIF]({user.display_avatar.with_format('gif').url})")
        links.extend([
            f"[PNG]({user.display_avatar.with_format('png').url})",
            f"[JPG]({user.display_avatar.with_format('jpg').url})",
            f"[WEBP]({user.display_avatar.with_format('webp').url})"
        ])
        embed.description = "**Download:** " + " · ".join(links)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        view = discord.ui.View()
        if banner_url:
            view.add_item(discord.ui.Button(label="Banner", style=discord.ButtonStyle.secondary, url=banner_url))
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=user.display_avatar.with_format('png').url))
        view.add_item(discord.ui.Button(label="JPEG", style=discord.ButtonStyle.link, url=user.display_avatar.with_format('jpg').url))
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   USER BANNER
    # ══════════════════════════════
    @commands.hybrid_command(name="userbanner", aliases=['banneruser'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def user_banner_cmd(self, ctx, member: Optional[Union[discord.Member, discord.User]] = None):
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)

        if not user.banner:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"**{member.display_name}** has no profile banner.",
                    color=color_primary
                )
            )

        embed = discord.Embed(title=f"{member.display_name}'s Banner", color=color_primary)
        embed.set_image(url=user.banner.url)
        embed.description = (
            "**Download:** "
            f"[PNG]({user.banner.with_format('png').url}) · "
            f"[JPG]({user.banner.with_format('jpg').url}) · "
            f"[WEBP]({user.banner.with_format('webp').url})"
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=user.banner.with_format('png').url))
        view.add_item(discord.ui.Button(label="JPEG", style=discord.ButtonStyle.link, url=user.banner.with_format('jpg').url))
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   SERVER ICON
    # ══════════════════════════════
    @commands.hybrid_command(name="servericon")
    async def servericon(self, ctx):
        if not ctx.guild.icon:
            return await ctx.reply(embed=discord.Embed(description="This server has no icon.", color=color_primary))

        icon = ctx.guild.icon
        embed = discord.Embed(title=f"{ctx.guild.name} — Server Icon", color=color_primary)
        embed.set_image(url=icon.url)
        embed.description = (
            "**Download:** "
            f"[PNG]({icon.with_format('png').url}) · "
            f"[JPG]({icon.with_format('jpg').url}) · "
            f"[WEBP]({icon.with_format('webp').url})"
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=icon.with_format("png").url))
        view.add_item(discord.ui.Button(label="JPEG", style=discord.ButtonStyle.link, url=icon.with_format("jpg").url))
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   SERVER BANNER
    # ══════════════════════════════
    @commands.hybrid_command(name="serverbanner")
    async def serverbanner(self, ctx):
        if not ctx.guild.banner:
            return await ctx.reply(embed=discord.Embed(description="This server has no banner.", color=color_primary))

        banner = ctx.guild.banner
        embed = discord.Embed(title=f"{ctx.guild.name} — Server Banner", color=color_primary)
        embed.set_image(url=banner.url)
        embed.description = (
            "**Download:** "
            f"[PNG]({banner.with_format('png').url}) · "
            f"[JPG]({banner.with_format('jpg').url}) · "
            f"[WEBP]({banner.with_format('webp').url})"
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=banner.with_format("png").url))
        view.add_item(discord.ui.Button(label="JPEG", style=discord.ButtonStyle.link, url=banner.with_format("jpg").url))
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   MEMBERCOUNT
    # ══════════════════════════════
    @commands.command(name="membercount", aliases=["mc"])
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def membercount(self, ctx):
        loading = discord.Embed(
            description=f"{E['loading']}  Fetching member stats...",
            color=color_primary
        )
        msg = await ctx.reply(embed=loading, mention_author=False)
        await asyncio.sleep(1)
        await msg.delete()
        await ctx.send(view=v2_memberstats_card(ctx.guild))

    # ══════════════════════════════
    #   POLL
    # ══════════════════════════════
    @commands.hybrid_command(name="poll")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def poll(self, ctx, *, question):
        loading = discord.Embed(
            description=f"{E['loading']}  Creating poll...",
            color=color_primary
        )
        msg = await ctx.reply(embed=loading, mention_author=False)
        await asyncio.sleep(1)
        await msg.delete()
        sent = await ctx.send(view=v2_poll_card(ctx.author, question))
        await sent.add_reaction("✅")
        await sent.add_reaction("❌")

    # ══════════════════════════════
    #   HACK  (fun — realistic feel)
    # ══════════════════════════════
    @commands.command(name="hack")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def hack(self, ctx, member: discord.Member):
        steps = [
            f"Connecting to server...",
            f"Bypassing firewall of **{member.display_name}**...",
            f"Extracting credentials...",
            f"Access granted. Compiling data...",
        ]
        msg = await ctx.send(f"```\n{steps[0]}\n```")
        for step in steps[1:]:
            await asyncio.sleep(1.2)
            await msg.edit(content=f"```\n{step}\n```")

        await asyncio.sleep(1)

        stringi = member.name
        random_pass = random.choice(lawda)
        random_pass2 = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
        email = f"{''.join(l for l in stringi if l.isalnum())}{random_pass}@gmail.com"
        password = f"{member.name}@{random_pass2}"

        await msg.delete()
        await ctx.reply(view=v2_hack_card(member, email, password))

    # ══════════════════════════════
    #   TOKEN  (fun — realistic feel)
    # ══════════════════════════════
    @commands.command(name="token")
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def token(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        msg = await ctx.send(f"```\nScanning {user.display_name}'s session...\n```")
        await asyncio.sleep(1.5)
        await msg.edit(content=f"```\nToken found. Decrypting...\n```")
        await asyncio.sleep(1)
        await msg.delete()

        token_list = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        token = ''.join(random.choices(token_list, k=59))
        await ctx.reply(view=v2_token_card(user, token))

    # ══════════════════════════════
    #   USERS
    # ══════════════════════════════
    @commands.command(name="users")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def users(self, ctx):
        loading = discord.Embed(
            description=f"{E['loading']}  Fetching global stats...",
            color=color_primary
        )
        msg = await ctx.reply(embed=loading, mention_author=False)
        await asyncio.sleep(1)
        total = sum(g.member_count for g in self.bot.guilds if g.member_count)
        guilds = len(self.bot.guilds)
        await msg.delete()
        await ctx.send(view=v2_users_card(total, guilds, self.bot.user.name, self.bot.user))

    # ══════════════════════════════
    #   WIZZ  (fun — realistic feel)
    # ══════════════════════════════
    @commands.command(name="wizz")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def wizz(self, ctx):
        steps = [
            f"Initializing wizz on **{ctx.guild.name}**...",
            f"Deleting **{len(ctx.guild.roles)}** roles...",
            f"Deleting **{len(ctx.guild.channels)}** channels...",
            "Removing webhooks and emojis...",
            "Installing ban wave...",
        ]
        msg = await ctx.send(f"```\n{steps[0]}\n```")
        for step in steps[1:]:
            await asyncio.sleep(1)
            await msg.edit(content=f"```\n{step}\n```")

        await asyncio.sleep(1)
        await msg.delete()
        await ctx.reply(view=v2_wizz_card(ctx.guild))

    # ══════════════════════════════
    #   URBAN
    # ══════════════════════════════
    @commands.command(name="urban")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def urban(self, ctx, *, phrase):
        async with self.aiohttp.get(f"http://api.urbandictionary.com/v0/define?term={phrase}") as resp:
            data = await resp.json()
            if data['list']:
                e = data['list'][0]
                definition = e['definition'].replace('[', '').replace(']', '')
                example = e['example'].replace('[', '').replace(']', '')
                await ctx.reply(view=v2_urban_card(phrase, definition, example, e['author'], e['written_on']))
            else:
                await ctx.reply(embed=discord.Embed(description=f"No definition found for **{phrase}**.", color=color_primary))

    # ══════════════════════════════
    #   INVITE  (loading → generated image card)
    # ══════════════════════════════
    @commands.command(name="invite", aliases=['invite-bot'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def invite(self, ctx):
        loading = discord.Embed(
            description="<a:CupidXloading:1474386958741536891>  Generating invite card...",
            color=color_primary
        )
        msg = await ctx.reply(embed=loading, mention_author=False)

        try:
            avatar_bytes = None
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        str(self.bot.user.display_avatar.with_format("png").with_size(256))
                    ) as r:
                        if r.status == 200:
                            avatar_bytes = await r.read()
            except Exception:
                pass

            image_buf = await self.bot.loop.run_in_executor(
                None, _generate_invite_image, avatar_bytes
            )

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Invite CupidX",   style=discord.ButtonStyle.link, url=BOT_INVITE))
            view.add_item(discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=SUPPORT_SERVER))

            file = discord.File(image_buf, filename="invite.png")
            await msg.delete()
            await ctx.reply(file=file, view=view, mention_author=False)

        except Exception as e:
            import traceback; traceback.print_exc()
            embed = discord.Embed(
                title="Invite CupidX",
                description=f"**Requested by:** {ctx.author.mention}\n\n[Invite Bot]({BOT_INVITE}) • [Support]({SUPPORT_SERVER})",
                color=color_primary
            )
            await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
