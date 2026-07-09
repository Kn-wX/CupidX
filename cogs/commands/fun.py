import discord
import requests
import aiohttp
import datetime
import random
import os
from discord.ext import commands
from random import randint
from utils.Tools import *
from core import Cog, cupidx, Context
from utils.config import *
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageOps
import io

def RandomColor():
    randcolor = discord.Color(random.randint(0x000000, 0xFFFFFF))
    return randcolor

RAPIDAPI_HOST = "truth-dare.p.rapidapi.com"
RAPIDAPI_KEY = "1cd7c71534msh2544b357ec07ad8p18fa0bjsn1358eef1f8e9"

class FunView(discord.ui.View):
    def __init__(self, embeds, ctx):
        super().__init__(timeout=60.0)
        self.embeds = embeds
        self.ctx = ctx
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0  # First
        self.children[1].disabled = self.current_page == 0  # Prev
        self.children[2].label = f"{self.current_page + 1}/{len(self.embeds)}"  # Counter
        self.children[3].disabled = self.current_page == len(self.embeds) - 1  # Next
        self.children[4].disabled = self.current_page == len(self.embeds) - 1  # Last

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != 0:
            self.current_page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="1/3", style=discord.ButtonStyle.primary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # Counter button - no action

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != len(self.embeds) - 1:
            self.current_page = len(self.embeds) - 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use these buttons!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass

class Fun(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.giphy_token = 'y3KcqQTdiS0RYcpNJrWn8hFGglKqX4is'
        self.google_api_key = 'AIzaSyA022fwm_TOQcYTg1N_ohqqIj_RUFUM9BY'
        self.search_engine_id = '2166875ec165a6c21'

    async def download_avatar(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")

    def circle_avatar(self, avatar):
        mask = Image.new("L", avatar.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + avatar.size, fill=255)
        avatar = ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5))
        avatar.putalpha(mask)
        return avatar
        
    async def fetch_image(self, ctx, endpoint):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://nekos.life/api/v2/img/{endpoint}") as response:
                if response.status == 200:
                    data = await response.json()
                    return data["url"]
            return None

    async def fetch_action_image(self, action):
        url = f"https://api.waifu.pics/sfw/{action}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json().get('url')
        except requests.exceptions.RequestException:
            return None

    # ═══════════════════════════════════════════════════════════════
    # 🐕 MYDOG COMMAND - ZENO STYLE FITTING
    # ═══════════════════════════════════════════════════════════════

    @commands.command()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mydog(self, ctx, user: discord.Member = None):

        user = user or ctx.author

        processing = await ctx.reply(
            "<a:CupidXloading:1474386958741536891> **Generating MyDog...**\n`<a:CupidXloading:1474386958741536891> Processing avatars & scaling`"
        )

        base_image_path = "data/pictures/mydog.jpg"

        if not os.path.exists(base_image_path):
            return await processing.edit(
                content="<:CupidXCross:1473996646873436336> **Template missing!** `data/pictures/mydog.jpg`"
            )

        try:
            # Load template
            background = Image.open(base_image_path).convert("RGBA")

            # Download avatars
            author_bytes = await ctx.author.display_avatar.read()
            user_bytes = await user.display_avatar.read()

            author_avatar = Image.open(io.BytesIO(author_bytes)).convert("RGBA")
            user_avatar = Image.open(io.BytesIO(user_bytes)).convert("RGBA")

            # --- ZENO EXACT LOGIC ---
            # Franklin face (Author) - Size 230x230
            author_pfp = self.circle_avatar(author_avatar.resize((230, 230), Image.LANCZOS))
            
            # Dog face (User) - Size 310x310 (Ye bada size green ko cover karta hai)
            user_pfp = self.circle_avatar(user_avatar.resize((310, 310), Image.LANCZOS))

            # Exact Zeno Paste Coordinates
            background.paste(author_pfp, (370, 0), author_pfp)
            background.paste(user_pfp, (0, 220), user_pfp)

            # Funny titles
            titles = [
                f"🐕 {ctx.author.display_name}'s Dangerous Dog!",
                f"🐶 {user.display_name} the Guard Dog!",
                f"🦴 {ctx.author.display_name}'s Loyal Dog!",
                f"🐕 Beware! {user.display_name} is unleashed!",
                f"🐶 {ctx.author.display_name} walking their dog!"
            ]

            title = random.choice(titles)

            with io.BytesIO() as image_binary:

                background.save(image_binary, "PNG")
                image_binary.seek(0)

                file = discord.File(
                    fp=image_binary,
                    filename="mydog.png"
                )

                embed = discord.Embed(
                    title=title,
                    color=RandomColor()
                )

                embed.set_image(
                    url="attachment://mydog.png"
                )

                embed.set_footer(
                    text=f"Requested by {ctx.author.display_name}",
                    icon_url=ctx.author.display_avatar.url
                )

                await processing.delete()

                await ctx.send(
                    embed=embed,
                    file=file
                )

        except Exception as e:
            embed = discord.Embed(
                title="<:CupidXCross:1473996646873436336> MyDog Generation Failed",
                description=f"`{str(e)}`",
                color=0xFF4C4C
            )
            await processing.edit(content="", embed=embed)


    # ═══════════════════════════════════════════════════════════════
    # 🖼️ IMAGE & GIF SEARCH - ELEVATED RESULTS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="image", aliases=["img"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def image(self, ctx, *, search_query: str):
        if not ctx.channel.nsfw:
            embed = discord.Embed(
                title="🔞 **NSFW CHANNEL REQUIRED**",
                description="**`image <query>`** works only in age-restricted channels\n`⚠️ Enable NSFW in channel settings`",
                color=0xFF4757
            )
            return await ctx.reply(embed=embed, ephemeral=True)
            
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.googleapis.com/customsearch/v1?key={self.google_api_key}&cx={self.search_engine_id}&q={search_query}&searchType=image&num=10"
            ) as response:
                data = await response.json()
                if "items" in data and data["items"]:
                    image_url = random.choice(data["items"])["link"]
                    embed = discord.Embed(
                        title=f"🖼️ **Image Search**",
                        description=f"**`{search_query}`** • Random result from Google Images\n`✨ 10+ results scanned`",
                        color=RandomColor()
                    )
                    embed.set_image(url=image_url)
                    embed.set_footer(text=f"🔍 Powered by CupidX • {ctx.author.display_name}")
                    await ctx.reply(embed=embed)
                else:
                    embed = discord.Embed(
                        title="🖼️ **No Images Found**",
                        description=f"**`{search_query}`** returned no results\n`❌ Try different keywords`",
                        color=0xFF6B6B
                    )
                    await ctx.reply(embed=embed)

    @commands.command(name="gif")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def gif(self, ctx, *, search_query: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.giphy.com/v1/gifs/search?api_key={self.giphy_token}&q={search_query}&limit=10"
            ) as response:
                data = await response.json()
                if data.get("data"):
                    gif_data = random.choice(data["data"])
                    embed = discord.Embed(
                        title=f"**Random Gif**",
                        description=f"**`{search_query}`**",
                        color=RandomColor()
                    )
                    embed.set_image(url=gif_data["images"]["original"]["url"])
                    embed.set_footer(text=f"")
                    await ctx.reply(embed=embed)
                else:
                    embed = discord.Embed(
                        title="**No GIFs Found Try Another**",
                        description=f"**`{search_query}`** has no matching GIFs\n`❌ Try broader terms`",
                        color=0xFF6B6B
                    )
                    await ctx.reply(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    # 📊 PERCENTAGE METERS - ELEVATED DESIGN
    # ═══════════════════════════════════════════════════════════════
    percentage_meters = {
        "howgay": {"title": "🌈 **GAY METER**", "trait": "gay", "emoji": "🌈"},
        "lesbian": {"title": "💖 **LESBIAN METER**", "trait": "lesbian", "emoji": "💖"},
        "chutiya": {"title": "😂 **CHUTIYA METER**", "trait": "chutiya", "emoji": "😂"},
        "tharki": {"title": "😏 **THARKI METER**", "trait": "tharki", "emoji": "😏"},
        "horny": {"title": "😳 **HORNY METER**", "trait": "horny", "emoji": "😳"},
        "cute": {"title": "🥰 **CUTE METER**", "trait": "cute", "emoji": "🥰"},
        "intelligence": {"title": "🧠 **IQ METER**", "trait": "intelligent", "emoji": "🧠"}
    }

    async def send_meter(self, ctx, cmd_name: str, person: str):
        data = self.percentage_meters[cmd_name]
        percent = random.randint(1, 100)
        
        embed = discord.Embed(
            title=data["title"],
            description=f"<:CupidXuser:1475151935379341382>**User:** {person}\n\n<:CupidXCommands:1475152376737566722>**Result:** {percent}% {data['trait']}\n<:CupidXtick1:1474369967271968949>**Scientifically accurate**",
            color=RandomColor()
        )
        embed.set_footer(text=f"Checked by {ctx.author.display_name} • Purely for fun!")
        await ctx.reply(embed=embed)

    @commands.command(name="howgay", aliases=['gay'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def howgay(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "howgay", person)

    @commands.command(name="lesbian", aliases=['lesbo'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def lesbian(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "lesbian", person)

    @commands.command(name="chutiya", aliases=['chu'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def chutiya(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "chutiya", person)

    @commands.command(name="tharki")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tharki(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "tharki", person)

    @commands.command(name="horny", aliases=['horniness'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def horny(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "horny", person)

    @commands.command(name="cute", aliases=['cuteness'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def cute(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        await self.send_meter(ctx, "cute", person)

    @commands.command(name="intelligence", aliases=['iq'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def intelligence(self, ctx, *, person=None):
        person = person or ctx.author.display_name
        iq = random.randint(70, 160)
        embed = discord.Embed(
            title="🧠 **IQ TEST RESULT**",
            description=f"**{person}** scored **{iq}** IQ points\n`📊 Professional analysis™`",
            color=RandomColor()
        )
        embed.add_field(name="🧠 Score", value=f"``````", inline=True)
        embed.add_field(name="📈 Percentile", value=f"`Top {100-(iq-70)*2:.0f}%`", inline=True)
        embed.set_footer(text=f"Tested by {ctx.author.display_name} • For entertainment only")
        await ctx.reply(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    # 🤗 ACTION COMMANDS - ELEVATED REACTIONS
    # ═══════════════════════════════════════════════════════════════
    action_reactions = {
        "hug": ("**HUG!**", "💕 Warm embrace delivered"),
        "kiss": ("**KISS!**", "💋 Lips met successfully"),
        "pat": ("**PAT!**", "✋ Gentle headpat"),
        "cuddle": ("**CUDDLE!**", "🛌 Cozy moment"),
        "slap": ("**SLAP!**", "💥 Cheek contact made"),
        "tickle": ("**TICKLED!**", "😂 Laughter guaranteed"),
        "spank": ("**SPANK!**", "🔥 Bottom warmed"),
        "kill": ("**ELIMINATED!**", "💀 Dramatic death")
    }


    async def handle_action(self, ctx, action: str, user=None):

        # NSFW Check
        if action == "spank" and not ctx.channel.nsfw:
            embed = discord.Embed(
                title="🔞 **NSFW REQUIRED**",
                description="**Spank** needs age-restricted channel\n`⚠️ Enable NSFW settings`",
                color=0xFF4757
            )
            return await ctx.reply(embed=embed)

        title, desc = self.action_reactions[action]

        # Fetch Image
        image_url = None
        if action in ["hug", "kiss", "pat", "cuddle", "slap", "tickle"]:
            image_url = await self.fetch_image(ctx, action)

        elif action == "kill":
            image_url = await self.fetch_action_image("kill")

        # Zeno Style User Logic
        if user is None:
            description = (
                f"```{ctx.author.display_name} {action}ed themselves!```"
            )
        else:
            description = (
                f"```{ctx.author.display_name} {action}ed {user.display_name}!```"
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=RandomColor()
        )

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(
            text=f""
        )

        await ctx.reply(embed=embed)

    @commands.command(name="fakeban", aliases=['fban'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fake_ban(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        embed = discord.Embed(
            title="<:CupidXtick1:1474369967271968949> | Successfully banned",
            description=f"**<:CupidXuser:1475151935379341382>Target user:** {user.mention}\n**<:CupidXMail:1475192722578215083>DM Sent:** No reason provided\n**<:CupidXCommands:1475152376737566722>Reason:** None",
            color=0xAAB8C2
        )
        embed.add_field(name="<:CupidXautomod:1474356609122697382>Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="<a:CupidXtimer:1475327919558496370>Time", value=f"`{datetime.datetime.now().strftime('%H:%M:%S')}`", inline=True)
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1088001241809536818.gif")
        await ctx.reply(embed=embed)

    @commands.command(name="hug")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def hug(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "hug", user)

    @commands.command(name="kiss")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def kiss(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "kiss", user)

    @commands.command(name="pat")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pat(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "pat", user)

    @commands.command(name="cuddle")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def cuddle(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "cuddle", user)

    @commands.command(name="slap")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slap(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "slap", user)

    @commands.command(name="tickle")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tickle(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "tickle", user)

    @commands.command(name="spank")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def spank(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "spank", user)

    @commands.command(name="kill")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def kill(self, ctx, user: discord.Member = None):
        await self.handle_action(ctx, "kill", user)

    # ═══════════════════════════════════════════════════════════════
    # 🎮 GAME COMMANDS - ELEVATED EMBEDS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="8ball", aliases=["8b"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def eight_ball(self, ctx, *, question: str = None):
        if not question:
            embed = discord.Embed(
                title="🎱 **MAGIC 8-BALL**",
                description="**❓ ASK A QUESTION**\n`8ball <your question here>`\n`🔮 The spirits await!`",
                color=0x3742FA
            )
            return await ctx.reply(embed=embed)
            
        async with aiohttp.ClientSession() as session:
            async with session.get("https://nekos.life/api/v2/8ball") as response:
                data = await response.json()
                answer = data.get('response', '¯\\_(ツ)_/¯')
                embed = discord.Embed(
                    title="🎱 **MAGIC 8-BALL**",
                    description=f"**Q:** {question}\n**🔮 A:** ||{answer}||\n`✨ Spirits have spoken`",
                    color=RandomColor()
                )
                embed.set_footer(text=f"Predicting future • {ctx.author.display_name}")
                await ctx.reply(embed=embed)

    @commands.command(name="truth", aliases=["t"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def truth(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.truthordarebot.xyz/api/truth") as response:
                if response.status == 200:
                    data = await response.json()
                    question = data.get("question", "No truth available")
                    embed = discord.Embed(
                        title="✅ **TRUTH TIME**",
                        description=f"**{question}**\n`🎲 Be honest!`",
                        color=0x00D2D3
                    )
                    embed.set_footer(text="Truth or Dare Bot • Spill the tea!")
                    await ctx.reply(embed=embed)
                else:
                    await ctx.reply("❌ **Truth fetch failed**\n`Try again later`")

    @commands.command(name="dare", aliases=["d"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def dare(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.truthordarebot.xyz/api/dare") as response:
                if response.status == 200:
                    data = await response.json()
                    challenge = data.get("question", "No dare available")
                    embed = discord.Embed(
                        title="🔥 **DARE ACCEPTED**",
                        description=f"**⚠️ {challenge}**\n`🎲 You MUST complete this!`",
                        color=0xFF9F43
                    )
                    embed.set_footer(text="Truth or Dare Bot • No chickening out!")
                    await ctx.reply(embed=embed)
                else:
                    await ctx.reply("❌ **Dare fetch failed**\n`Try again later`")

    # ═══════════════════════════════════════════════════════════════
    # 🌐 UTILITY COMMANDS - ELEVATED INFO
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="iplookup", aliases=['ip'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def iplookup(self, ctx, *, ip: str = None):
        if not ip:
            try:
                response = requests.get("http://httpbin.org/ip", timeout=5)
                ip = response.json()["origin"]
            except:
                ip = "auto-detect-failed"

        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{ip}?fields=status,continent,country,city,isp,org,lat,lon,proxy") as response:
                data = await response.json()
                
                if data.get('status') == 'fail':
                    embed = discord.Embed(
                        title="🌐 **IP LOOKUP FAILED**",
                        description=f"**`{ip}`** is invalid\n`❌ Check IP format`",
                        color=0xFF6B6B
                    )
                    return await ctx.reply(embed=embed)

                embed = discord.Embed(
                    title=f"🌐 **IP ANALYSIS** • {data.get('query', ip)}",
                    color=RandomColor()
                )
                embed.add_field(
                    name="📍 **Location**",
                    value=f"`{data.get('city', 'N/A')}, {data.get('country', 'N/A')}`",
                    inline=True
                )
                embed.add_field(
                    name="🌍 **Coordinates**", 
                    value=f"`{data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}`",
                    inline=True
                )
                embed.add_field(
                    name="📡 **ISP**",
                    value=f"`{data.get('isp', 'N/A')}`",
                    inline=False
                )
                embed.add_field(
                    name="🔒 **Proxy**",
                    value=f"`{'🟢 YES' if data.get('proxy') else '🔴 NO'}`",
                    inline=True
                )
                embed.set_footer(text=f"IP-API • Requested by {ctx.author.display_name}")
                await ctx.reply(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def weather(self, ctx, *, city: str):
        api_key = "b81e2218c328686836ab6d9d31ce97d0"
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://api.openweathermap.org/data/2.5/weather?q={city}&APPID={api_key}&units=metric") as response:
                if response.status == 200:
                    data = await response.json()
                    main = data['main']
                    weather = data['weather'][0]
                    
                    embed = discord.Embed(
                        title=f"☁️ **WEATHER** • {city.title()}",
                        color=RandomColor()
                    )
                    embed.add_field(
                        name="🌡️ **Temperature**",
                        value=f"**{main['temp']:.1f}°C** (`feels like {main['feels_like']:.1f}°C`)",
                        inline=True
                    )
                    embed.add_field(
                        name="💧 **Humidity**",
                        value=f"**{main['humidity']}%**",
                        inline=True
                    )
                    embed.add_field(
                        name="🌪️ **Condition**",
                        value=f"**{weather['description'].title()}**",
                        inline=False
                    )
                    embed.set_footer(text=f"OpenWeather • {ctx.author.display_name}")
                    await ctx.reply(embed=embed)
                else:
                    embed = discord.Embed(
                        title="☁️ **CITY NOT FOUND**",
                        description=f"**`{city}`** doesn't exist\n`❌ Try correct spelling`",
                        color=0xFF6B6B
                    )
                    await ctx.reply(embed=embed)

    @commands.command(name="translate", aliases=["tl"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def translate_command(self, ctx, *, message=None):
        if not message:
            embed = discord.Embed(
                title="🌐 **TRANSLATE**",
                description="**Provide text or reply to message**\n`translate <your text>`",
                color=0x3742FA
            )
            return await ctx.reply(embed=embed)

        if ctx.message.reference:
            replied = await ctx.fetch_message(ctx.message.reference.message_id)
            message = replied.content if replied else message

        async with aiohttp.ClientSession() as session:
            params = {
                "client": "gtx", "sl": "auto", "tl": "en",
                "dt": "t", "q": message[:5000]
            }
            async with session.get("https://translate.googleapis.com/translate_a/single", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    translated = data[0][0][0]
                    detected = data[2]
                    
                    embed = discord.Embed(
                        title="🌐 **TRANSLATION COMPLETE**",
                        color=RandomColor()
                    )
                    embed.add_field(
                        name="📥 **Original**",
                        value=f"`{message[:1000]}{'...' if len(message) > 1000 else ''}`",
                        inline=False
                    )
                    embed.add_field(
                        name="📤 **English**",
                        value=f"`{translated[:1000]}{'...' if len(translated) > 1000 else ''}`",
                        inline=False
                    )
                    embed.set_footer(text=f"Detected: {detected.upper()} • Google Translate • {ctx.author.display_name}")
                    await ctx.reply(embed=embed)
                else:
                    embed = discord.Embed(
                        title="🌐 **TRANSLATION FAILED**",
                        description="`❌ Service temporarily unavailable`",
                        color=0xFF6B6B
                    )
                    await ctx.reply(embed=embed)

    async def send_paginator(self, ctx, embeds):
        """Simple paginator for fun help"""
        if len(embeds) == 1:
            return await ctx.reply(embed=embeds[0])
        
        # This would need View for full pagination, but keeping simple for now
        await ctx.reply(embed=embeds[0])

async def setup(bot):
    await bot.add_cog(Fun(bot))