import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.ui_v2 import v2_card

# ===============================
#          EMOJI CATEGORY
# ===============================
class Emojis:
    DELETE = "<:CupidXdelete:1474795676251459748>"
    USER = "<:CupidXuser:1475151935379341382>"
    MENTION = "<:CupidXmention:1476575411247906897>"
    COMMANDS = "<:CupidXCommands:1475152376737566722>"
    TICK = "<:CupidXtick1:1474369967271968949>"
    ADMIN = "<:CupidXautomod:1474356609122697382>"


class KickView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=120)
        self.member = member
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji=Emojis.DELETE)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="kick",
        help="Kicks a member from the server.",
        usage="kick <member> [reason]",
        aliases=["kickmember"]
    )
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick_command(
        self,
        ctx,
        member: discord.Member = commands.parameter(description="The member to kick"),
        *,
        reason: str = commands.parameter(description="Reason for the kick", default=None)
    ):
        reason = reason or "No reason provided"

        if member == ctx.author:
            return await ctx.reply("You cannot kick yourself.")

        if member == ctx.bot.user:
            return await ctx.reply("You cannot kick me.")

        if not ctx.author == ctx.guild.owner:
            if member == ctx.guild.owner:
                return await ctx.reply("I cannot kick the server owner.")

            if ctx.author.top_role <= member.top_role:
                return await ctx.reply("You cannot kick a member with a higher or equal role.")

        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.reply("I cannot kick a member with a higher or equal role.")

        if member not in ctx.guild.members:
            embed = discord.Embed(
                description="**Member Not Found:** The specified member does not exist in this server.",
                color=self.color
            )
            view = KickView(member)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        dm_status = "Yes"
        try:
            await member.send(
                f"You have been kicked from **{ctx.guild.name}**. Reason: {reason}"
            )
        except (discord.Forbidden, discord.HTTPException):
            dm_status = "No"

        await member.kick(reason=f"Kicked by {ctx.author} | Reason: {reason}")

        body = (
            f"{Emojis.USER} **Target User:** [{member}](https://discord.com/users/{member.id})\n"
            f"{Emojis.MENTION} **User Mention:** {member.mention}\n"
            f"{Emojis.COMMANDS} **Reason:** {reason}\n"
            f"{Emojis.TICK} **DM Sent:** {dm_status}\n\n"
            f"**{Emojis.ADMIN} Moderator:** {ctx.author.mention}"
        )

        card_view = v2_card(f"Successfully Kicked {member.name}", body)
        btn_view = KickView(member)
        
        await ctx.send(view=card_view)
        message = await ctx.send(view=btn_view)
        btn_view.message = message


async def setup(bot):
    await bot.add_cog(Kick(bot))
