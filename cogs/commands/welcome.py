import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import aiosqlite
import asyncio
import re
import json
import io
import aiohttp
from datetime import datetime
from utils.Tools import *
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ══════════════════════════════════════════════
#   WELCOME / LEAVE IMAGE CARD GENERATOR
#   Custom image card with avatar background,
#   rounded panel, circular avatar, and text.
# ══════════════════════════════════════════════

_W, _H = 1000, 340

# Default image config
_DEFAULT_IMG_CONFIG = {
    "message":        None,       # Text above the image (e.g. "Hey {user}, welcome!")
    "label":          None,       # Custom label text on card (e.g. "Welcome to {server_name}!")
    "bg_type":        "avatar",   # "avatar" or "custom"
    "custom_bg_url":  None,       # URL if bg_type == "custom"
    "accent_color":   None,       # Hex string e.g. "FF6400" — ring + underline + badge color
    "footer_text":    None,       # Bottom footer text on card
}

def _hex_to_rgba(hex_str: str, alpha: int = 255):
    """Convert hex color string to RGBA tuple."""
    try:
        h = hex_str.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r, g, b, alpha)
    except Exception:
        return (255, 255, 255, alpha)

def _make_welcome_card(
    avatar_bytes: bytes,
    username: str,
    member_count: int,
    mode: str = "welcome",
    config: dict = None,
    bg_bytes: bytes = None,      # pre-fetched custom bg bytes
) -> io.BytesIO:
    W, H = _W, _H
    cfg = {**_DEFAULT_IMG_CONFIG, **(config or {})}

    # ── Accent color ──
    accent_hex = cfg.get("accent_color") or "FFFFFF"
    accent     = _hex_to_rgba(accent_hex, 255)
    accent_dim = _hex_to_rgba(accent_hex, 160)
    accent_glow= _hex_to_rgba(accent_hex, 60)

    # ── Background ──
    bg_source_bytes = avatar_bytes  # default: user avatar
    if cfg.get("bg_type") == "custom" and bg_bytes:
        bg_source_bytes = bg_bytes

    try:
        bg_src = Image.open(io.BytesIO(bg_source_bytes)).convert("RGBA").resize((W, H), Image.LANCZOS)
    except Exception:
        bg_src = Image.new("RGBA", (W, H), (30, 30, 35, 255))

    bg = bg_src.filter(ImageFilter.GaussianBlur(radius=28))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 155))
    bg = Image.alpha_composite(bg, dark)

    # ── Rounded card panel ──
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [22, 22, W - 22, H - 22], radius=28,
        fill=(15, 15, 18, 210),
        outline=(_hex_to_rgba(accent_hex, 80)),
        width=2
    )
    img = Image.alpha_composite(bg, card)
    draw = ImageDraw.Draw(img)

    # ── Circular avatar (left side) ──
    AV_CX, AV_CY, AV_R = 160, H // 2, 100

    # Accent-colored ring
    for t, a in [(6, 30), (4, 80), (2, 170), (1, 255)]:
        draw.ellipse(
            [AV_CX - AV_R - t, AV_CY - AV_R - t, AV_CX + AV_R + t, AV_CY + AV_R + t],
            outline=_hex_to_rgba(accent_hex, a), width=2
        )

    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AV_R * 2, AV_R * 2), Image.LANCZOS)
        mask = Image.new("L", (AV_R * 2, AV_R * 2), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, AV_R * 2, AV_R * 2], fill=255)
        av.putalpha(mask)
        img.paste(av, (AV_CX - AV_R, AV_CY - AV_R), av)
        draw = ImageDraw.Draw(img)
    except Exception:
        draw.ellipse([AV_CX - AV_R, AV_CY - AV_R, AV_CX + AV_R, AV_CY + AV_R], fill=(40, 40, 45, 255))

    # ── Text (right side) ──
    TX = AV_CX + AV_R + 50

    try:
        f_label  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      22)
        f_name   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62)
        f_badge  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
        f_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      14)
    except Exception:
        f_label = f_name = f_badge = f_footer = ImageFont.load_default()

    # Label (custom or default)
    default_label = "Welcome" if mode == "welcome" else "Goodbye"
    label_text = cfg.get("label") or default_label
    draw.text((TX, AV_CY - 92), label_text, font=f_label, fill=(200, 200, 210, 255))

    # Username
    name = username if len(username) <= 18 else username[:16] + "…"
    draw.text((TX, AV_CY - 58), name, font=f_name, fill=(255, 255, 255, 255))

    # Accent underline
    name_w = int(draw.textlength(name, font=f_name))
    uy = AV_CY - 58 + 68
    draw.rounded_rectangle([TX, uy, TX + name_w, uy + 3], radius=2, fill=accent)

    # MEMBER badge
    badge_text = f"MEMBER #{member_count:,}"
    badge_w    = int(draw.textlength(badge_text, font=f_badge)) + 28
    badge_h    = 34
    badge_y    = uy + 14
    draw.rounded_rectangle(
        [TX, badge_y, TX + badge_w, badge_y + badge_h],
        radius=badge_h // 2, fill=(0, 0, 0, 0),
        outline=accent_dim, width=2
    )
    draw.text((TX + 14, badge_y + 7), badge_text, font=f_badge, fill=(220, 220, 230, 255))

    # Footer text (bottom center of card)
    footer = cfg.get("footer_text")
    if footer:
        fw = int(draw.textlength(footer, font=f_footer))
        draw.text(((W - fw) // 2, H - 44), footer, font=f_footer, fill=(160, 160, 170, 255))

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


# ========== EMOJIS TOP PE ==========
class Emojis:
    TICK = "<:CupidXtick1:1474369967271968949> "
    CROSS = "<:CupidXCross:1473996646873436336> "
    WARN = "<:CupidXWarning:1474348304186867784> "
    INFO = "<a:CupidXping:1474771697289924721> "
    USER = "<:CupidXuser:1475151935379341382> "
    CHANNEL = "<:cupidxchannel:1475164013913702633> "
    SETTINGS = "<a:emojisetting:1476854070412316713> "
    EDIT = "<:CupidXIgnore:1487128712477675602> "
    TRASH = "<:CupidXdelete:1474795676251459748> "
    ARROW = "<:CupidXarrow:1474383919725150362> "
    HEART = "<:CupidXflower:1487021616612511846> "
    STAR = "<a:Star_Blue:1487146818553778389> "

class VariableButton(Button):
    def __init__(self, author, for_leave=False):
        super().__init__(label="Variables", style=discord.ButtonStyle.secondary)
        self.author = author
        self.for_leave = for_leave

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can use this button.", ephemeral=True)
            return

        variables = {
            "{user}": "Mentions the user (e.g., @UserName).",
            "{user_avatar}": "The user's avatar URL.",
            "{user_name}": "The user's username.",
            "{user_id}": "The user's ID number.",
            "{user_nick}": "The user's nickname in the server.",
            "{user_joindate}": "The user's join date in the server (formatted as Day, Month Day, Year).",
            "{user_createdate}": "The user's account creation date (formatted as Day, Month Day, Year).",
            "{server_name}": "The server's name.",
            "{server_id}": "The server's ID number.",
            "{server_membercount}": "The server's total member count.",
            "{server_icon}": "The server's icon URL."
        }
        
        event_type = "Leave" if self.for_leave else "Welcome"

        embed = discord.Embed(
            title=f"Available Placeholders - {event_type}",
            description="Use these placeholders in your message:",
            color=discord.Color(0xFCD005)
        )

        for var, desc in variables.items():
            embed.add_field(name=var, value=desc, inline=False)

        embed.set_footer(text="Add placeholders directly in the welcome message or embed fields.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Welcomer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self._create_tables())

    async def _create_tables(self):
        async with aiosqlite.connect("db/welcome.db") as db:
            # Original welcome table
            await db.execute("""
            CREATE TABLE IF NOT EXISTS welcome (
                guild_id INTEGER PRIMARY KEY,
                welcome_type TEXT,
                welcome_message TEXT,
                channel_id INTEGER,
                embed_data TEXT,
                auto_delete_duration INTEGER
            )
            """)
            # New leave table (same structure)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS leave (
                guild_id INTEGER PRIMARY KEY,
                leave_type TEXT,
                leave_message TEXT,
                channel_id INTEGER,
                embed_data TEXT,
                auto_delete_duration INTEGER
            )
            """)
            await db.commit()

    # ========== UTILITY FUNCTIONS ==========
    
    def safe_format(self, text, member, guild):
        if not text:
            return text
            
        placeholders = {
            "user": member.mention,
            "user_name": member.name,
            "user_id": str(member.id),
            "user_nick": member.display_name,
            "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
            "user_joindate": member.joined_at.strftime("%a, %b %d, %Y") if member.joined_at else "Unknown",
            "user_createdate": member.created_at.strftime("%a, %b %d, %Y"),
            "server_name": guild.name,
            "server_id": str(guild.id),
            "server_membercount": str(guild.member_count),
            "server_icon": guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(datetime.utcnow())
        }

        def replace_var(match):
            var_name = match.group(1).lower()
            return str(placeholders.get(var_name, f"{{{var_name}}}"))

        return re.sub(r"\{(\w+)\}", replace_var, text)

    async def get_welcome_config(self, guild_id):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM welcome WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone()

    async def get_leave_config(self, guild_id):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM leave WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone()

    # ========== EVENT LISTENERS ==========

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = await self.get_leave_config(member.guild.id)
        if not config or not config[1]:  # leave_type check
            return

        leave_type, message, channel_id, embed_data, auto_delete = config[1], config[2], config[3], config[4], config[5]
        channel = self.bot.get_channel(channel_id) if channel_id else None

        if not channel:
            return

        try:
            if leave_type == "simple" and message:
                formatted = self.safe_format(message, member, member.guild)
                msg = await channel.send(formatted)
                if auto_delete:
                    await msg.delete(delay=auto_delete)

            elif leave_type == "embed" and embed_data:
                embed_info = json.loads(embed_data)
                content = self.safe_format(embed_info.get("message", ""), member, member.guild) or None
                
                embed = discord.Embed(
                    title=self.safe_format(embed_info.get("title"), member, member.guild),
                    description=self.safe_format(embed_info.get("description"), member, member.guild),
                    color=discord.Color(embed_info["color"]) if embed_info.get("color") else discord.Color(0x2f3136)
                )
                embed.timestamp = discord.utils.utcnow()

                if embed_info.get("footer_text"):
                    embed.set_footer(
                        text=self.safe_format(embed_info["footer_text"], member, member.guild),
                        icon_url=self.safe_format(embed_info.get("footer_icon"), member, member.guild)
                    )
                if embed_info.get("author_name"):
                    embed.set_author(
                        name=self.safe_format(embed_info["author_name"], member, member.guild),
                        icon_url=self.safe_format(embed_info.get("author_icon"), member, member.guild)
                    )
                if embed_info.get("thumbnail"):
                    embed.set_thumbnail(url=self.safe_format(embed_info["thumbnail"], member, member.guild))
                if embed_info.get("image"):
                    embed.set_image(url=self.safe_format(embed_info["image"], member, member.guild))

                msg = await channel.send(content=content, embed=embed)
                if auto_delete:
                    await msg.delete(delay=auto_delete)

        except Exception as e:
            print(f"Leave error in {member.guild.id}: {e}")

    # ========== HYBRID GROUP - GREET (ORIGINAL CODE EXACT) ==========

    @commands.hybrid_group(invoke_without_command=True, name="greet", help="Shows all the greet commands.")
    @blacklist_check()
    @ignore_check()
    async def greet(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = discord.Embed(
                title="👋 Welcomer Commands",
                description="Setup and manage welcome messages for new members.",
                color=0x134E5E
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            
            sub_cmds = (
                f"`{ctx.prefix}greet setup` - Configure a welcome message\n"
                f"`{ctx.prefix}greet reset` - Delete welcome configuration\n"
                f"`{ctx.prefix}greet channel` - Set the welcome channel\n"
                f"`{ctx.prefix}greet test` - Preview your welcome message\n"
                f"`{ctx.prefix}greet config` - View current configuration\n"
                f"`{ctx.prefix}greet autodelete` - Set message auto-delete timer\n"
                f"`{ctx.prefix}greet edit` - Modify existing settings"
            )
            embed.add_field(name="Subcommands", value=sub_cmds, inline=False)
            embed.set_footer(text="cupidx HQ • cupidx", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    # ========== HYBRID GROUP - LEAVE (SAME AS GREET) ==========

    @commands.hybrid_group(invoke_without_command=True, name="leave", help="Shows all the leave commands.")
    @blacklist_check()
    @ignore_check()
    async def leave(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = discord.Embed(
                title="👋 Leave Commands",
                description="Setup and manage leave messages for departing members.",
                color=0x134E5E
            )
            embed.set_author(name="CupidX Help Center", icon_url=self.bot.user.display_avatar.url)
            
            sub_cmds = (
                f"`{ctx.prefix}leave setup` - Configure a leave message\n"
                f"`{ctx.prefix}leave reset` - Delete leave configuration\n"
                f"`{ctx.prefix}leave channel` - Set the leave channel\n"
                f"`{ctx.prefix}leave test` - Preview your leave message\n"
                f"`{ctx.prefix}leave config` - View current configuration\n"
                f"`{ctx.prefix}leave autodelete` - Set message auto-delete timer\n"
                f"`{ctx.prefix}leave edit` - Modify existing settings"
            )
            embed.add_field(name="Subcommands", value=sub_cmds, inline=False)
            embed.set_footer(text="cupidx HQ • cupidx", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            ctx.command.reset_cooldown(ctx)

    # ========== GREET SETUP (ORIGINAL CODE EXACT) ==========

    @greet.command(name="setup", help="Configures a welcome message for new members joining the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_setup(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if row:
            error = discord.Embed(description=f"A welcome message has already been set in {ctx.guild.name}. Use `{ctx.prefix}greet reset` to reconfigure.", color=0xFCD005)
            error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        options_view = View(timeout=600)

        async def option_callback(interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.defer()

            if button.custom_id == "simple":
                await interaction.message.delete()
                await self.simple_setup(ctx)
                
            elif button.custom_id == "embed":
                await interaction.message.delete()
                await self.embed_setup(ctx)
            elif button.custom_id == "image":
                await interaction.message.delete()
                if not await self._is_premium(ctx.guild.id):
                    no_prem = discord.Embed(
                        description="**Image Card** is a **Premium-only** feature.\nUpgrade your server with `premium redeem <code>` or `premium trial`.",
                        color=0xFCD005
                    )
                    no_prem.set_author(name="Premium Required", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
                    return await ctx.send(embed=no_prem)
                await self.image_setup(ctx)
            elif button.custom_id == "cancel":
                await interaction.message.delete()

        button_simple = Button(label="Simple", style=discord.ButtonStyle.success, custom_id="simple")
        button_simple.callback = lambda interaction: option_callback(interaction, button_simple)
        options_view.add_item(button_simple)

        button_embed = Button(label="Embed", style=discord.ButtonStyle.success, custom_id="embed")
        button_embed.callback = lambda interaction: option_callback(interaction, button_embed)
        options_view.add_item(button_embed)

        button_image = Button(label="Image Card", style=discord.ButtonStyle.primary, custom_id="image")
        button_image.callback = lambda interaction: option_callback(interaction, button_image)
        options_view.add_item(button_image)

        button_cancel = Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
        button_cancel.callback = lambda interaction: option_callback(interaction, button_cancel)
        options_view.add_item(button_cancel)

        embed = discord.Embed(
            title="Welcome Message Setup",
            description="Choose the type of welcome message you want to create:",
            color=0xFCD005
        )

        embed.add_field(
            name=" Simple",
            value="Send a plain text welcome message. You can use placeholders to personalize it.\n\n",
            inline=False
        )
        embed.add_field(
            name=" Embed",
            value="Send a welcome message in an embed format. You can customize the embed with a title, description, image, etc.",
            inline=False
        )
        embed.add_field(
            name=" Image Card",
            value="Send a beautiful image card with the user's avatar as background.",
            inline=False
        )

        embed.set_footer(text="Click the buttons below to choose the welcome message type.", icon_url=self.bot.user.display_avatar.url)
        
        await ctx.send(embed=embed, view=options_view)

    # ========== LEAVE SETUP (SAME AS GREET) ==========

    @leave.command(name="setup", help="Configures a leave message for members leaving the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_setup(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM leave WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if row:
            error = discord.Embed(description=f"A leave message has already been set in {ctx.guild.name}. Use `{ctx.prefix}leave reset` to reconfigure.", color=0xFCD005)
            error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        options_view = View(timeout=600)

        async def option_callback(interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.defer()

            if button.custom_id == "simple":
                await interaction.message.delete()
                await self.simple_setup_leave(ctx)
                
            elif button.custom_id == "embed":
                await interaction.message.delete()
                await self.embed_setup_leave(ctx)
            elif button.custom_id == "image":
                await interaction.message.delete()
                if not await self._is_premium(ctx.guild.id):
                    no_prem = discord.Embed(
                        description="**Image Card** is a **Premium-only** feature.\nUpgrade your server with `premium redeem <code>` or `premium trial`.",
                        color=0xFCD005
                    )
                    no_prem.set_author(name="Premium Required", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
                    return await ctx.send(embed=no_prem)
                await self.image_setup_leave(ctx)
            elif button.custom_id == "cancel":
                await interaction.message.delete()

        button_simple = Button(label="Simple", style=discord.ButtonStyle.success, custom_id="simple")
        button_simple.callback = lambda interaction: option_callback(interaction, button_simple)
        options_view.add_item(button_simple)

        button_embed = Button(label="Embed", style=discord.ButtonStyle.success, custom_id="embed")
        button_embed.callback = lambda interaction: option_callback(interaction, button_embed)
        options_view.add_item(button_embed)

        button_image = Button(label="Image Card", style=discord.ButtonStyle.primary, custom_id="image")
        button_image.callback = lambda interaction: option_callback(interaction, button_image)
        options_view.add_item(button_image)

        button_cancel = Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
        button_cancel.callback = lambda interaction: option_callback(interaction, button_cancel)
        options_view.add_item(button_cancel)

        embed = discord.Embed(
            title="Leave Message Setup",
            description="Choose the type of leave message you want to create:",
            color=0xFCD005
        )

        embed.add_field(
            name=" Simple",
            value="Send a plain text leave message. You can use placeholders to personalize it.\n\n",
            inline=False
        )
        embed.add_field(
            name=" Embed",
            value="Send a leave message in an embed format. You can customize the embed with a title, description, image, etc.",
            inline=False
        )
        embed.add_field(
            name=" Image Card",
            value="Send a beautiful image card with the user's avatar as background.",
            inline=False
        )

        embed.set_footer(text="Click the buttons below to choose the leave message type.", icon_url=self.bot.user.display_avatar.url)
        
        await ctx.send(embed=embed, view=options_view)

    # ========== SIMPLE SETUP (WELCOME - ORIGINAL) ==========

    async def simple_setup(self, ctx):
        setup_view = View(timeout=600)
        first = View(timeout=600)
        message_content = []

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}

            def replace_var(match):
                var_name = match.group(1).lower()
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        async def update_preview(content):
            preview = safe_format(content)
            await preview_message.edit(content=f"**Preview:** {preview}", view=setup_view)

        first.add_item(VariableButton(ctx.author))

        preview_message = await ctx.send("__**Simple Message Setup**__ \nEnter your welcome message here:", view=first)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            if message_content:
                await self._save_welcome_data(ctx.guild.id, "simple", message_content[0])
                await interaction.response.send_message(f"{Emojis.TICK} Welcome message setup completed!")
                for item in setup_view.children:
                    item.disabled = True
                await preview_message.edit(view=setup_view)
            else:
                await interaction.response.send_message("No message entered to submit.", ephemeral=True)

        async def edit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.defer()
            await ctx.send("Enter the updated welcome message:")
            try:
                msg = await self.bot.wait_for("message", timeout=600, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                message_content.clear()
                message_content.append(msg.content)
                await msg.delete()
                await update_preview(msg.content)
            except asyncio.TimeoutError:
                await ctx.send("Editing timed out.")

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)

        edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
        edit_button.callback = edit_callback
        setup_view.add_item(edit_button)
        setup_view.add_item(VariableButton(ctx.author))

        cancel_button = Button(emoji="<:icons_plus:1328966531140288524>", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        try:
            msg = await self.bot.wait_for("message", timeout=600, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            message_content.append(msg.content)
            await msg.delete()
            await update_preview(msg.content)
        except asyncio.TimeoutError:
            await ctx.send("Setup timed out.")

    # ========== SIMPLE SETUP (LEAVE) ==========

    async def simple_setup_leave(self, ctx):
        setup_view = View(timeout=600)
        first = View(timeout=600)
        message_content = []

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}

            def replace_var(match):
                var_name = match.group(1).lower()
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        async def update_preview(content):
            preview = safe_format(content)
            await preview_message.edit(content=f"**Preview:** {preview}", view=setup_view)

        first.add_item(VariableButton(ctx.author, for_leave=True))

        preview_message = await ctx.send("__**Simple Leave Message Setup**__ \nEnter your leave message here:", view=first)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            if message_content:
                await self._save_leave_data(ctx.guild.id, "simple", message_content[0])
                await interaction.response.send_message(f"{Emojis.TICK} Leave message setup completed!")
                for item in setup_view.children:
                    item.disabled = True
                await preview_message.edit(view=setup_view)
            else:
                await interaction.response.send_message("No message entered to submit.", ephemeral=True)

        async def edit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.defer()
            await ctx.send("Enter the updated leave message:")
            try:
                msg = await self.bot.wait_for("message", timeout=600, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                message_content.clear()
                message_content.append(msg.content)
                await msg.delete()
                await update_preview(msg.content)
            except asyncio.TimeoutError:
                await ctx.send("Editing timed out.")

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)

        edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
        edit_button.callback = edit_callback
        setup_view.add_item(edit_button)
        setup_view.add_item(VariableButton(ctx.author, for_leave=True))

        cancel_button = Button(emoji="<:icons_plus:1328966531140288524>", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        try:
            msg = await self.bot.wait_for("message", timeout=600, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            message_content.append(msg.content)
            await msg.delete()
            await update_preview(msg.content)
        except asyncio.TimeoutError:
            await ctx.send("Setup timed out.")

    # ========== SAVE FUNCTIONS ==========

    async def _save_welcome_data(self, guild_id, welcome_type, message, embed_data=None):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT channel_id, auto_delete_duration FROM welcome WHERE guild_id = ?", (guild_id,)) as cursor:
                existing = await cursor.fetchone()
            existing_channel_id = existing[0] if existing else None
            existing_auto_delete = existing[1] if existing else None
            await db.execute("""
            INSERT OR REPLACE INTO welcome (guild_id, welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, welcome_type, message, existing_channel_id, json.dumps(embed_data) if embed_data else None, existing_auto_delete))
            await db.commit()

    async def _save_leave_data(self, guild_id, leave_type, message, embed_data=None):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT channel_id, auto_delete_duration FROM leave WHERE guild_id = ?", (guild_id,)) as cursor:
                existing = await cursor.fetchone()
            existing_channel_id = existing[0] if existing else None
            existing_auto_delete = existing[1] if existing else None
            await db.execute("""
            INSERT OR REPLACE INTO leave (guild_id, leave_type, leave_message, channel_id, embed_data, auto_delete_duration)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, leave_type, message, existing_channel_id, json.dumps(embed_data) if embed_data else None, existing_auto_delete))
            await db.commit()

    # ========== PREMIUM CHECK HELPER ==========

    async def _is_premium(self, guild_id: int) -> bool:
        try:
            premium_cog = self.bot.get_cog("Premium")
            if premium_cog:
                return await premium_cog.is_premium(guild_id)
        except Exception:
            pass
        return False

    # ========== IMAGE SETUP (WELCOME) ==========

    async def image_setup(self, ctx):
        img_config = {
            "message":       None,
            "title":         None,
            "label":         None,
            "bg_type":       "avatar",
            "custom_bg_url": None,
            "accent_color":  None,
            "footer_text":   None,
        }

        def config_summary():
            lines = [
                f"**Message:** {img_config['message'] or '`None` (above image)'}",
                f"**Title:** {img_config['title'] or '`None` (default)'}",
                f"**Label:** {img_config['label'] or '`Welcome` (default)'}",
                f"**Background:** {img_config['bg_type']} {'`' + img_config['custom_bg_url'] + '`' if img_config.get('custom_bg_url') else ''}",
                f"**Accent Color:** {'`#' + img_config['accent_color'] + '`' if img_config.get('accent_color') else '`White (default)`'}",
                f"**Footer Text:** {img_config['footer_text'] or '`None`'}",
            ]
            return "\n".join(lines)

        setup_view = View(timeout=120)

        embed = discord.Embed(
            title="Image Card Setup — Welcome",
            description=f"Configure your welcome image card.\n\n{config_summary()}",
            color=0xFCD005
        )
        embed.set_footer(text="Use the dropdown to edit each field, then Submit.", icon_url=self.bot.user.display_avatar.url)

        preview_message = await ctx.send(embed=embed, view=setup_view)

        async def on_timeout():
            try:
                for item in setup_view.children:
                    item.disabled = True
                timeout_embed = discord.Embed(
                    title="Image Card Setup — Welcome",
                    description=f"⏱️ Setup timed out due to inactivity.\n\n{config_summary()}",
                    color=0x555555
                )
                await preview_message.edit(embed=timeout_embed, view=None)
            except Exception:
                pass

        setup_view.on_timeout = on_timeout

        select_menu = Select(
            placeholder="Choose a field to edit",
            options=[
                discord.SelectOption(label="Message",         value="message",       description="Text above image (e.g. Hey {user}, welcome! supports {user} etc)"),
                discord.SelectOption(label="Title",           value="title",         description="Title shown at top of the embed message"),
                discord.SelectOption(label="Label Text",      value="label",         description="Text above username (e.g. Welcome to {server_name}!)"),
                discord.SelectOption(label="Background Type", value="bg_type",       description="avatar = user avatar, custom = your own image URL"),
                discord.SelectOption(label="Custom BG URL",   value="custom_bg_url", description="Image URL for background (only if bg_type = custom)"),
                discord.SelectOption(label="Accent Color",    value="accent_color",  description="Hex color for ring, underline & badge (e.g. FF6400)"),
                discord.SelectOption(label="Footer Text",     value="footer_text",   description="Small text at bottom of card"),
            ]
        )

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            selected = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected == "message":
                    await ctx.send("Enter message text above the image (supports `{user}`, `{server_name}`, `{user_name}` etc, or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["message"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                elif selected == "title":
                    await ctx.send("Enter the title text for the embed (or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["title"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                elif selected == "label":
                    await ctx.send("Enter label text (supports `{server_name}`, `{user_name}`):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["label"] = msg.content
                    await msg.delete()

                elif selected == "bg_type":
                    await ctx.send("Enter background type: `avatar` (user avatar) or `custom` (your own image URL):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    val = msg.content.strip().lower()
                    if val in ("avatar", "custom"):
                        img_config["bg_type"] = val
                    else:
                        await ctx.send("Invalid value. Use `avatar` or `custom`.")
                    await msg.delete()

                elif selected == "custom_bg_url":
                    await ctx.send("Enter a valid image URL for the background:")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    if msg.content.startswith("http"):
                        img_config["custom_bg_url"] = msg.content.strip()
                    else:
                        await ctx.send("Invalid URL. Must start with `http`.")
                    await msg.delete()

                elif selected == "accent_color":
                    await ctx.send("Enter a hex color code (e.g. `FF6400` or `#FF6400`):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    color_code = msg.content.strip().lstrip("#")
                    if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) == 6:
                        img_config["accent_color"] = color_code.upper()
                    else:
                        await ctx.send("Invalid hex color. Example: `FF6400`")
                    await msg.delete()

                elif selected == "footer_text":
                    await ctx.send("Enter footer text (or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["footer_text"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                embed.description = f"Configure your welcome image card.\n\n{config_summary()}"
                await preview_message.edit(embed=embed, view=setup_view)

            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond.")

        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        async def submit_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await self._save_welcome_data(ctx.guild.id, "image", "image", img_config)
            await interaction.response.send_message(f"{Emojis.TICK} Welcome image card configured! Use `{ctx.prefix}greet channel` to set the channel.", ephemeral=True)
            for item in setup_view.children:
                item.disabled = True
            await preview_message.edit(view=setup_view)

        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()
            await interaction.response.send_message("Setup cancelled.", ephemeral=True)

        submit_btn = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_btn.callback = submit_callback
        setup_view.add_item(submit_btn)

        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_btn.callback = cancel_callback
        setup_view.add_item(cancel_btn)

        await preview_message.edit(embed=embed, view=setup_view)

    # ========== IMAGE SETUP (LEAVE) ==========

    async def image_setup_leave(self, ctx):
        img_config = {
            "message":       None,
            "title":         None,
            "label":         None,
            "bg_type":       "avatar",
            "custom_bg_url": None,
            "accent_color":  None,
            "footer_text":   None,
        }

        def config_summary():
            lines = [
                f"**Message:** {img_config['message'] or '`None` (above image)'}",
                f"**Title:** {img_config['title'] or '`None` (default)'}",
                f"**Label:** {img_config['label'] or '`Goodbye` (default)'}",
                f"**Background:** {img_config['bg_type']} {'`' + img_config['custom_bg_url'] + '`' if img_config.get('custom_bg_url') else ''}",
                f"**Accent Color:** {'`#' + img_config['accent_color'] + '`' if img_config.get('accent_color') else '`White (default)`'}",
                f"**Footer Text:** {img_config['footer_text'] or '`None`'}",
            ]
            return "\n".join(lines)

        setup_view = View(timeout=120)

        embed = discord.Embed(
            title="Image Card Setup — Leave",
            description=f"Configure your leave image card.\n\n{config_summary()}",
            color=0xFCD005
        )
        embed.set_footer(text="Use the dropdown to edit each field, then Submit.", icon_url=self.bot.user.display_avatar.url)

        preview_message = await ctx.send(embed=embed, view=setup_view)

        async def on_timeout():
            try:
                for item in setup_view.children:
                    item.disabled = True
                timeout_embed = discord.Embed(
                    title="Image Card Setup — Leave",
                    description=f"⏱️ Setup timed out due to inactivity.\n\n{config_summary()}",
                    color=0x555555
                )
                await preview_message.edit(embed=timeout_embed, view=None)
            except Exception:
                pass

        setup_view.on_timeout = on_timeout

        select_menu = Select(
            placeholder="Choose a field to edit",
            options=[
                discord.SelectOption(label="Message",         value="message",       description="Text above image (e.g. Goodbye {user}! supports {user} etc)"),
                discord.SelectOption(label="Title",           value="title",         description="Title shown at top of the embed message"),
                discord.SelectOption(label="Label Text",      value="label",         description="Text above username (e.g. Goodbye from {server_name}!)"),
                discord.SelectOption(label="Background Type", value="bg_type",       description="avatar = user avatar, custom = your own image URL"),
                discord.SelectOption(label="Custom BG URL",   value="custom_bg_url", description="Image URL for background (only if bg_type = custom)"),
                discord.SelectOption(label="Accent Color",    value="accent_color",  description="Hex color for ring, underline & badge (e.g. FF6400)"),
                discord.SelectOption(label="Footer Text",     value="footer_text",   description="Small text at bottom of card"),
            ]
        )

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            selected = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected == "message":
                    await ctx.send("Enter message text above the image (supports `{user}`, `{server_name}`, `{user_name}` etc, or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["message"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                elif selected == "title":
                    await ctx.send("Enter the title text for the embed (or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["title"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                elif selected == "label":
                    await ctx.send("Enter label text (supports `{server_name}`, `{user_name}`):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["label"] = msg.content
                    await msg.delete()

                elif selected == "bg_type":
                    await ctx.send("Enter background type: `avatar` (user avatar) or `custom` (your own image URL):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    val = msg.content.strip().lower()
                    if val in ("avatar", "custom"):
                        img_config["bg_type"] = val
                    else:
                        await ctx.send("Invalid value. Use `avatar` or `custom`.")
                    await msg.delete()

                elif selected == "custom_bg_url":
                    await ctx.send("Enter a valid image URL for the background:")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    if msg.content.startswith("http"):
                        img_config["custom_bg_url"] = msg.content.strip()
                    else:
                        await ctx.send("Invalid URL. Must start with `http`.")
                    await msg.delete()

                elif selected == "accent_color":
                    await ctx.send("Enter a hex color code (e.g. `FF6400` or `#FF6400`):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    color_code = msg.content.strip().lstrip("#")
                    if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) == 6:
                        img_config["accent_color"] = color_code.upper()
                    else:
                        await ctx.send("Invalid hex color. Example: `FF6400`")
                    await msg.delete()

                elif selected == "footer_text":
                    await ctx.send("Enter footer text (or type `none` to remove):")
                    msg = await self.bot.wait_for("message", timeout=120, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    img_config["footer_text"] = None if msg.content.strip().lower() == "none" else msg.content
                    await msg.delete()

                embed.description = f"Configure your leave image card.\n\n{config_summary()}"
                await preview_message.edit(embed=embed, view=setup_view)

            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond.")

        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        async def submit_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await self._save_leave_data(ctx.guild.id, "image", "image", img_config)
            await interaction.response.send_message(f"{Emojis.TICK} Leave image card configured! Use `{ctx.prefix}leave channel` to set the channel.", ephemeral=True)
            for item in setup_view.children:
                item.disabled = True
            await preview_message.edit(view=setup_view)

        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()
            await interaction.response.send_message("Setup cancelled.", ephemeral=True)

        submit_btn = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_btn.callback = submit_callback
        setup_view.add_item(submit_btn)

        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_btn.callback = cancel_callback
        setup_view.add_item(cancel_btn)

        await preview_message.edit(embed=embed, view=setup_view)

    # ========== EMBED SETUP (WELCOME - ORIGINAL) ==========

    async def embed_setup(self, ctx):
        setup_view = View(timeout=600)
        embed_data = {
            "message": None,
            "title": None,
            "description": None,
            "color": None,
            "footer_text": None,
            "footer_icon": None,
            "author_name": None,
            "author_icon": None,
            "thumbnail": None,
            "image": None,
        }

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        async def update_preview():
            content = safe_format(embed_data["message"]) or "Message Content."
            embed = discord.Embed(
    title=safe_format(embed_data["title"]) or "",
    description=safe_format(embed_data["description"]) or "```Customize your welcome embed, take help of variables.```",
    color=discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0xFCD005)
            )

            
            if embed_data["footer_text"]:
                embed.set_footer(text=safe_format(embed_data["footer_text"]), icon_url=safe_format(embed_data["footer_icon"]) or None)
            if embed_data["author_name"]:
                embed.set_author(name=safe_format(embed_data["author_name"]), icon_url=safe_format(embed_data["author_icon"]) or None)
            if embed_data["thumbnail"]:
                embed.set_thumbnail(url=safe_format(embed_data["thumbnail"]))
            if embed_data["image"]:
                embed.set_image(url=safe_format(embed_data["image"]))

            await preview_message.edit(content="**Embed Preview:** " + content, embed=embed, view=setup_view)

        preview_message = await ctx.send("Configuring embed welcome message...")

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            selected_option = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected_option == "message":
                    await ctx.send("Enter the welcome message content:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["message"] = msg.content

                elif selected_option == "title":
                    await ctx.send("Enter the embed title:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["title"] = msg.content

                elif selected_option == "description":
                    await ctx.send("Enter the embed description:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["description"] = msg.content

                elif selected_option == "color":
                    await ctx.send("Enter a hex color (e.g., #3498db or 3498db):")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    color_code = msg.content.lstrip("#")
                    if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) in {3, 6}:
                        embed_data["color"] = int(color_code.lstrip("#"), 16)
                    else:
                        await ctx.send("Invalid color code. Please enter a valid hex color.")

                elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                    await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    url_or_text = msg.content
                    if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                        if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                            embed_data[selected_option] = url_or_text
                        else:
                            await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                    else:
                        embed_data[selected_option] = url_or_text

                await update_preview()
                await interaction.followup.send(f"{selected_option.capitalize()} updated.", ephemeral=True)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

        select_menu = Select(
            placeholder="Choose an option to edit the Embed",
            options=[
                discord.SelectOption(label="Message Content", value="message"),
                discord.SelectOption(label="Title", value="title"),
                discord.SelectOption(label="Description", value="description"),
                discord.SelectOption(label="Color", value="color"),
                discord.SelectOption(label="Footer Text", value="footer_text"),
                discord.SelectOption(label="Footer Icon", value="footer_icon"),
                discord.SelectOption(label="Author Name", value="author_name"),
                discord.SelectOption(label="Author Icon", value="author_icon"),
                discord.SelectOption(label="Thumbnail", value="thumbnail"),
                discord.SelectOption(label="Image", value="image")
            ]
        )
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            if not any(embed_data[key] for key in ["title", "description"]):
                await interaction.response.send_message("Please provide at least a title or an description before submitting.", ephemeral=True)
                return

            await self._save_welcome_data(ctx.guild.id, "embed", embed_data["message"] or "", embed_data)
            await interaction.response.send_message(f"{Emojis.TICK} Embed welcome message setup completed!")

            for item in setup_view.children:
                item.disabled = True
            await preview_message.edit(view=setup_view)

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)
        setup_view.add_item(VariableButton(ctx.author))

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()
            await interaction.response.send_message("Embed setup cancelled.", ephemeral=True)

        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        await update_preview()

    # ========== EMBED SETUP (LEAVE) ==========

    async def embed_setup_leave(self, ctx):
        setup_view = View(timeout=600)
        embed_data = {
            "message": None,
            "title": None,
            "description": None,
            "color": None,
            "footer_text": None,
            "footer_icon": None,
            "author_name": None,
            "author_icon": None,
            "thumbnail": None,
            "image": None,
        }

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        async def update_preview():
            content = safe_format(embed_data["message"]) or "Message Content."
            embed = discord.Embed(
    title=safe_format(embed_data["title"]) or "",
    description=safe_format(embed_data["description"]) or "```Customize your leave embed, take help of variables.```",
    color=discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0x2f3136)
            )

            
            if embed_data["footer_text"]:
                embed.set_footer(text=safe_format(embed_data["footer_text"]), icon_url=safe_format(embed_data["footer_icon"]) or None)
            if embed_data["author_name"]:
                embed.set_author(name=safe_format(embed_data["author_name"]), icon_url=safe_format(embed_data["author_icon"]) or None)
            if embed_data["thumbnail"]:
                embed.set_thumbnail(url=safe_format(embed_data["thumbnail"]))
            if embed_data["image"]:
                embed.set_image(url=safe_format(embed_data["image"]))

            await preview_message.edit(content="**Embed Preview:** " + content, embed=embed, view=setup_view)

        preview_message = await ctx.send("Configuring embed leave message...")

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            selected_option = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected_option == "message":
                    await ctx.send("Enter the leave message content:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["message"] = msg.content

                elif selected_option == "title":
                    await ctx.send("Enter the embed title:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["title"] = msg.content

                elif selected_option == "description":
                    await ctx.send("Enter the embed description:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["description"] = msg.content

                elif selected_option == "color":
                    await ctx.send("Enter a hex color (e.g., #3498db or 3498db):")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    color_code = msg.content.lstrip("#")
                    if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) in {3, 6}:
                        embed_data["color"] = int(color_code.lstrip("#"), 16)
                    else:
                        await ctx.send("Invalid color code. Please enter a valid hex color.")

                elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                    await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    url_or_text = msg.content
                    if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                        if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                            embed_data[selected_option] = url_or_text
                        else:
                            await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                    else:
                        embed_data[selected_option] = url_or_text

                await update_preview()
                await interaction.followup.send(f"{selected_option.capitalize()} updated.", ephemeral=True)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

        select_menu = Select(
            placeholder="Choose an option to edit the Embed",
            options=[
                discord.SelectOption(label="Message Content", value="message"),
                discord.SelectOption(label="Title", value="title"),
                discord.SelectOption(label="Description", value="description"),
                discord.SelectOption(label="Color", value="color"),
                discord.SelectOption(label="Footer Text", value="footer_text"),
                discord.SelectOption(label="Footer Icon", value="footer_icon"),
                discord.SelectOption(label="Author Name", value="author_name"),
                discord.SelectOption(label="Author Icon", value="author_icon"),
                discord.SelectOption(label="Thumbnail", value="thumbnail"),
                discord.SelectOption(label="Image", value="image")
            ]
        )
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            if not any(embed_data[key] for key in ["title", "description"]):
                await interaction.response.send_message("Please provide at least a title or an description before submitting.", ephemeral=True)
                return

            await self._save_leave_data(ctx.guild.id, "embed", embed_data["message"] or "", embed_data)
            await interaction.response.send_message(f"{Emojis.TICK} Embed leave message setup completed!")

            for item in setup_view.children:
                item.disabled = True
            await preview_message.edit(view=setup_view)

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)
        setup_view.add_item(VariableButton(ctx.author, for_leave=True))

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()
            await interaction.response.send_message("Embed setup cancelled.", ephemeral=True)

        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        await update_preview()

    # ========== GREET RESET (ORIGINAL) ==========

    @greet.command(name="reset", aliases=["disable"], help="Resets and deletes the current welcome configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_reset(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            cursor = await db.execute("SELECT 1 FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up: 
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0xFCD005)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        embed = discord.Embed(
            title="Are you sure?",
            description="This will remove all welcome configurations & data related to welcome messages for this server!",
            color=0xFCD005
        )

        yes_button = Button(label="Confirm", style=discord.ButtonStyle.danger)
        no_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def yes_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can confirm this action.", ephemeral=True)
                return

            async with aiosqlite.connect("db/welcome.db") as db:
                await db.execute("DELETE FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed.color = discord.Color(0xFCD005)
            embed.title = f"{Emojis.TICK} Success"
            embed.description = "Welcome message configuration has been successfully reset."
            await interaction.message.edit(embed=embed, view=None)

        async def no_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can cancel this action.", ephemeral=True)
                return

            embed.color = discord.Color(0xFCD005)
            embed.title = "Cancelled"
            embed.description = "Greet Reset operation has been cancelled."
            await interaction.message.edit(embed=embed, view=None)

        yes_button.callback = yes_button_callback
        no_button.callback = no_button_callback

        view = View()
        view.add_item(yes_button)
        view.add_item(no_button)

        await ctx.send(embed=embed, view=view)

    # ========== LEAVE RESET ==========

    @leave.command(name="reset", aliases=["disable"], help="Resets and deletes the current leave configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_reset(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            cursor = await db.execute("SELECT 1 FROM leave WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up: 
            error = discord.Embed(description=f"No leave message has been set for {ctx.guild.name}! Please set a leave message first using `{ctx.prefix}leave setup`", color=0xFCD005)
            error.set_author(name="Leave is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        embed = discord.Embed(
            title="Are you sure?",
            description="This will remove all leave configurations & data related to leave messages for this server!",
            color=0xFCD005
        )

        yes_button = Button(label="Confirm", style=discord.ButtonStyle.danger)
        no_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def yes_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can confirm this action.", ephemeral=True)
                return

            async with aiosqlite.connect("db/welcome.db") as db:
                await db.execute("DELETE FROM leave WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed.color = discord.Color(0xFCD005)
            embed.title = f"{Emojis.TICK} Success"
            embed.description = "Leave message configuration has been successfully reset."
            await interaction.message.edit(embed=embed, view=None)

        async def no_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can cancel this action.", ephemeral=True)
                return

            embed.color = discord.Color(0xFCD005)
            embed.title = "Cancelled"
            embed.description = "Leave Reset operation has been cancelled."
            await interaction.message.edit(embed=embed, view=None)

        yes_button.callback = yes_button_callback
        no_button.callback = no_button_callback

        view = View()
        view.add_item(yes_button)
        view.add_item(no_button)

        await ctx.send(embed=embed, view=view)

    # ========== GREET CHANNEL (ORIGINAL) ==========

    @greet.command(name="channel", help="Sets the channel where welcome messages will be sent.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_channel(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, channel_id FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                welcome_message = result[0] if result else None
                welcome_channel = ctx.guild.get_channel(result[1]) if result and result[1] else None

        if not welcome_message:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x000000)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        channels = ctx.guild.text_channels
        chunk_size = 25
        chunks = [channels[i:i + chunk_size] for i in range(0, len(channels), chunk_size)]
        current_page = 0

        def generate_view(page):
            select_menu = Select(
                placeholder="Select a channel for welcome messages",
                options=[
                    discord.SelectOption(label=channel.name, emoji="<:icons_channel:1327829380935843941>", value=str(channel.id))
                    for channel in chunks[page]
                ]
            )

            async def select_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to set the welcome channel.", ephemeral=True)
                    return

                selected_channel_id = int(select_menu.values[0])
                selected_channel = ctx.guild.get_channel(selected_channel_id)

                async with aiosqlite.connect("db/welcome.db") as db:
                    await db.execute("UPDATE welcome SET channel_id = ? WHERE guild_id = ?", (selected_channel_id, ctx.guild.id))
                    await db.commit()

                embed.description = f"Current Welcome Channel: {selected_channel.mention}"
                await interaction.response.edit_message(embed=embed, view=None)
                await ctx.send(f"{Emojis.TICK} Welcome channel has been set to {selected_channel.mention}")

            select_menu.callback = select_callback

            next_button = Button(label="Next List of Channels", style=discord.ButtonStyle.secondary, disabled=page >= len(chunks) - 1)
            previous_button = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=page <= 0)

            async def next_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to navigate these menus.", ephemeral=True)
                    return
                nonlocal current_page
                current_page += 1
                await interaction.response.edit_message(embed=embed, view=generate_view(current_page))

            async def previous_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to navigate these menus.", ephemeral=True)
                    return
                nonlocal current_page
                current_page -= 1
                await interaction.response.edit_message(embed=embed, view=generate_view(current_page))

            next_button.callback = next_callback
            previous_button.callback = previous_callback

            view = View()
            view.add_item(select_menu)
            view.add_item(previous_button)
            view.add_item(next_button)
            return view

        embed = discord.Embed(
            title=f"Welcome Channel for {ctx.guild.name}",
            description=f"Current Welcome Channel: {welcome_channel.mention if welcome_channel else 'None'}",
            color=0xFCD005
        )
        embed.set_footer(text="Use the dropdown menu to select a channel. Navigate pages if needed.")

        await ctx.send(embed=embed, view=generate_view(current_page))

    # ========== LEAVE CHANNEL ==========

    @leave.command(name="channel", help="Sets the channel where leave messages will be sent.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_channel(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT leave_type, channel_id FROM leave WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                leave_message = result[0] if result else None
                leave_channel = ctx.guild.get_channel(result[1]) if result and result[1] else None

        if not leave_message:
            error = discord.Embed(description=f"No leave message has been set for {ctx.guild.name}! Please set a leave message first using `{ctx.prefix}leave setup`", color=0x000000)
            error.set_author(name="Leave is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        channels = ctx.guild.text_channels
        chunk_size = 25
        chunks = [channels[i:i + chunk_size] for i in range(0, len(channels), chunk_size)]
        current_page = 0

        def generate_view(page):
            select_menu = Select(
                placeholder="Select a channel for leave messages",
                options=[
                    discord.SelectOption(label=channel.name, emoji="<:icons_channel:1327829380935843941>", value=str(channel.id))
                    for channel in chunks[page]
                ]
            )

            async def select_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to set the leave channel.", ephemeral=True)
                    return

                selected_channel_id = int(select_menu.values[0])
                selected_channel = ctx.guild.get_channel(selected_channel_id)

                async with aiosqlite.connect("db/welcome.db") as db:
                    await db.execute("UPDATE leave SET channel_id = ? WHERE guild_id = ?", (selected_channel_id, ctx.guild.id))
                    await db.commit()

                embed.description = f"Current Leave Channel: {selected_channel.mention}"
                await interaction.response.edit_message(embed=embed, view=None)
                await ctx.send(f"{Emojis.TICK} Leave channel has been set to {selected_channel.mention}")

            select_menu.callback = select_callback

            next_button = Button(label="Next List of Channels", style=discord.ButtonStyle.secondary, disabled=page >= len(chunks) - 1)
            previous_button = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=page <= 0)

            async def next_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to navigate these menus.", ephemeral=True)
                    return
                nonlocal current_page
                current_page += 1
                await interaction.response.edit_message(embed=embed, view=generate_view(current_page))

            async def previous_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to navigate these menus.", ephemeral=True)
                    return
                nonlocal current_page
                current_page -= 1
                await interaction.response.edit_message(embed=embed, view=generate_view(current_page))

            next_button.callback = next_callback
            previous_button.callback = previous_callback

            view = View()
            view.add_item(select_menu)
            view.add_item(previous_button)
            view.add_item(next_button)
            return view

        embed = discord.Embed(
            title=f"Leave Channel for {ctx.guild.name}",
            description=f"Current Leave Channel: {leave_channel.mention if leave_channel else 'None'}",
            color=0xFCD005
        )
        embed.set_footer(text="Use the dropdown menu to select a channel. Navigate pages if needed.")

        await ctx.send(embed=embed, view=generate_view(current_page))

    # ========== GREET TEST (ORIGINAL) ==========

    @greet.command(name="test", help="Sends a test welcome message to preview the setup.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_test(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, welcome_message, channel_id, embed_data FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0xFCD005)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        welcome_type, welcome_message, channel_id, embed_data = row
        welcome_channel = self.bot.get_channel(channel_id)

        if not welcome_channel:
            error2 = discord.Embed(description=f"Welcome channel not set or invalid. Use `{ctx.prefix}greet channel` to set one.", color=0xFCD005)
            error2.set_author(name="Channel not set", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error2)
            return

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()  
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        if welcome_type == "simple" and welcome_message:
            await welcome_channel.send(safe_format(welcome_message))

        elif welcome_type == "embed" and embed_data:
            try:
                embed_info = json.loads(embed_data) 
                color_value = embed_info.get("color", None)

                
                embed_color = 0x2f3136

                
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                elif isinstance(color_value, int): 
                    embed_color = discord.Color(color_value)

            except (ValueError, SyntaxError, json.JSONDecodeError):
                await ctx.send("Invalid embed data format. Please reconfigure.")
                return

            content = safe_format(embed_info.get("message", "")) or None
            embed = discord.Embed(
                title=safe_format(embed_info.get("title", "")),
                description=safe_format(embed_info.get("description", "")),
                color=embed_color
            )
            embed.timestamp = discord.utils.utcnow()


            if embed_info.get("footer_text"):
                embed.set_footer(
                    text=safe_format(embed_info["footer_text"]),
                    icon_url=safe_format(embed_info.get("footer_icon", ""))
                )
            if embed_info.get("author_name"):
                embed.set_author(
                    name=safe_format(embed_info["author_name"]),
                    icon_url=safe_format(embed_info.get("author_icon", ""))
                )
            if embed_info.get("thumbnail"):
                embed.set_thumbnail(url=safe_format(embed_info["thumbnail"]))
            if embed_info.get("image"):
                embed.set_image(url=safe_format(embed_info["image"]))

            await welcome_channel.send(content=content, embed=embed)

        elif welcome_type == "image":
            avatar_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            avatar_bytes = await _fetch_avatar(avatar_url)
            img_cfg = json.loads(embed_data) if embed_data else {}
            bg_bytes = None
            if img_cfg.get("bg_type") == "custom" and img_cfg.get("custom_bg_url"):
                bg_bytes = await _fetch_avatar(img_cfg["custom_bg_url"])
            # resolve placeholders
            if img_cfg.get("label"):
                img_cfg["label"] = safe_format(img_cfg["label"])
            if img_cfg.get("footer_text"):
                img_cfg["footer_text"] = safe_format(img_cfg["footer_text"])
            msg_content = safe_format(img_cfg.get("message") or "") or None
            buf = await self.bot.loop.run_in_executor(
                None, _make_welcome_card,
                avatar_bytes or b"", ctx.author.name,
                ctx.guild.member_count, "welcome", img_cfg, bg_bytes
            )
            file = discord.File(buf, filename="welcome.png")
            await welcome_channel.send(content=msg_content, file=file)
            await ctx.send(f"{Emojis.TICK} Test welcome image card sent to {welcome_channel.mention}!")

    # ========== LEAVE TEST ==========

    @leave.command(name="test", help="Sends a test leave message to preview the setup.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_test(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT leave_type, leave_message, channel_id, embed_data FROM leave WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No leave message has been set for {ctx.guild.name}! Please set a leave message first using `{ctx.prefix}leave setup`", color=0xFCD005)
            error.set_author(name="Leave is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        leave_type, leave_message, channel_id, embed_data = row
        leave_channel = self.bot.get_channel(channel_id)

        if not leave_channel:
            error2 = discord.Embed(description=f"Leave channel not set or invalid. Use `{ctx.prefix}leave channel` to set one.", color=0xFCD005)
            error2.set_author(name="Channel not set", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error2)
            return

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": ctx.author.joined_at.strftime("%a, %b %d, %Y"),
            "user_createdate": ctx.author.created_at.strftime("%a, %b %d, %Y"),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()  
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        if leave_type == "simple" and leave_message:
            await leave_channel.send(safe_format(leave_message))

        elif leave_type == "embed" and embed_data:
            try:
                embed_info = json.loads(embed_data) 
                color_value = embed_info.get("color", None)

                
                embed_color = 0x2f3136

                
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                elif isinstance(color_value, int): 
                    embed_color = discord.Color(color_value)

            except (ValueError, SyntaxError, json.JSONDecodeError):
                await ctx.send("Invalid embed data format. Please reconfigure.")
                return

            content = safe_format(embed_info.get("message", "")) or None
            embed = discord.Embed(
                title=safe_format(embed_info.get("title", "")),
                description=safe_format(embed_info.get("description", "")),
                color=embed_color
            )
            embed.timestamp = discord.utils.utcnow()


            if embed_info.get("footer_text"):
                embed.set_footer(
                    text=safe_format(embed_info["footer_text"]),
                    icon_url=safe_format(embed_info.get("footer_icon", ""))
                )
            if embed_info.get("author_name"):
                embed.set_author(
                    name=safe_format(embed_info["author_name"]),
                    icon_url=safe_format(embed_info.get("author_icon", ""))
                )
            if embed_info.get("thumbnail"):
                embed.set_thumbnail(url=safe_format(embed_info["thumbnail"]))
            if embed_info.get("image"):
                embed.set_image(url=safe_format(embed_info["image"]))

            await leave_channel.send(content=content, embed=embed)

        elif leave_type == "image":
            avatar_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            avatar_bytes = await _fetch_avatar(avatar_url)
            img_cfg = json.loads(embed_data) if embed_data else {}
            bg_bytes = None
            if img_cfg.get("bg_type") == "custom" and img_cfg.get("custom_bg_url"):
                bg_bytes = await _fetch_avatar(img_cfg["custom_bg_url"])
            if img_cfg.get("label"):
                img_cfg["label"] = safe_format(img_cfg["label"])
            if img_cfg.get("footer_text"):
                img_cfg["footer_text"] = safe_format(img_cfg["footer_text"])
            msg_content = safe_format(img_cfg.get("message") or "") or None
            buf = await self.bot.loop.run_in_executor(
                None, _make_welcome_card,
                avatar_bytes or b"", ctx.author.name,
                ctx.guild.member_count, "leave", img_cfg, bg_bytes
            )
            file = discord.File(buf, filename="leave.png")
            await leave_channel.send(content=msg_content, file=file)
            await ctx.send(f"{Emojis.TICK} Test leave image card sent to {leave_channel.mention}!")

    # ========== GREET CONFIG (ORIGINAL) ==========

    @greet.command(name="config", help="Shows the current welcome configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_config(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            _, welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration = row
            response_type = "Simple" if welcome_type == "simple" else ("Embed" if welcome_type == "embed" else "Image Card")

            embed = discord.Embed(
                title=f"Greet Configuration for {ctx.guild.name}",
                color=0x000000
            )

            embed.add_field(name="Response Type", value=response_type, inline=False)

            if welcome_type == "simple":
                details = f"Message Content: {welcome_message or 'None'}"
                embed.add_field(name="Details", value=details[:1024], inline=False)
            else:
                embed_details = json.loads(embed_data) if embed_data else {}
                formatted_embed_data = "\n".join(
                    f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_details.items()
                ) or "None"

                for i, chunk in enumerate([formatted_embed_data[i:i+1024] for i in range(0, len(formatted_embed_data), 1024)]):
                    embed.add_field(name=f"Embed Data Part {i+1}", value=chunk, inline=False)

            greet_channel = self.bot.get_channel(channel_id)
            channel_display = greet_channel.mention if greet_channel else "None"
            auto_delete_duration = f"{auto_delete_duration} seconds" if auto_delete_duration else "None"

            embed.add_field(name="Greet Channel", value=channel_display, inline=False)
            embed.add_field(name="Auto Delete Duration", value=auto_delete_duration, inline=False)
            await ctx.send(embed=embed)
        else:
            error = discord.Embed(
                description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`",
                color=0x000000
            )
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)

    # ========== LEAVE CONFIG ==========

    @leave.command(name="config", help="Shows the current leave configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_config(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM leave WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            _, leave_type, leave_message, channel_id, embed_data, auto_delete_duration = row
            response_type = "Simple" if leave_type == "simple" else ("Embed" if leave_type == "embed" else "Image Card")

            embed = discord.Embed(
                title=f"Leave Configuration for {ctx.guild.name}",
                color=0x000000
            )

            embed.add_field(name="Response Type", value=response_type, inline=False)

            if leave_type == "simple":
                details = f"Message Content: {leave_message or 'None'}"
                embed.add_field(name="Details", value=details[:1024], inline=False)
            else:
                embed_details = json.loads(embed_data) if embed_data else {}
                formatted_embed_data = "\n".join(
                    f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_details.items()
                ) or "None"

                for i, chunk in enumerate([formatted_embed_data[i:i+1024] for i in range(0, len(formatted_embed_data), 1024)]):
                    embed.add_field(name=f"Embed Data Part {i+1}", value=chunk, inline=False)

            leave_channel = self.bot.get_channel(channel_id)
            channel_display = leave_channel.mention if leave_channel else "None"
            auto_delete_duration = f"{auto_delete_duration} seconds" if auto_delete_duration else "None"

            embed.add_field(name="Leave Channel", value=channel_display, inline=False)
            embed.add_field(name="Auto Delete Duration", value=auto_delete_duration, inline=False)
            await ctx.send(embed=embed)
        else:
            error = discord.Embed(
                description=f"No leave message has been set for {ctx.guild.name}! Please set a leave message first using `{ctx.prefix}leave setup`",
                color=0x000000
            )
            error.set_author(name="Leave is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)

    # ========== GREET AUTODELETE (ORIGINAL) ==========

    @greet.command(name="autodelete", aliases=["autodel"], help="Sets the auto-delete duration for the welcome message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_autodelete(self, ctx, time: str):
        
        if time.endswith("s"):
            seconds = int(time[:-1])
            if 3 <= seconds <= 300:
                auto_delete_duration = seconds
            else:
                await ctx.send("Auto delete time should be between 3 seconds and 300 seconds.")
                return
        elif time.endswith("m"):
            minutes = int(time[:-1])
            if 1 <= minutes <= 5:
                auto_delete_duration = minutes * 60  
            else:
                await ctx.send("Auto delete time should be between 1 minute and 5 minutes.")
                return
        else:
            await ctx.send("Invalid time format. Please use 's' for seconds and 'm' for minutes.")
            return

        
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
            UPDATE welcome
            SET auto_delete_duration = ?
            WHERE guild_id = ?
            """, (auto_delete_duration, ctx.guild.id))
            await db.commit()

        await ctx.send(f"{Emojis.TICK} Auto delete duration has been set to **{auto_delete_duration}** seconds.")

    # ========== LEAVE AUTODELETE ==========

    @leave.command(name="autodelete", aliases=["autodel"], help="Sets the auto-delete duration for the leave message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_autodelete(self, ctx, time: str):
        
        if time.endswith("s"):
            seconds = int(time[:-1])
            if 3 <= seconds <= 300:
                auto_delete_duration = seconds
            else:
                await ctx.send("Auto delete time should be between 3 seconds and 300 seconds.")
                return
        elif time.endswith("m"):
            minutes = int(time[:-1])
            if 1 <= minutes <= 5:
                auto_delete_duration = minutes * 60  
            else:
                await ctx.send("Auto delete time should be between 1 minute and 5 minutes.")
                return
        else:
            await ctx.send("Invalid time format. Please use 's' for seconds and 'm' for minutes.")
            return

        
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
            UPDATE leave
            SET auto_delete_duration = ?
            WHERE guild_id = ?
            """, (auto_delete_duration, ctx.guild.id))
            await db.commit()

        await ctx.send(f"{Emojis.TICK} Auto delete duration has been set to **{auto_delete_duration}** seconds.")

    # ========== GREET EDIT (ORIGINAL) ==========

    @greet.command(name="edit", help="Edits the current welcome message settings for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_edit(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, welcome_message, embed_data FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x000000)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        welcome_type, welcome_message, embed_data = row

        cancel_flag = False  

        if welcome_type == "image":
            img_cfg = json.loads(embed_data) if embed_data else {}

            def config_summary():
                lines = [
                    f"**Message:** {img_cfg.get('message') or '`None` (above image)'}",
                    f"**Label:** {img_cfg.get('label') or '`Welcome` (default)'}",
                    f"**Background:** {img_cfg.get('bg_type', 'avatar')} {'`' + img_cfg['custom_bg_url'] + '`' if img_cfg.get('custom_bg_url') else ''}",
                    f"**Accent Color:** {'`#' + img_cfg['accent_color'] + '`' if img_cfg.get('accent_color') else '`White (default)`'}",
                    f"**Footer Text:** {img_cfg.get('footer_text') or '`None`'}",
                ]
                return "\n".join(lines)

            edit_view = View(timeout=600)
            embed = discord.Embed(
                title="Edit Welcome Image Card",
                description=f"**Response Type:** Image Card\n\n{config_summary()}",
                color=0xFCD005
            )
            msg = await ctx.send(embed=embed, view=edit_view)

            select_menu = Select(
                placeholder="Choose a field to edit",
                options=[
                    discord.SelectOption(label="Message",         value="message"),
                    discord.SelectOption(label="Label Text",      value="label"),
                    discord.SelectOption(label="Background Type", value="bg_type"),
                    discord.SelectOption(label="Custom BG URL",   value="custom_bg_url"),
                    discord.SelectOption(label="Accent Color",    value="accent_color"),
                    discord.SelectOption(label="Footer Text",     value="footer_text"),
                ]
            )

            async def handle_edit(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                selected = select_menu.values[0]
                await interaction.response.defer()
                try:
                    prompts = {
                        "message":       "Enter message text above the image (supports `{user}`, `{server_name}` etc, or `none` to remove):",
                        "label":         "Enter new label text (supports `{server_name}`, `{user_name}`):",
                        "bg_type":       "Enter background type: `avatar` or `custom`:",
                        "custom_bg_url": "Enter image URL for custom background:",
                        "accent_color":  "Enter hex color (e.g. `FF6400`):",
                        "footer_text":   "Enter footer text (or `none` to remove):",
                    }
                    await ctx.send(prompts[selected])
                    reply = await self.bot.wait_for("message", timeout=300, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    val = reply.content.strip()
                    await reply.delete()

                    if selected == "bg_type" and val.lower() not in ("avatar", "custom"):
                        return await ctx.send("Invalid. Use `avatar` or `custom`.")
                    if selected == "custom_bg_url" and not val.startswith("http"):
                        return await ctx.send("Invalid URL.")
                    if selected == "accent_color":
                        val = val.lstrip("#")
                        if not (len(val) == 6 and all(c in "0123456789abcdefABCDEF" for c in val)):
                            return await ctx.send("Invalid hex color.")
                        val = val.upper()
                    if selected in ("footer_text", "message") and val.lower() == "none":
                        val = None

                    img_cfg[selected] = val
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute("UPDATE welcome SET embed_data = ? WHERE guild_id = ?", (json.dumps(img_cfg), ctx.guild.id))
                        await db.commit()

                    embed.description = f"**Response Type:** Image Card\n\n{config_summary()}"
                    await msg.edit(embed=embed)
                    await ctx.send(f"{Emojis.TICK} `{selected}` updated.")
                except asyncio.TimeoutError:
                    await ctx.send("Timed out.")

            select_menu.callback = handle_edit
            edit_view.add_item(select_menu)
            await msg.edit(embed=embed, view=edit_view)
            return

        if welcome_type == "simple":
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Simple\n**Message Content:** {welcome_message or 'None'}",
                color=0xFCD005
            )
            edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def edit_button_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit the welcome message.", ephemeral=True)
                    return

                await interaction.response.send_message("Please provide the new welcome message:", ephemeral=True)
                try:
                    new_message = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=600
                    )
                    if cancel_flag:  
                        await ctx.send("Setup was canceled. No changes were made.")
                        return
                    await new_message.delete()
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute("UPDATE welcome SET welcome_message = ? WHERE guild_id = ?", (new_message.content, ctx.guild.id))
                        await db.commit()

                    embed.description = f"**Response Type:** Simple\n**Message Content:** {new_message.content}"
                    edit_button.disabled = True
                    cancel_button.disabled = True
                    await interaction.message.edit(embed=embed, view=view)
                    await ctx.send("Welcome message has been successfully updated.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")

            edit_button.callback = edit_button_callback
            view = View()
            view.add_item(edit_button)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)

        elif welcome_type == "embed":
            embed_data_json = json.loads(embed_data) if embed_data else {}
            formatted_embed_data = "\n".join(
                f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_data_json.items()
            ) or "None"
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Embed\n**Embed Data:**\n```{formatted_embed_data}```",
                color=0x000000
            )

            select_menu = Select(
                placeholder="Select an embed field to edit",
                options=[
                    discord.SelectOption(label=field.replace('_', ' ').title(), value=field)
                    for field in embed_data_json.keys()
                ]
            )

            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def select_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit this embed.", ephemeral=True)
                    return

                selected_option = select_menu.values[0]
                await interaction.response.defer()

                while not cancel_flag:  
                    try:
                        if selected_option == "message":
                            await ctx.send("Enter the welcome message content:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["message"] = msg.content

                        elif selected_option == "title":
                            await ctx.send("Enter the embed title:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["title"] = msg.content

                        elif selected_option == "description":
                            await ctx.send("Enter the embed description:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["description"] = msg.content

                        elif selected_option == "color":
                            await ctx.send("Enter a hex color (e.g., #3498db or 3498db):")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            color_code = msg.content.lstrip("#")
                            if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) in {3, 6}:
                                embed_data_json["color"] = int(color_code.lstrip("#"), 16)
                            else:
                                await ctx.send("Invalid color code. Please enter a valid hex color.")
                                continue  

                        elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                            await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            url_or_text = msg.content
                            if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                                if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                                    embed_data_json[selected_option] = url_or_text
                                else:
                                    await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                                    continue  
                            else:
                                embed_data_json[selected_option] = url_or_text

                        async with aiosqlite.connect("db/welcome.db") as db:
                            await db.execute("UPDATE welcome SET embed_data = ? WHERE guild_id = ?", (json.dumps(embed_data_json), ctx.guild.id))
                            await db.commit()

                        embed.description = f"**Response Type:** Embed\n**Embed Data:**\n```{json.dumps(embed_data_json, indent=4)}```"
                        await interaction.message.edit(embed=embed, view=None)
                        await ctx.send("Embed data has been successfully updated.")
                        break 
                    except asyncio.TimeoutError:
                        await ctx.send("You took too long to respond.")
                        break
                    except Exception as e:
                        await ctx.send(f"An error occurred: {e}")
                        break

            select_menu.callback = select_callback
            view = View()
            view.add_item(select_menu)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)

    # ========== LEAVE EDIT ==========

    @leave.command(name="edit", help="Edits the current leave message settings for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def leave_edit(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT leave_type, leave_message, embed_data FROM leave WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No leave message has been set for {ctx.guild.name}! Please set a leave message first using `{ctx.prefix}leave setup`", color=0x000000)
            error.set_author(name="Leave is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        leave_type, leave_message, embed_data = row

        cancel_flag = False  

        if leave_type == "image":
            img_cfg = json.loads(embed_data) if embed_data else {}

            def config_summary():
                lines = [
                    f"**Message:** {img_cfg.get('message') or '`None` (above image)'}",
                    f"**Label:** {img_cfg.get('label') or '`Goodbye` (default)'}",
                    f"**Background:** {img_cfg.get('bg_type', 'avatar')} {'`' + img_cfg['custom_bg_url'] + '`' if img_cfg.get('custom_bg_url') else ''}",
                    f"**Accent Color:** {'`#' + img_cfg['accent_color'] + '`' if img_cfg.get('accent_color') else '`White (default)`'}",
                    f"**Footer Text:** {img_cfg.get('footer_text') or '`None`'}",
                ]
                return "\n".join(lines)

            edit_view = View(timeout=600)
            embed = discord.Embed(
                title="Edit Leave Image Card",
                description=f"**Response Type:** Image Card\n\n{config_summary()}",
                color=0xFCD005
            )
            msg = await ctx.send(embed=embed, view=edit_view)

            select_menu = Select(
                placeholder="Choose a field to edit",
                options=[
                    discord.SelectOption(label="Message",         value="message"),
                    discord.SelectOption(label="Label Text",      value="label"),
                    discord.SelectOption(label="Background Type", value="bg_type"),
                    discord.SelectOption(label="Custom BG URL",   value="custom_bg_url"),
                    discord.SelectOption(label="Accent Color",    value="accent_color"),
                    discord.SelectOption(label="Footer Text",     value="footer_text"),
                ]
            )

            async def handle_edit(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                selected = select_menu.values[0]
                await interaction.response.defer()
                try:
                    prompts = {
                        "message":       "Enter message text above the image (supports `{user}`, `{server_name}` etc, or `none` to remove):",
                        "label":         "Enter new label text (supports `{server_name}`, `{user_name}`):",
                        "bg_type":       "Enter background type: `avatar` or `custom`:",
                        "custom_bg_url": "Enter image URL for custom background:",
                        "accent_color":  "Enter hex color (e.g. `FF6400`):",
                        "footer_text":   "Enter footer text (or `none` to remove):",
                    }
                    await ctx.send(prompts[selected])
                    reply = await self.bot.wait_for("message", timeout=300, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    val = reply.content.strip()
                    await reply.delete()

                    if selected == "bg_type" and val.lower() not in ("avatar", "custom"):
                        return await ctx.send("Invalid. Use `avatar` or `custom`.")
                    if selected == "custom_bg_url" and not val.startswith("http"):
                        return await ctx.send("Invalid URL.")
                    if selected == "accent_color":
                        val = val.lstrip("#")
                        if not (len(val) == 6 and all(c in "0123456789abcdefABCDEF" for c in val)):
                            return await ctx.send("Invalid hex color.")
                        val = val.upper()
                    if selected in ("footer_text", "message") and val.lower() == "none":
                        val = None

                    img_cfg[selected] = val
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute("UPDATE leave SET embed_data = ? WHERE guild_id = ?", (json.dumps(img_cfg), ctx.guild.id))
                        await db.commit()

                    embed.description = f"**Response Type:** Image Card\n\n{config_summary()}"
                    await msg.edit(embed=embed)
                    await ctx.send(f"{Emojis.TICK} `{selected}` updated.")
                except asyncio.TimeoutError:
                    await ctx.send("Timed out.")

            select_menu.callback = handle_edit
            edit_view.add_item(select_menu)
            await msg.edit(embed=embed, view=edit_view)
            return

        if leave_type == "simple":
            embed = discord.Embed(
                title="Edit Leave Message",
                description=f"**Response Type:** Simple\n**Message Content:** {leave_message or 'None'}",
                color=0xFCD005
            )
            edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def edit_button_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit the leave message.", ephemeral=True)
                    return

                await interaction.response.send_message("Please provide the new leave message:", ephemeral=True)
                try:
                    new_message = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=600
                    )
                    if cancel_flag:  
                        await ctx.send("Setup was canceled. No changes were made.")
                        return
                    await new_message.delete()
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute("UPDATE leave SET leave_message = ? WHERE guild_id = ?", (new_message.content, ctx.guild.id))
                        await db.commit()

                    embed.description = f"**Response Type:** Simple\n**Message Content:** {new_message.content}"
                    edit_button.disabled = True
                    cancel_button.disabled = True
                    await interaction.message.edit(embed=embed, view=view)
                    await ctx.send("Leave message has been successfully updated.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")

            edit_button.callback = edit_button_callback
            view = View()
            view.add_item(edit_button)
            view.add_item(VariableButton(ctx.author, for_leave=True))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)

        elif leave_type == "embed":
            embed_data_json = json.loads(embed_data) if embed_data else {}
            formatted_embed_data = "\n".join(
                f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_data_json.items()
            ) or "None"
            embed = discord.Embed(
                title="Edit Leave Message",
                description=f"**Response Type:** Embed\n**Embed Data:**\n```{formatted_embed_data}```",
                color=0x000000
            )

            select_menu = Select(
                placeholder="Select an embed field to edit",
                options=[
                    discord.SelectOption(label=field.replace('_', ' ').title(), value=field)
                    for field in embed_data_json.keys()
                ]
            )

            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def select_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit this embed.", ephemeral=True)
                    return

                selected_option = select_menu.values[0]
                await interaction.response.defer()

                while not cancel_flag:  
                    try:
                        if selected_option == "message":
                            await ctx.send("Enter the leave message content:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["message"] = msg.content

                        elif selected_option == "title":
                            await ctx.send("Enter the embed title:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["title"] = msg.content

                        elif selected_option == "description":
                            await ctx.send("Enter the embed description:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["description"] = msg.content

                        elif selected_option == "color":
                            await ctx.send("Enter a hex color (e.g., #3498db or 3498db):")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            color_code = msg.content.lstrip("#")
                            if all(c in "0123456789abcdefABCDEF" for c in color_code) and len(color_code) in {3, 6}:
                                embed_data_json["color"] = int(color_code.lstrip("#"), 16)
                            else:
                                await ctx.send("Invalid color code. Please enter a valid hex color.")
                                continue  

                        elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                            await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            url_or_text = msg.content
                            if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                                if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                                    embed_data_json[selected_option] = url_or_text
                                else:
                                    await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                                    continue  
                            else:
                                embed_data_json[selected_option] = url_or_text

                        async with aiosqlite.connect("db/welcome.db") as db:
                            await db.execute("UPDATE leave SET embed_data = ? WHERE guild_id = ?", (json.dumps(embed_data_json), ctx.guild.id))
                            await db.commit()

                        embed.description = f"**Response Type:** Embed\n**Embed Data:**\n```{json.dumps(embed_data_json, indent=4)}```"
                        await interaction.message.edit(embed=embed, view=None)
                        await ctx.send("Embed data has been successfully updated.")
                        break 
                    except asyncio.TimeoutError:
                        await ctx.send("You took too long to respond.")
                        break
                    except Exception as e:
                        await ctx.send(f"An error occurred: {e}")
                        break

            select_menu.callback = select_callback
            view = View()
            view.add_item(select_menu)
            view.add_item(VariableButton(ctx.author, for_leave=True))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)


