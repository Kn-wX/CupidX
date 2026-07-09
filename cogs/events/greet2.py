import discord
import aiosqlite
import json
import re
import io
import asyncio
import aiohttp
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ══════════════════════════════════════════════
#   WELCOME / LEAVE ══════════════════════════════════════════════

_W, _H = 1000, 340

def _make_welcome_card(
    avatar_bytes: bytes,
    username: str,
    member_count: int,
    mode: str = "welcome",   # "welcome" or "leave"
) -> io.BytesIO:

    W, H = _W, _H

    # ── 1. Background: avatar stretched + heavy blur + darken ──
    try:
        bg_src = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((W, H), Image.LANCZOS)
    except Exception:
        bg_src = Image.new("RGBA", (W, H), (30, 30, 35, 255))

    bg = bg_src.filter(ImageFilter.GaussianBlur(radius=28))
    # darken overlay
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 155))
    bg = Image.alpha_composite(bg, dark)

    # ── 2. Rounded card panel ──
    card_margin = 22
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [card_margin, card_margin, W - card_margin, H - card_margin],
        radius=28,
        fill=(15, 15, 18, 210),
        outline=(60, 60, 70, 180),
        width=2
    )
    img = Image.alpha_composite(bg, card)
    draw = ImageDraw.Draw(img)

    # ── 3. Circular avatar (left side) ──
    AV_CX = 160
    AV_CY = H // 2
    AV_R  = 100

    # white ring
    for t, a in [(6, 60), (4, 130), (2, 220), (1, 255)]:
        draw.ellipse(
            [AV_CX - AV_R - t, AV_CY - AV_R - t,
             AV_CX + AV_R + t, AV_CY + AV_R + t],
            outline=(255, 255, 255, a), width=2
        )

    # avatar circle
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((AV_R * 2, AV_R * 2), Image.LANCZOS)
        mask = Image.new("L", (AV_R * 2, AV_R * 2), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, AV_R * 2, AV_R * 2], fill=255)
        av.putalpha(mask)
        img.paste(av, (AV_CX - AV_R, AV_CY - AV_R), av)
        draw = ImageDraw.Draw(img)
    except Exception:
        draw.ellipse(
            [AV_CX - AV_R, AV_CY - AV_R, AV_CX + AV_R, AV_CY + AV_R],
            fill=(40, 40, 45, 255)
        )

    # ── 4. Text (right side) ──
    TX = AV_CX + AV_R + 50   # text start x

    try:
        f_label   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",         22)
        f_name    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    62)
        f_badge   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    17)
    except Exception:
        f_label = f_name = f_badge = ImageFont.load_default()

    label_text = "Welcome" if mode == "welcome" else "Goodbye"
    label_color = (200, 200, 210, 255)

    # "Welcome" / "Goodbye" label
    draw.text((TX, AV_CY - 88), label_text, font=f_label, fill=label_color)

    # Username — clip if too long
    name = username if len(username) <= 18 else username[:16] + "…"
    draw.text((TX, AV_CY - 58), name, font=f_name, fill=(255, 255, 255, 255))

    # underline
    name_w = int(draw.textlength(name, font=f_name))
    uy = AV_CY - 58 + 68
    draw.rounded_rectangle([TX, uy, TX + name_w, uy + 3], radius=2, fill=(255, 255, 255, 180))

    # MEMBER #XXXX badge
    badge_text = f"MEMBER #{member_count:,}"
    badge_w = int(draw.textlength(badge_text, font=f_badge)) + 28
    badge_h = 34
    badge_x = TX
    badge_y = uy + 16
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=badge_h // 2,
        fill=(0, 0, 0, 0),
        outline=(200, 200, 210, 160),
        width=2
    )
    draw.text(
        (badge_x + 14, badge_y + 7),
        badge_text, font=f_badge, fill=(220, 220, 230, 255)
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def _fetch_avatar(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status == 200:
                    return await r.read()
    except Exception:
        pass
    return None


class greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.join_queue = {}
        self.processing = set()

    async def safe_format(self, text, placeholders):
        placeholders_lower = {k.lower(): v for k, v in placeholders.items()}
        def replace_var(match):
            var_name = match.group(1).lower()
            return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))
        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    def _build_placeholders(self, member, guild):
        return {
            "user": member.mention,
            "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
            "user_name": member.name,
            "user_id": member.id,
            "user_nick": member.display_name,
            "user_joindate": member.joined_at.strftime("%a, %b %d, %Y") if member.joined_at else "Unknown",
            "user_createdate": member.created_at.strftime("%a, %b %d, %Y"),
            "server_name": guild.name,
            "server_id": guild.id,
            "server_membercount": guild.member_count,
            "server_icon": guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(discord.utils.utcnow()),
        }

    # ========== ON MEMBER JOIN ==========

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id not in self.join_queue:
            self.join_queue[member.guild.id] = []
        self.join_queue[member.guild.id].append(member)
        if member.guild.id not in self.processing:
            self.processing.add(member.guild.id)
            await self.process_queue(member.guild)

    async def process_queue(self, guild):
        while self.join_queue[guild.id]:
            member = self.join_queue[guild.id].pop(0)
            async with aiosqlite.connect("db/welcome.db") as db:
                async with db.execute(
                    "SELECT welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration FROM welcome WHERE guild_id = ?",
                    (guild.id,)
                ) as cursor:
                    row = await cursor.fetchone()

            if row is None:
                continue

            welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration = row
            welcome_channel = self.bot.get_channel(channel_id) if channel_id else None
            if not welcome_channel:
                continue

            placeholders = self._build_placeholders(member, guild)

            try:
                sent_message = None

                if welcome_type == "simple" and welcome_message:
                    content = await self.safe_format(welcome_message, placeholders)
                    sent_message = await welcome_channel.send(content=content)

                elif welcome_type == "embed" and embed_data:
                    embed_info = json.loads(embed_data)
                    color_value = embed_info.get("color", None)
                    embed_color = 0x2f3136
                    if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                        embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                    elif isinstance(color_value, int):
                        embed_color = discord.Color(color_value)

                    content = await self.safe_format(embed_info.get("message", ""), placeholders) or None
                    embed = discord.Embed(
                        title=await self.safe_format(embed_info.get("title", ""), placeholders),
                        description=await self.safe_format(embed_info.get("description", ""), placeholders),
                        color=embed_color
                    )
                    embed.timestamp = discord.utils.utcnow()
                    if embed_info.get("footer_text"):
                        embed.set_footer(
                            text=await self.safe_format(embed_info["footer_text"], placeholders),
                            icon_url=await self.safe_format(embed_info.get("footer_icon", ""), placeholders)
                        )
                    if embed_info.get("author_name"):
                        embed.set_author(
                            name=await self.safe_format(embed_info["author_name"], placeholders),
                            icon_url=await self.safe_format(embed_info.get("author_icon", ""), placeholders)
                        )
                    if embed_info.get("thumbnail"):
                        embed.set_thumbnail(url=await self.safe_format(embed_info["thumbnail"], placeholders))
                    if embed_info.get("image"):
                        embed.set_image(url=await self.safe_format(embed_info["image"], placeholders))
                    sent_message = await welcome_channel.send(content=content, embed=embed)

                elif welcome_type == "image":
                    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                    avatar_bytes = await _fetch_avatar(avatar_url)
                    img_cfg = json.loads(embed_data) if embed_data else {}
                    bg_bytes = None
                    if img_cfg.get("bg_type") == "custom" and img_cfg.get("custom_bg_url"):
                        bg_bytes = await _fetch_avatar(img_cfg["custom_bg_url"])
                    # Resolve placeholders
                    if img_cfg.get("label"):
                        img_cfg["label"] = await self.safe_format(img_cfg["label"], placeholders)
                    if img_cfg.get("footer_text"):
                        img_cfg["footer_text"] = await self.safe_format(img_cfg["footer_text"], placeholders)
                    msg_content = await self.safe_format(img_cfg.get("message") or "", placeholders) or None
                    buf = await self.bot.loop.run_in_executor(
                        None, _make_welcome_card,
                        avatar_bytes or b"",
                        member.name,
                        guild.member_count,
                        "welcome",
                        img_cfg,
                        bg_bytes
                    )
                    file = discord.File(buf, filename="welcome.png")
                    sent_message = await welcome_channel.send(
                        content=msg_content,
                        file=file
                    )

                if sent_message and auto_delete_duration:
                    await sent_message.delete(delay=auto_delete_duration)

            except discord.Forbidden:
                continue
            except discord.HTTPException as e:
                if e.code == 50035 or e.status == 429:
                    await asyncio.sleep(1)
                    self.join_queue[guild.id].append(member)
                    continue

            await asyncio.sleep(2)

        self.processing.remove(guild.id)

    # ========== ON MEMBER REMOVE (LEAVE) ==========

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            async with aiosqlite.connect("db/welcome.db") as db:
                async with db.execute(
                    "SELECT leave_type, leave_message, channel_id, embed_data, auto_delete_duration FROM leave WHERE guild_id = ?",
                    (member.guild.id,)
                ) as cursor:
                    config = await cursor.fetchone()

            if not config or not config[0]:
                return

            leave_type, leave_message, channel_id, embed_data, auto_delete = config
            channel = self.bot.get_channel(channel_id) if channel_id else None
            if not channel:
                return

            placeholders = self._build_placeholders(member, member.guild)
            sent_message = None

            if leave_type == "simple" and leave_message:
                formatted = await self.safe_format(leave_message, placeholders)
                sent_message = await channel.send(formatted)

            elif leave_type == "embed" and embed_data:
                embed_info = json.loads(embed_data)
                color_value = embed_info.get("color", None)
                embed_color = 0x2f3136
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                elif isinstance(color_value, int):
                    embed_color = discord.Color(color_value)

                content = await self.safe_format(embed_info.get("message", ""), placeholders) or None
                embed = discord.Embed(
                    title=await self.safe_format(embed_info.get("title", ""), placeholders),
                    description=await self.safe_format(embed_info.get("description", ""), placeholders),
                    color=embed_color
                )
                embed.timestamp = discord.utils.utcnow()
                if embed_info.get("footer_text"):
                    embed.set_footer(
                        text=await self.safe_format(embed_info["footer_text"], placeholders),
                        icon_url=await self.safe_format(embed_info.get("footer_icon", ""), placeholders)
                    )
                if embed_info.get("author_name"):
                    embed.set_author(
                        name=await self.safe_format(embed_info["author_name"], placeholders),
                        icon_url=await self.safe_format(embed_info.get("author_icon", ""), placeholders)
                    )
                if embed_info.get("thumbnail"):
                    embed.set_thumbnail(url=await self.safe_format(embed_info["thumbnail"], placeholders))
                if embed_info.get("image"):
                    embed.set_image(url=await self.safe_format(embed_info["image"], placeholders))
                sent_message = await channel.send(content=content, embed=embed)

            elif leave_type == "image":
                avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                avatar_bytes = await _fetch_avatar(avatar_url)
                img_cfg = json.loads(embed_data) if embed_data else {}
                bg_bytes = None
                if img_cfg.get("bg_type") == "custom" and img_cfg.get("custom_bg_url"):
                    bg_bytes = await _fetch_avatar(img_cfg["custom_bg_url"])
                if img_cfg.get("label"):
                    img_cfg["label"] = await self.safe_format(img_cfg["label"], placeholders)
                if img_cfg.get("footer_text"):
                    img_cfg["footer_text"] = await self.safe_format(img_cfg["footer_text"], placeholders)
                buf = await self.bot.loop.run_in_executor(
                    None, _make_welcome_card,
                    avatar_bytes or b"",
                    member.display_name,
                    member.guild.member_count,
                    "leave",
                    img_cfg,
                    bg_bytes
                )
                file = discord.File(buf, filename="leave.png")
                sent_message = await channel.send(file=file)

            if sent_message and auto_delete:
                await sent_message.delete(delay=auto_delete)

        except Exception as e:
            print(f"[LEAVE ERROR] guild={member.guild.id} | {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(greet(bot))
