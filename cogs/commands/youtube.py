import discord

from discord.ext import commands

import urllib.parse

import urllib.request

import re

from utils.Tools import blacklist_check, ignore_check

class Youtube(commands.Cog):

    """YouTube search command Cog"""

    def __init__(self, bot: commands.Bot):

        self.bot = bot

    @commands.command(name="yt", aliases=["youtube"])

    @blacklist_check()

    @ignore_check()

    async def search_youtube(self, ctx: commands.Context, *, search_query: str):

        """Searches YouTube for the given query and returns the top video result."""

        try:

            # Prepare search URL

            query_string = urllib.parse.urlencode({"search_query": search_query})

            url = f"https://www.youtube.com/results?{query_string}"

            # Request page content

            async with ctx.typing():

                with urllib.request.urlopen(url) as response:

                    html_content = response.read().decode()

            # Extract video IDs from search results

            search_results = re.findall(r"watch\?v=(\S{11})", html_content)

            if not search_results:

                await ctx.send("❌ No search results found.")

                return

            # Send first result

            video_url = f"https://www.youtube.com/watch?v={search_results[0]}"

            embed = discord.Embed(

                title="YouTube Search Result",

                description=f"**[Click here to watch the top result]({video_url})**",

                color=discord.Color.red()

            )

            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:

            await ctx.send(f"⚠️ An error occurred while searching YouTube: `{e}`")

async def setup(bot: commands.Bot):

    await bot.add_cog(Youtube(bot))