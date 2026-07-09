import discord
from discord.ext import commands
import aiohttp
import random
from discord import app_commands

PEXELS_API_KEY = "js24mfV1bCCvgV6KfnEFvo5UnCHnATFarFnAdDrpDbczl7f0yXpjDF8x"

COMMANDS_INFO = {
    "boy":    {"emoji": "👦", "label": "Boy Pic",     "query": "handsome boy",     "color": 0x3498db},
    "girl":   {"emoji": "👧", "label": "Girl Pic",    "query": "beautiful girl",   "color": 0xff69b4},
    "couple": {"emoji": "💑", "label": "Couple Pic",  "query": "romantic couple",  "color": 0xff4d6d},
    "anime":  {"emoji": "🌸", "label": "Anime Waifu", "query": None,               "color": 0x9b59b6},
}

class ImageCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ───── HELPERS ─────

    async def fetch_pexels_image(self, query: str) -> str | None:
        headers = {"Authorization": PEXELS_API_KEY}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.pexels.com/v1/search?query={query}&per_page=50",
                headers=headers
            ) as resp:
                data = await resp.json()
                if data.get("photos"):
                    return random.choice(data["photos"])["src"]["original"]
        return None

    async def fetch_waifu_image(self, category: str = "waifu") -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.waifu.pics/sfw/{category}") as resp:
                data = await resp.json()
                return data["url"]

    def make_embed(self, key: str, url: str) -> discord.Embed:
        info = COMMANDS_INFO[key]
        embed = discord.Embed(
            title=f"{info['emoji']} {info['label']}",
            color=info["color"]
        )
        embed.set_image(url=url)
        embed.set_footer(text="© CupidX HQ")
        return embed

    # ───── HYBRID COMMANDS ─────

    @commands.hybrid_command(name="image", description="Show all image commands")
    async def image_menu(self, ctx: commands.Context):
        """Show all image commands."""
        embed = discord.Embed(title="🖼️ Image Commands", color=0x3498db)
        embed.add_field(name="Commands", value=(
            f"`{ctx.prefix}boy` — Random boy picture\n"
            f"`{ctx.prefix}girl` — Random girl picture\n"
            f"`{ctx.prefix}couple` — Random couple picture\n"
            f"`{ctx.prefix}anime` — Random anime waifu"
        ), inline=False)
        embed.set_footer(text="© CupidX HQ")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="boy", description="Send a random boy picture")
    async def boy_image(self, ctx: commands.Context):
        """Send a random boy picture."""
        await ctx.defer() # Hybrid commands ke liye typing ki jagah defer use hota hai
        url = await self.fetch_pexels_image("handsome boy")
        if url:
            await ctx.send(embed=self.make_embed("boy", url))
        else:
            await ctx.send("❌ No boy image found. Try again later.")

    @commands.hybrid_command(name="girl", description="Send a random girl picture")
    async def girl_image(self, ctx: commands.Context):
        """Send a random girl picture."""
        await ctx.defer()
        url = await self.fetch_pexels_image("beautiful girl")
        if url:
            await ctx.send(embed=self.make_embed("girl", url))
        else:
            await ctx.send("❌ No girl image found. Try again later.")

    @commands.hybrid_command(name="couple", description="Send a random couple picture")
    async def couple_image(self, ctx: commands.Context):
        """Send a random couple picture."""
        await ctx.defer()
        url = await self.fetch_pexels_image("romantic couple")
        if url:
            await ctx.send(embed=self.make_embed("couple", url))
        else:
            await ctx.send("❌ No couple image found. Try again later.")

    @commands.hybrid_command(name="anime", description="Send a random anime waifu picture")
    async def anime_image(self, ctx: commands.Context):
        """Send a random anime waifu picture."""
        await ctx.defer()
        url = await self.fetch_waifu_image("waifu")
        await ctx.send(embed=self.make_embed("anime", url))

async def setup(bot):
    await bot.add_cog(ImageCommands(bot))
