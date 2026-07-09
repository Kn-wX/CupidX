import base64
import discord
from discord.ext import commands, tasks
import random
import time
import asyncio
import aiohttp
import aiosqlite
import datetime
from core import Cog
from utils.config import OWNER_IDS

class PremiumFeatures(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/premium.db'
        # Background task loop shuru karein
        self.check_giveaways.start()
        # Database initialize karein
        bot.loop.create_task(self.init_giveaway_db())

    def cog_unload(self):
        # Reload hone par purana loop cancel karein taaki double winner announce na ho
        self.check_giveaways.cancel()

    async def init_giveaway_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways(
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                guild_id INTEGER,
                prize TEXT,
                winner_count INTEGER,
                host_id INTEGER,
                end_time INTEGER,
                rigged_id INTEGER
            )
            """)
            await db.commit()

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        current_time = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            # Sirf expired giveaways ko uthayein
            async with db.execute("SELECT * FROM giveaways WHERE end_time <= ?", (current_time,)) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                message_id, channel_id, guild_id, prize, winner_count, host_id, end_time, rigged_id = row
                
                # Race condition se bachne ke liye pehle hi DB se delete karein
                await db.execute("DELETE FROM giveaways WHERE message_id = ?", (message_id,))
                await db.commit()

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue

                try:
                    msg = await channel.fetch_message(message_id)
                    reaction = discord.utils.get(
                        msg.reactions,
                        emoji=discord.PartialEmoji(
                            name="CupidXgift",
                            id=1484062612386746398,
                            animated=True
                        )
                    )
                    users = [u async for u in reaction.users() if not u.bot] if reaction else []

                    if not users:
                        await channel.send(f"⚠️ No one joined the giveaway for **{prize}**.")
                        continue

                    # Winner Selection Logic (Rigging support ke saath)
                    winners = []
                    rigged_member = channel.guild.get_member(rigged_id) if rigged_id else None

                    if rigged_member and rigged_member in users:
                        winners.append(rigged_member)
                        if winner_count > 1:
                            rem = [u for u in users if u != rigged_member]
                            winners.extend(random.sample(rem, min(len(rem), winner_count - 1)))
                    else:
                        winners = random.sample(users, min(len(users), winner_count))

                    mentions = ", ".join([w.mention for w in winners])
                    host = channel.guild.get_member(host_id)

                    # Winner Announcement
                    announce_embed = discord.Embed(
                        title="🎊 GIVEAWAY ENDED 🎊",
                        description=f"**Prize:** {prize}\n**Winner(s):** {mentions}\n**Hosted by:** {host.mention if host else 'Unknown'}",
                        color=0x00ff77
                    )
                    await channel.send(f"Congratulations {mentions}! You won **{prize}**!", embed=announce_embed)

                    # Original Embed Edit
                    if msg.embeds:
                        embed = msg.embeds[0]
                        embed.description = f"**Giveaway Ended**\n**Winner(s):** {mentions}\n**Hosted by:** {host.mention if host else 'Unknown'}"
                        await msg.edit(content="🎉 **GIVEAWAY FINISHED** 🎉", embed=embed)

                except Exception as e:
                    print(f"Giveaway Loop Error: {e}")

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def is_premium_admin(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id FROM premium_guilds WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                res = await cursor.fetchone()

        if not res:
            await ctx.reply(embed=discord.Embed(description="<:icons_warning:1327829522573430864> This is a **Premium Only** command.", color=0xFCD005))
            return False

        owners = getattr(self.bot, 'owner_ids', [])
        if not ctx.author.guild_permissions.administrator and ctx.author.id not in owners:
            await ctx.reply("❌ Only for admin.")
            return False
        return True

    async def is_user_premium(self, user_id):
        async with aiosqlite.connect('db/np.db') as db:
            async with db.execute("SELECT id FROM np WHERE id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
        return res is not None

    async def is_guild_premium(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id FROM premium_guilds WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                res = await cursor.fetchone()
        return res is not None

    # 1. SAY COMMAND
    @commands.hybrid_command(name="say", description="👤 Impersonate a user")
    async def say(self, ctx, member: discord.Member, *, message: str):
        if ctx.author.id not in OWNER_IDS:
            if not await self.is_premium_admin(ctx):
                return
        await ctx.defer(ephemeral=True)
        webhook = await ctx.channel.create_webhook(name=member.display_name)
        await webhook.send(str(message), username=member.display_name, avatar_url=member.display_avatar.url)
        await webhook.delete()
        await ctx.send("✅ Done!", ephemeral=True)

    # 2. STOCK COMMAND
    @commands.hybrid_command(name="stock", description="📈 Live Crypto prices (Premium Admin Only)")
    async def stock(self, ctx, symbol: str = "btc"):
        if not await self.is_premium_admin(ctx):
            return
        await ctx.defer()
        coin_map = {
            "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
            "doge": "dogecoin", "trx": "tron", "bnb": "binancecoin",
            "matic": "matic-network", "xrp": "ripple", "ada": "cardano"
        }
        input_sym = symbol.lower()
        coin_id = coin_map.get(input_sym, input_sym)
        async with aiohttp.ClientSession() as session:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            async with session.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    if coin_id in data:
                        price = data[coin_id]['usd']
                        display_price = f"{price:,.2f}" if price >= 1 else f"{price:.6f}"
                        embed = discord.Embed(title=f"📊 Market Update: {symbol.upper()}", color=0x00ff77)
                        embed.add_field(name="Current Price", value=f"**${display_price} USD**", inline=False)
                        embed.set_footer(text="Powered by CoinGecko API")
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"❌ **'{symbol.upper()}' not found.**")
                else:
                    await ctx.send("⚠️ API connection issue.")

    # 3. GLSTART COMMAND
    @commands.hybrid_command(name="glstart", description="🎉 Start a giveaway (Premium Only)")
    async def glstart(self, ctx, duration: str, winner_count: int, prize: str, win: discord.Member = None):
        if not await self.is_premium_admin(ctx):
            return

        time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = duration[-1].lower()
        if unit not in time_units or not duration[:-1].isdigit():
            return await ctx.reply("❌ Invalid duration! Use `10m`, `1h`, `1d`.", ephemeral=True)

        seconds = int(duration[:-1]) * time_units[unit]
        await ctx.defer()

        end_time = int(time.time() + seconds)
        timestamp = f"<t:{end_time}:R>"

        embed = discord.Embed(
            title=f"**Prize:** {prize} ",
            description=f"<a:CupidXdot:1473986328126558209> React with <a:CupidXgift:1484062612386746398> to enter!\n\n<:arrow:1460268999081459732> **Ends:** {timestamp}\n<:arrow:1460268999081459732> **Hosted by:** {ctx.author.mention}\n<:arrow:1460268999081459732> **Winners:** {winner_count}",
            color=0x2b2d31
        )
        embed.set_footer(text="Good Luck!")
        msg = await ctx.send(content="**GIVEAWAY STARTED**", embed=embed)
        await msg.add_reaction("<a:CupidXgift:1484062612386746398>")

        rigged_id = win.id if win else None

        # Database Entry for Restart Proof
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO giveaways VALUES(?,?,?,?,?,?,?,?)",
                (msg.id, ctx.channel.id, ctx.guild.id, prize, winner_count, ctx.author.id, end_time, rigged_id)
            )
            await db.commit()
            
    # CUSTOM BOT PROFILE COMMAND
    @commands.hybrid_command(name="customprofile", description="🎨 Customize bot profile (Premium Guilds Only)", aliases= ["custompr", "botprofile", "bp"])
    async def customprofile(self, ctx, action: str = None, *, value: str = None):
        # 🔥 PREMIUM CHECK
        if not await self.is_guild_premium(ctx):
            return await ctx.reply(
                embed=discord.Embed(
                    description="<:icons_warning:1327829522573430864> This server does not have **Premium**.",
                    color=0xFCD005
                )
            )

# 🔥 OWNER CHECK (SERVER OWNER + BOT OWNER)
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in OWNER_IDS:
            return await ctx.reply("❌ Only Server Owner or Bot Owner can use this command.")

        if action is None:
            help_embed = discord.Embed(
                title="<a:BLUE_DOT:1465183409776365797> Bot Profile Customization",
                description="Customize your server's bot profile with various options.",
                color=0xFCD005
            )
            help_embed.add_field(
                name="<a:animate:1465608157127512265> Available Actions:",
                value=(
                    "`bp nickname <name>` - Set bot nickname\n"
                    "`bp avatar <url>` - Set server-specific avatar\n"
                    "`bp banner <url>` - Set bot banner (Server Specific)\n"
                    "`bp bio <text>` - Set server-specific bot bio\n"
                    "`bp reset [action]` - Reset server customizations"
                ),
                inline=False
            )
            help_embed.set_footer(text="CupidX HQ")
            return await ctx.reply(embed=help_embed)

        action = action.lower()

        # --- NICKNAME ---
        if action == "nickname":
            if not value:
                return await ctx.reply("❌ Please provide a nickname.")
            await ctx.defer()
            try:
                await ctx.guild.me.edit(nick=value)
                embed = discord.Embed(
                    title="<:tick:1327829594954530896> Success",
                    description=f"Bot nickname has been updated to **{value}**.",
                    color=0x000000
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.reply(embed=embed)
            except Exception as e:
                await ctx.reply(f"❌ Failed: {str(e)}")

        # --- AVATAR ---
        elif action == "avatar":
            if not value and not ctx.message.attachments:
                return await ctx.reply("❌ Provide an image or URL.")
            await ctx.defer()
            try:
                image_data = None
                if ctx.message.attachments:
                    image_data = await ctx.message.attachments[0].read()
                else:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(value) as resp:
                            if resp.status == 200:
                                image_data = await resp.read()

                if image_data:
                    await ctx.guild.me.edit(avatar=image_data)
                    embed = discord.Embed(
                        title="<:tick:1327829594954530896> Success",
                        description="Server-specific bot avatar has been updated.",
                        color=0x000000
                    )
                    embed.set_thumbnail(url=ctx.guild.me.display_avatar.url)
                    embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                    await ctx.reply(embed=embed)
                else:
                    await ctx.reply("❌ Download failed.")
            except Exception as e:
                await ctx.reply(f"❌ Failed: {str(e)}")

        # --- BANNER ---
        elif action == "banner":
            if not ctx.author.guild_permissions.manage_guild and ctx.author.id not in OWNER_IDS:
                return await ctx.reply("❌ You need **Manage Server** permission.")
            await ctx.defer()
            try:
                image_data = None
                content_type = "image/png"
                if ctx.message.attachments:
                    attachment = ctx.message.attachments[0]
                    content_type = attachment.content_type
                    image_data = await attachment.read()
                elif value:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(value) as resp:
                            content_type = resp.headers.get('Content-Type', 'image/png')
                            image_data = await resp.read()

                if image_data:
                    banner_base64 = base64.b64encode(image_data).decode('utf-8')
                    banner_data = f"data:{content_type};base64,{banner_base64}"
                    await self._patch_member_profile(ctx.guild.id, banner=banner_data)
                    embed = discord.Embed(
                        title="<:tick:1327829594954530896> Success",
                        description="Server-specific bot banner has been updated.",
                        color=0x000000
                    )
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                    embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                    await ctx.reply(embed=embed)
                else:
                    await ctx.reply("❌ No image found.")
            except Exception as e:
                await ctx.reply(f"❌ Banner update failed: {str(e)}")

        # --- BIO ---
        elif action == "bio":
            if not value:
                return await ctx.reply("❌ Please provide a bio text.")
            if len(value) > 190:
                return await ctx.reply("❌ Bio must be **190 characters or less**.")
            await ctx.defer()
            try:
                await self._patch_member_profile(ctx.guild.id, bio=value)
                embed = discord.Embed(
                    title="<:tick:1327829594954530896> Success",
                    description=f"Server-specific bot bio has been updated.",
                    color=0x000000
                )
                embed.add_field(name="Bio", value=f"```{value}```", inline=False)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await ctx.reply(embed=embed)
            except Exception as e:
                await ctx.reply(f"❌ Bio update failed: {str(e)}")

        # --- RESET ---
        elif action == "reset":
            await ctx.defer()
            try:
                if value:
                    subaction = value.lower()
                    if subaction == "avatar":
                        await ctx.guild.me.edit(avatar=None)
                        embed = discord.Embed(title="<:tick:1327829594954530896> Success", description="Server avatar has been reset.", color=0x000000)
                    elif subaction == "nickname":
                        await ctx.guild.me.edit(nick=None)
                        embed = discord.Embed(title="<:tick:1327829594954530896> Success", description="Bot nickname has been reset.", color=0x000000)
                    elif subaction == "banner":
                        await self._patch_member_profile(ctx.guild.id, banner=None)
                        embed = discord.Embed(title="<:tick:1327829594954530896> Success", description="Server banner has been reset.", color=0x000000)
                    elif subaction == "bio":
                        await self._patch_member_profile(ctx.guild.id, bio="")
                        embed = discord.Embed(title="<:tick:1327829594954530896> Success", description="Server bio has been reset.", color=0x000000)
                    elif subaction == "status":
                        await self.bot.change_presence(activity=None, status=discord.Status.online)
                        embed = discord.Embed(title="<:tick:1327829594954530896> Success", description="Global status has been reset.", color=0x000000)
                    else:
                        return await ctx.reply("❌ Unknown reset option.")
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                    embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                    await ctx.reply(embed=embed)
                else:
                    await ctx.guild.me.edit(avatar=None, nick=None)
                    await self._patch_member_profile(ctx.guild.id, banner=None, bio="")
                    await self.bot.change_presence(activity=None, status=discord.Status.online)
                    embed = discord.Embed(
                        title="<:tick:1327829594954530896> Success",
                        description="All server customizations have been reset.",
                        color=0x000000
                    )
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1279464563150032991.png")
                    embed.set_footer(text=f"Requested by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                    await ctx.reply(embed=embed)
            except Exception as e:
                await ctx.reply(f"❌ Reset failed: {str(e)}")

    # --- HELPER FUNCTIONS ---
    async def _patch_member_profile(self, guild_id: int, **fields):
        route = discord.http.Route("PATCH", f"/guilds/{guild_id}/members/@me")
        await self.bot.http.request(route, json=fields)


async def setup(bot):
    await bot.add_cog(PremiumFeatures(bot))