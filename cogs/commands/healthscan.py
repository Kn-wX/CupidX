import discord
from discord.ext import commands
from datetime import datetime, timezone
import aiosqlite
from utils.config import OWNER_IDS


class HealthScan(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/premium.db'

    async def is_premium(self, guild_id):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT 1 FROM premium_guilds WHERE guild_id = ?",
                    (guild_id,)
                )
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            print(f"Premium check error: {e}")
            return False

    async def is_staff(self, guild_id, user_id):
        try:
            async with aiosqlite.connect("db/staff.db") as db:
                cursor = await db.execute(
                    "SELECT * FROM staff WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id)
                )
                return await cursor.fetchone()
        except:
            return None

    async def can_use(self, ctx):
        if ctx.author.id in OWNER_IDS:
            return True

        is_prem = await self.is_premium(ctx.guild.id)
        if not is_prem:
            return False

        if ctx.author.guild_permissions.administrator or ctx.guild.owner_id == ctx.author.id:
            return True

        return False


# ================= SCAN ================= #

    @commands.command(name="scan")
    async def scan(self, ctx, member: discord.Member=None):

        if not await self.can_use(ctx):
            return await ctx.send("<:CupidXCross:1473996646873436336> This command is only for **Premium Servers** (Admin/Owner use only).")

        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)

        now = datetime.now(timezone.utc)

        acc_age = (now - member.created_at).days
        join_age = (now - member.joined_at).days

        staff = await self.is_staff(ctx.guild.id, member.id)
        badges = ", ".join([b.name for b in member.public_flags.all()]) or "None"

        risk = "Low"
        if acc_age < 30:
            risk = "High"
        elif acc_age < 90:
            risk = "Medium"

        embed = discord.Embed(
            title="<a:CupidXSecurity:1474384985791270952> CupidX Deep Scan Analysis",
            color=discord.Color.red(),
            timestamp=now
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        if user.banner:
            embed.set_image(url=user.banner.url)

        embed.add_field(name="User", value=f"{member.mention}\nID: {member.id}", inline=False)
        embed.add_field(name="Account Created", value=f"{member.created_at.strftime('%Y-%m-%d')}\n({acc_age} Days)", inline=True)
        embed.add_field(name="Joined Server", value=f"{member.joined_at.strftime('%Y-%m-%d')}\n({join_age} Days)", inline=True)
        embed.add_field(name="Bot?", value=member.bot, inline=True)
        embed.add_field(name="Roles", value=len(member.roles)-1, inline=True)
        embed.add_field(name="Badges", value=badges, inline=False)
        embed.add_field(name="Staff Linked", value="Yes" if staff else "No", inline=True)
        embed.add_field(name="Risk Level", value=risk, inline=True)

        await ctx.send(embed=embed)


# ================= SERVER HEALTH ================= #

    @commands.command(name="serverhealth")
    async def serverhealth(self, ctx):

        if not await self.can_use(ctx):
            return await ctx.send("<:CupidXCross:1473996646873436336> This command is only for **Premium Servers**.")

        staff_count = 0
        try:
            async with aiosqlite.connect("db/staff.db") as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM staff WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                data = await cursor.fetchone()
                staff_count = data[0]
        except:
            pass

        bots = len([m for m in ctx.guild.members if m.bot])
        humans = len(ctx.guild.members) - bots

        score = 100
        if staff_count < 2:
            score -= 20
        if humans < 20:
            score -= 15
        if bots > humans:
            score -= 25

        status = "Safe"
        if score < 50:
            status = "Danger"
        elif score < 75:
            status = "Medium"

        embed = discord.Embed(
            title="CupidX Server Health Report",
            color=discord.Color.green()
        )

        embed.add_field(name="Members", value=humans)
        embed.add_field(name="Bots", value=bots)
        embed.add_field(name="Staff", value=staff_count)
        embed.add_field(name="Security Score", value=f"{score}%")
        embed.add_field(name="Status", value=status)

        await ctx.send(embed=embed)


# ================= GHOST AUDIT ================= #

    async def strict_ghost_check(self, ctx):

        # Bot Owner always allowed
        if ctx.author.id in OWNER_IDS:
            return True

        if not ctx.guild:
            return False

        # Must be premium server
        if not await self.is_premium(ctx.guild.id):
            return False

        # Only Administrator or Server Owner
        if ctx.author.guild_permissions.administrator:
            return True

        if ctx.guild.owner_id == ctx.author.id:
            return True

        return False


    async def calculate_threat(self, guild, member):
        score = 0
        deletes = 0
        role_updates = 0
        bans = 0

        try:
            async for entry in guild.audit_logs(limit=50):
                if entry.user.id != member.id:
                    continue

                if entry.action == discord.AuditLogAction.channel_delete:
                    deletes += 1
                    score += 25

                if entry.action == discord.AuditLogAction.role_update:
                    role_updates += 1
                    score += 10

                if entry.action == discord.AuditLogAction.ban:
                    bans += 1
                    score += 30
        except:
            pass

        if score >= 60:
            level = "HIGH 🔴"
        elif score >= 30:
            level = "MEDIUM 🟡"
        else:
            level = "LOW 🟢"

        return score, level, deletes, role_updates, bans


    @commands.command(name="ghostaudit")
    async def ghostaudit(self, ctx, member: discord.Member=None):

        if not await self.strict_ghost_check(ctx):
            return await ctx.send("👑 Premium Server + Administrator Required.")

        member = member or ctx.author
        score, level, deletes, role_updates, bans = await self.calculate_threat(ctx.guild, member)

        embed = discord.Embed(
            title="👻 Ghost Audit Report",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention}\nID: {member.id}", inline=False)
        embed.add_field(name="Channel Deletes", value=deletes)
        embed.add_field(name="Role Updates", value=role_updates)
        embed.add_field(name="Ban Actions", value=bans)
        embed.add_field(name="Threat Score", value=f"{score}/100", inline=False)
        embed.add_field(name="Threat Level", value=level, inline=False)

        await ctx.send(embed=embed)


    @discord.app_commands.command(name="ghostaudit", description="Premium Ghost Audit Scan")
    async def ghostaudit_slash(self, interaction: discord.Interaction, member: discord.Member):

        ctx = await commands.Context.from_interaction(interaction)

        if not await self.strict_ghost_check(ctx):
            return await interaction.response.send_message(
                "👑 Premium Server + Administrator Required.",
                ephemeral=True
            )

        score, level, deletes, role_updates, bans = await self.calculate_threat(interaction.guild, member)

        embed = discord.Embed(
            title="👻 Ghost Audit Report",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention}\nID: {member.id}", inline=False)
        embed.add_field(name="Channel Deletes", value=deletes)
        embed.add_field(name="Role Updates", value=role_updates)
        embed.add_field(name="Ban Actions", value=bans)
        embed.add_field(name="Threat Score", value=f"{score}/100", inline=False)
        embed.add_field(name="Threat Level", value=level, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    cog = HealthScan(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.ghostaudit_slash)