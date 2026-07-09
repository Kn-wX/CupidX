import discord
from discord.ext import commands

class QR(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x2b2d31
        self.arrow = "<:CupidXarrow:1474383919725150362>"

    @commands.command(name="qr", aliases=["qrcode"])
    @commands.has_permissions(administrator=True)
    async def qr(self, ctx):
        embed = discord.Embed(
            title="Payment Platform",
            description="You can make the payment via UPI using the QR code below:",
            color=self.color
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1431155774352134216/1476511325256679456/Screenshot_20260226-145819_GPay.png?ex=69a163d4&is=69a01254&hm=1017cf3dc1cbd9ebc420a62308250906c17ea7405c1b0d69cd49148970f7a6d5&")
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name="staffrules", aliases=["rulestaff", "rulesstaff"])
    @commands.has_permissions(administrator=True)
    async def staffrules(self, ctx):
        embed = discord.Embed(
            title="🛡️ Staff Rules & Regulations",
            description="All staff members are required to strictly follow these rules:",
            color=self.color
        )
        
        rules_part1 = (
            f"{self.arrow} NP Access can be granted for a maximum of 1 months only.\n"
            f"{self.arrow} Staff cannot extend NP without explicit Owner approval.\n"
            f"{self.arrow} Add the bot only to servers that you personally manage.\n"
            f"{self.arrow} Do not add the bot to untrusted or unknown servers.\n"
            f"{self.arrow} No unauthorized free unlimited access is permitted.\n"
            f"{self.arrow} Misuse of staff permissions is strictly prohibited."
        )
        
        rules_part2 = (
            f"{self.arrow} Be respectful to all community members.\n"
            f"{self.arrow} Do not abuse your permissions or staff commands.\n"
            f"{self.arrow} Unnecessary pings to higher staff are not allowed.\n"
            f"{self.arrow} Maintain a professional attitude in all public channels.\n"
            f"{self.arrow} Strictly follow the server's Terms of Service.\n"
            f"{self.arrow} The Owner's final decision is binding in all matters."
        )
        
        embed.add_field(name="📜 Rules Part 1", value=rules_part1, inline=False)
        embed.add_field(name="📜 Rules Part 2", value=rules_part2, inline=False)
        embed.set_footer(text="Created by mr.x", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name="staffr", aliases=["staffrequirement", "requirementstaff"])
    @commands.has_permissions(administrator=True)
    async def staffr(self, ctx):
        embed = discord.Embed(
            title="📋 Staff Recruitment Requirements",
            description="To join our official staff team, you must fulfill the following criteria:",
            color=self.color
        )
        
        req_text = (
            f"{self.arrow} You must add the bot to your managed servers.\n"
            f"{self.arrow} Your combined servers must have a total of at least **15,000 (15k) members**.\n"
            f"{self.arrow} All servers must be active; fake member counts will not be considered.\n"
            f"{self.arrow} You should have a basic understanding of moderation and bot management."
        )
        
        embed.add_field(name="🚀 Mandatory Criteria:", value=req_text, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # Simplified Error Handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ Administrator permissions required.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ Retry in `{round(error.retry_after, 1)}s`.")

async def setup(bot):
    await bot.add_cog(QR(bot))
