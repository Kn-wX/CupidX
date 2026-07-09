import discord
from discord.ext import commands
import asyncio

class OwnerAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_entry(self, guild, action, target_id):
        # Wait for Audit Logs to update
        await asyncio.sleep(3) 
        async for entry in guild.audit_logs(limit=10, action=action):
            if entry.target.id == target_id:
                return entry
        return None

# ================= MASTER SECURITY AUDIT EMBED =================
    async def send_master_alert(self, guild, action_name, target, executor):
        # STRICT OWNER BYPASS: If the executor is the Server Owner, stop the alert.
        if executor.id == guild.owner_id:
            return

        # Fetch full user details to get Banner and Account History
        try:
            # We fetch the Executor's info because they are the one who triggered the action
            trigger_user = await self.bot.fetch_user(executor.id)
        except:
            trigger_user = executor

        embed = discord.Embed(
            title="🚨 SECURITY AUDIT | ADMINISTRATIVE ACTION",
            description=f"A sensitive action was detected in **{guild.name}**",
            color=0xff0000
        )
        
        # Set the Trigger User (Admin/Member) as the primary focus of the report
        embed.set_author(name=f"Triggered By: {trigger_user}", icon_url=trigger_user.display_avatar.url)
        embed.set_thumbnail(url=trigger_user.display_avatar.url)
        
        # Display the Executor's Banner if available (A-Z Profile Details)
        if hasattr(trigger_user, 'banner') and trigger_user.banner:
            embed.set_image(url=trigger_user.banner.url)

        # --- Detailed Information Fields ---
        embed.add_field(
            name="🛡️ Executor (Admin/User)", 
            value=f"**User:** {trigger_user}\n**ID:** `{trigger_user.id}`\n**Mention:** {trigger_user.mention}", 
            inline=True
        )
        embed.add_field(
            name="👤 Target (Affected Entity)", 
            value=f"**Name:** {target}\n**ID:** `{target.id}`", 
            inline=True
        )
        
        # Account History & Timestamps
        created_at = discord.utils.format_dt(trigger_user.created_at, style='R')
        joined_at = "Not Available"
        if isinstance(trigger_user, discord.Member):
            joined_at = discord.utils.format_dt(trigger_user.joined_at, style='R')
        
        embed.add_field(
            name="📊 Executor History", 
            value=f"**Account Created:** {created_at}\n**Joined Server:** {joined_at}", 
            inline=False
        )
        
        embed.add_field(
            name="📝 Incident Log", 
            value=f"The user {trigger_user.mention} performed **{action_name}**. This report has been sent to the Owner as the executor is not the Server Owner.", 
            inline=False
        )

        embed.set_footer(text="CupidX Advanced Security Monitoring", icon_url=self.bot.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        try:
            await guild.owner.send(embed=embed)
        except:
            # Silently fail if Owner DMs are closed
            pass

# ================= PUNISHMENT NOTIFICATION (User DM) =================
    async def user_punishment_dm(self, user, guild, action):
        try:
            embed = discord.Embed(
                title="🚨 Security Enforcement",
                description=(
                    f"You have been **{action}** from **{guild.name}**.\n\n"
                    "**Reason:** Detection of suspicious administrative activity or security violation."
                ),
                color=0xff0000
            )
            embed.set_footer(text="CupidX Global Security Engine")
            await user.send(embed=embed)
        except:
            pass

# ================= SECURITY EVENT LISTENERS =================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        entry = await self.get_entry(guild, discord.AuditLogAction.ban, user.id)
        if not entry or entry.user.id == guild.owner_id: 
            return
        
        await self.send_master_alert(guild, "MEMBER BAN", user, entry.user)
        
        # DM the user only if the action was taken by the Bot (Anti-Nuke trigger)
        if entry.user.id == self.bot.user.id:
            await self.user_punishment_dm(user, guild, "BANNED")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        entry = await self.get_entry(guild, discord.AuditLogAction.kick, member.id)
        if not entry or entry.user.id == guild.owner_id: 
            return
        
        await self.send_master_alert(guild, "MEMBER KICK", member, entry.user)
        
        if entry.user.id == self.bot.user.id:
            await self.user_punishment_dm(member, guild, "KICKED")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot: 
            return
        guild = member.guild
        entry = await self.get_entry(guild, discord.AuditLogAction.bot_add, member.id)
        if not entry or entry.user.id == guild.owner_id: 
            return
        
        # Report the admin who added the unauthorized bot
        await self.send_master_alert(guild, "UNAUTHORIZED BOT ADDED", member, entry.user)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        entry = await self.get_entry(guild, discord.AuditLogAction.channel_delete, channel.id)
        if not entry or entry.user.id == guild.owner_id: 
            return
        
        await self.send_master_alert(guild, "CHANNEL DELETION", channel, entry.user)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild
        entry = await self.get_entry(guild, discord.AuditLogAction.role_delete, role.id)
        if not entry or entry.user.id == guild.owner_id: 
            return
        
        await self.send_master_alert(guild, "ROLE DELETION", role, entry.user)

async def setup(bot):
    await bot.add_cog(OwnerAlert(bot))
