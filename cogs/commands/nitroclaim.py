import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.config import SUPPORT_SERVER

class NitroView(View):
    def __init__(self, user):
        super().__init__(timeout=45)
        self.user = user

    @discord.ui.button(label="🔥 CLAIM NITRO NOW", style=discord.ButtonStyle.green, emoji="🎁")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "Ye button sirf original user ke liye hai!", ephemeral=True
            )

        embed = discord.Embed(
            title="🔐 SECURITY VERIFICATION",
            description=f"""
**{interaction.user.mention} Almost Done!**

1️⃣ Join Support Server  
2️⃣ React in #verify  
3️⃣ Get Nitro Code Instantly!

⏱️ 15 Seconds Left!
""",
            color=0x00ff88
        )

        view = View()
        view.add_item(Button(
            label="📱 JOIN SUPPORT SERVER",
            url=SUPPORT_SERVER,
            style=discord.ButtonStyle.link,
            emoji="🔗"
        ))

        await interaction.response.edit_message(embed=embed, view=view)

        try:
            dm = discord.Embed(
                title="🎁 Your Nitro Reserved!",
                description=f"""
Hey {interaction.user.name}

👉 Join Now:
{SUPPORT_SERVER}

Staff will DM code in 10 seconds!
""",
                color=0x5865F2
            )
            await interaction.user.send(embed=dm)
        except:
            pass


class NitroClaim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ✅ PREFIX COMMAND
    @commands.command(name="nitro")
    async def nitro(self, ctx):

        embed = discord.Embed(
            title="🎉 NITRO GIFT CLAIMED!",
            description=f"""
{ctx.author.mention}

You've won FREE Discord Nitro!

🔥 Includes:
• Server Boost  
• Custom Emojis  
• HD Streaming  
• Bigger Uploads  
• Custom Profiles  

LIMITED TIME – Claim Now!
""",
            color=0x5865F2
        )

        embed.add_field(name="Time Remaining", value="00:05:23")
        embed.add_field(name="Success Rate", value="98.7%")

        view = NitroView(ctx.author)

        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(NitroClaim(bot))