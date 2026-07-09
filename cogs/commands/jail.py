import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import re
from typing import Optional

DB_FILE = "db/jail.db"

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_FILE)
        # Create tables for jail system and settings
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jailed (
                guild_id TEXT,
                user_id TEXT,
                mod_id TEXT,
                reason TEXT,
                jailed_at TEXT,
                duration INTEGER,
                roles TEXT,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jail_settings (
                guild_id TEXT PRIMARY KEY,
                jail_role TEXT,
                jail_channel TEXT,
                mod_role TEXT,
                log_channel TEXT
            );
        """)
        # Safe migration for roles column
        try:
            self.conn.execute("SELECT roles FROM jailed LIMIT 1;")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE jailed ADD COLUMN roles TEXT;")
        self.conn.commit()

        self.jail_check_loop.start()

    def cog_unload(self):
        self.jail_check_loop.cancel()
        self.conn.close()

    def get_setting(self, guild_id, field):
        cursor = self.conn.execute(f"SELECT {field} FROM jail_settings WHERE guild_id = ?", (str(guild_id),))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_setting(self, guild_id, field, value):
        self.conn.execute(f"""
            INSERT INTO jail_settings (guild_id, {field})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {field} = excluded.{field}
        """, (str(guild_id), str(value)))
        self.conn.commit()

    def parse_duration(self, duration_str: str):
        if not duration_str: return None
        pattern = re.compile(r'((?P<hours>\d+)h)?((?P<minutes>\d+)m)?')
        match = pattern.fullmatch(duration_str.lower())
        if not match:
            return None
        hours = int(match.group('hours') or 0)
        minutes = int(match.group('minutes') or 0)
        return (hours * 60 + minutes) * 60 if (hours or minutes) else None

    @tasks.loop(minutes=1)
    async def jail_check_loop(self):
        now = datetime.utcnow()
        cursor = self.conn.execute("SELECT guild_id, user_id, duration, jailed_at, roles FROM jailed")
        for guild_id, user_id, duration, jailed_at, roles in cursor.fetchall():
            if not duration:
                continue
            jailed_time = datetime.fromisoformat(jailed_at)
            if (now - jailed_time).total_seconds() >= duration:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        await self.unjail_member(guild, member)

    async def unjail_member(self, guild, member):
        jail_role_id = self.get_setting(guild.id, "jail_role")
        if jail_role_id:
            jail_role = guild.get_role(int(jail_role_id))
            if jail_role and jail_role in member.roles:
                await member.remove_roles(jail_role, reason="Unjailed")

        cursor = self.conn.execute("SELECT roles FROM jailed WHERE guild_id = ? AND user_id = ?", (str(guild.id), str(member.id)))
        row = cursor.fetchone()
        if row and row[0]:
            role_ids = map(int, row[0].split(","))
            roles = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
            try:
                await member.add_roles(*roles, reason="Restored previous roles after jail")
            except: pass

        self.conn.execute("DELETE FROM jailed WHERE guild_id = ? AND user_id = ?", (str(guild.id), str(member.id)))
        self.conn.commit()

        try:
            await member.send(f"🔓 You have been unjailed in **{guild.name}**.")
        except:
            pass

        log_channel_id = self.get_setting(guild.id, "log_channel")
        if log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔓 Member Unjailed", color=0xFCD005)
                embed.add_field(name="User", value=member.mention)
                embed.timestamp = datetime.utcnow()
                embed.set_footer(text=f"{guild.name}")
                await log_channel.send(embed=embed)

    # --- Configuration Command ---
    @commands.hybrid_command(name="jailsetup", description="Configure jail settings for the server")
    @commands.has_permissions(administrator=True)
    async def jailsetup(self, ctx, role: discord.Role, channel: discord.TextChannel, log_channel: discord.TextChannel = None):
        self.set_setting(ctx.guild.id, "jail_role", role.id)
        self.set_setting(ctx.guild.id, "jail_channel", channel.id)
        if log_channel:
            self.set_setting(ctx.guild.id, "log_channel", log_channel.id)
        
        embed = discord.Embed(title="✅ Jail System Configured", color=0xFCD005)
        embed.add_field(name="Jail Role", value=role.mention, inline=True)
        embed.add_field(name="Jail Channel", value=channel.mention, inline=True)
        if log_channel:
            embed.add_field(name="Log Channel", value=log_channel.mention, inline=True)
        await ctx.send(embed=embed)

    # --- Main Jail Command ---
    @commands.hybrid_command(name="jail", description="Jail a member or view help menu")
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx, member: Optional[discord.Member] = None, duration: str = None, *, reason="No reason provided"):
        # Help menu shown if no member is mentioned
        if member is None:
            embed = discord.Embed(title="🔒 Jail System Help", color=0xFCD005)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.description = (
                "**Usage:**\n"
                "`jailsetup <role> <channel> [logs]` - Set up the system\n"
                "`jail <user> [time] [reason]` - Send a user to jail\n"
                "`unjail <user>` - Release a user from jail\n"
                "`jailhistory <user>` - View jail history records\n\n"
                "**Time Format:** `1h`, `30m`, `1h30m`"
            )
            embed.set_footer(text="CupidX Jail System")
            return await ctx.send(embed=embed)

        jail_role_id = self.get_setting(ctx.guild.id, "jail_role")
        jail_channel_id = self.get_setting(ctx.guild.id, "jail_channel")
        log_channel_id = self.get_setting(ctx.guild.id, "log_channel")

        if not jail_role_id or not jail_channel_id:
            return await ctx.send("⚠️ **Jail system is not fully configured.** Please use `/jailsetup` first.")

        jail_role = ctx.guild.get_role(int(jail_role_id))
        if not jail_role:
            return await ctx.send("⚠️ **Configured jail role not found.** Please update your settings.")

        duration_secs = self.parse_duration(duration) if duration else None
        jailed_at = datetime.utcnow().isoformat()
        roles_str = ",".join(str(r.id) for r in member.roles if r != ctx.guild.default_role)

        self.conn.execute("DELETE FROM jailed WHERE guild_id = ? AND user_id = ?", (str(ctx.guild.id), str(member.id)))
        self.conn.execute("""
            INSERT INTO jailed (guild_id, user_id, mod_id, reason, jailed_at, duration, roles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(ctx.guild.id), str(member.id), str(ctx.author.id), reason, jailed_at, duration_secs, roles_str))
        self.conn.commit()

        try:
            await member.edit(roles=[jail_role], reason=f"Jailed by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("❌ **Permission Denied:** I don't have permission to change roles for this member.")

        await ctx.send(f"🔒 {member.mention} has been jailed. Duration: **{duration or 'Permanent'}**.")

        if log_channel_id:
            log_channel = ctx.guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔒 Member Jailed", color=discord.Color.red())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Duration", value=duration or "Permanent", inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)

    @commands.hybrid_command(name="unjail", description="Release a member from jail")
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx, member: discord.Member):
        await self.unjail_member(ctx.guild, member)
        await ctx.send(f"✅ {member.mention} has been successfully unjailed.")

    @commands.hybrid_command(name="jailhistory", description="Check jail record for a member")
    async def jailhistory(self, ctx, member: discord.Member):
        cursor = self.conn.execute("""
            SELECT reason, jailed_at, duration, mod_id FROM jailed
            WHERE guild_id = ? AND user_id = ?
        """, (str(ctx.guild.id), str(member.id)))
        row = cursor.fetchone()
        if row:
            reason, jailed_at, duration, mod_id = row
            mod = ctx.guild.get_member(int(mod_id))
            jailed_time = datetime.fromisoformat(jailed_at)
            embed = discord.Embed(title="📄 Jail Record", color=discord.Color.orange())
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Jailed At", value=jailed_time.strftime("%Y-%m-%d %H:%M:%S UTC"))
            embed.add_field(name="Duration", value=f"{duration // 60} minutes" if duration else "Permanent")
            embed.add_field(name="Jailed By", value=mod.mention if mod else "Unknown")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ No active jail record found for {member.mention}.")

async def setup(bot):
    await bot.add_cog(Jail(bot))
