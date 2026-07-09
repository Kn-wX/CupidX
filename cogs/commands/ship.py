import discord
import random
import sqlite3
import aiohttp
from io import BytesIO
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

DB = "ship.db"

class Ship(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect(DB)
        self.cursor = self.db.cursor()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS ships(
        user1 INTEGER,
        user2 INTEGER,
        percentage INTEGER
        )
        """)
        self.db.commit()

    # ---------------- SHIP COMMAND ----------------

    @commands.hybrid_command(name="ship")
    async def ship(self, ctx, *, arg=None):

        prefix = ctx.clean_prefix

        if arg is None:
            embed = discord.Embed(title="💘 Ship Commands", color=0xff4d6d)
            embed.add_field(name="Commands", value=(
                f"`{ctx.prefix}ship @user` — Love percentage\n"
                f"`{ctx.prefix}ship top` — Server leaderboard\n"
                f"`{ctx.prefix}ship breakup @user` — Break your ship"
            ), inline=False)
            embed.set_footer(text="© CupidX HQ")
            return await ctx.send(embed=embed)

        # ---------------- LEADERBOARD ----------------

        if arg.lower() == "top":
            self.cursor.execute("SELECT * FROM ships ORDER BY percentage DESC LIMIT 10")
            data = self.cursor.fetchall()

            if not data:
                return await ctx.send("No ships yet 💔")

            text = ""
            for i, row in enumerate(data, start=1):
                user1 = ctx.guild.get_member(row[0])
                user2 = ctx.guild.get_member(row[1])
                if user1 and user2:
                    text += f"{i}. {user1.name} ❤️ {user2.name} — **{row[2]}%**\n"

            embed = discord.Embed(title="🏆 Top Ships", description=text, color=0xff4d6d)
            return await ctx.send(embed=embed)

        # ---------------- BREAKUP (Ab isme bhi Image aayegi) ----------------

        if arg.lower().startswith("breakup"):
            try:
                user = await commands.MemberConverter().convert(ctx, arg.split()[1])
            except:
                return await ctx.send(f"❌ Mention a valid user.\nUse `{ctx.prefix}shiphelp`")

            pair = sorted([ctx.author.id, user.id])
            self.cursor.execute("DELETE FROM ships WHERE user1=? AND user2=?", (pair[0], pair[1]))
            self.db.commit()

            # Breakup ke liye 💔 icon generate karega
            image = await self.generate_ship_image(ctx.author, user, 0)
            file = discord.File(image, filename="breakup.png")

            embed = discord.Embed(
                description=f"💔 {ctx.author.mention} broke up with {user.mention}",
                color=0xff0000
            )
            embed.set_image(url="attachment://breakup.png")
            return await ctx.send(embed=embed, file=file)

        # ---------------- SHIP USER ----------------

        try:
            user = await commands.MemberConverter().convert(ctx, arg)
        except:
            return await ctx.send(f"❌ Invalid user.\nUse `{ctx.prefix}shiphelp`")

        user1 = ctx.author
        user2 = user
        pair = sorted([user1.id, user2.id])

        self.cursor.execute("SELECT percentage FROM ships WHERE user1=? AND user2=?", (pair[0], pair[1]))
        data = self.cursor.fetchone()

        if data:
            rate = data[0]
        else:
            seed = int(f"{pair[0]}{pair[1]}")
            random.seed(seed)
            rate = random.randint(1, 100)
            self.cursor.execute("INSERT INTO ships VALUES (?,?,?)", (pair[0], pair[1], rate))
            self.db.commit()

        # ---------------- COMMENT ----------------
        
        name1 = user1.display_name
        name2 = user2.display_name
        shipname = name1[:len(name1)//2] + name2[len(name2)//2:]

        if rate >= 90:
            comment = "💍 Soulmates!"
            icon = "💖"
        elif rate >= 75:
            comment = "💞 Perfect Couple!"
            icon = "❤️"
        elif rate >= 50:
            comment = "💕 Great Match!"
            icon = "❤️"
        elif rate >= 20:
            comment = "😬 Risky!"
            icon = "💔"
        else:
            comment = "💀 Disaster!"
            icon = "💀"

        progress = self.progress_bar(rate)

        # ---------------- IMAGE CARD (Ab Icon dynamically jayega) ----------------

        image = await self.generate_ship_image(user1, user2, rate)
        file = discord.File(image, filename="ship.png")

        embed = discord.Embed(
            title="💘 CupidX Love Calculator",
            description=(
                f"{user1.mention} ❤️ {user2.mention}\n\n"
                f"💞 **Ship Name**\n> `{shipname}`\n\n"
                f"## 💖 {rate}%\n"
                f"{progress}\n\n"
                f"**{comment}**"
            ),
            color=0xff4d6d
        )
        embed.set_image(url="attachment://ship.png")
        embed.set_footer(text=f"For more info type {ctx.prefix}shiphelp")

        await ctx.send(embed=embed, file=file)

    # ---------------- PROGRESS BAR ----------------

    def progress_bar(self, rate):
        filled = int(rate / 10)
        empty = 10 - filled
        return "💖"*filled + "🤍"*empty

    # ---------------- IMAGE GENERATOR (CLEANED UP) ----------------

    async def generate_ship_image(self, user1, user2, rate_val: int):

        self._current_rate = rate_val

        async with aiohttp.ClientSession() as session:
            async with session.get(str(user1.display_avatar.url)) as r1:
                p1_data = await r1.read()
            async with session.get(str(user2.display_avatar.url)) as r2:
                p2_data = await r2.read()

        width, height = 900, 300
        base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        
        # 1. Vibrant Gradient Background
        for i in range(width):
            r = int(255 - (i * (255 - 120) / width))
            g = int(120 - (i * (120 - 100) / width))
            b = int(50 + (i * (200 - 50) / width))
            draw.line([(i, 0), (i, height)], fill=(r, g, b))

        # 2. Glassmorphism Overlay
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        d_overlay = ImageDraw.Draw(overlay)
        d_overlay.rounded_rectangle([30, 30, 870, 270], radius=50, fill=(255, 255, 255, 60))
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        def make_circular(im_data):
            img = Image.open(BytesIO(im_data)).convert("RGBA").resize((180, 180))
            mask = Image.new("L", (180, 180), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)
            img.putalpha(mask)
            return img

        p1 = make_circular(p1_data)
        p2 = make_circular(p2_data)

        # White Borders for PFPs
        draw.ellipse((65, 55, 255, 245), outline="white", width=8)
        draw.ellipse((645, 55, 835, 245), outline="white", width=8)

        base.paste(p1, (70, 60), p1)
        base.paste(p2, (650, 60), p2)

        # 3. DRAW PERCENTAGE NUMBER IN THE MIDDLE — big, bold, always visible
        percent_text = f"{self._current_rate}%"
        font_large = None
        for font_path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "arial.ttf",
            "DejaVuSans-Bold.ttf",
        ]:
            try:
                font_large = ImageFont.truetype(font_path, 100)
                break
            except Exception:
                continue

        # Manual centering — works on ALL Pillow versions
        cx, cy = 450, 150
        if font_large is None:
            try:
                font_large = ImageFont.load_default(size=80)
            except Exception:
                font_large = ImageFont.load_default()

        try:
            bbox = draw.textbbox((0, 0), percent_text, font=font_large)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = 120, 60
        tx = cx - tw // 2
        ty = cy - th // 2

        # Dark shadow so number visible on any gradient
        for ox, oy in [(-4,-4),(4,-4),(-4,4),(4,4),(0,-5),(0,5),(-5,0),(5,0)]:
            draw.text((tx+ox, ty+oy), percent_text, fill=(0, 0, 0, 180), font=font_large)
        # Main white text
        draw.text((tx, ty), percent_text, fill="white", font=font_large)

        buffer = BytesIO()
        base.save(buffer, "PNG")
        buffer.seek(0)
        return buffer

    # ---------------- HELP ----------------



async def setup(bot):
    await bot.add_cog(Ship(bot))
