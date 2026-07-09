import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import app_commands
import sqlite3

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = "db/rr.db"
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    guild_id INTEGER,
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled INTEGER DEFAULT 1
                )
            """)

    def add_reaction_role(self, guild_id, message_id, emoji, role_id):
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
                (guild_id, int(message_id), emoji, role_id)
            )

    def get_role_by_emoji(self, guild_id, message_id, emoji):
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute(
                "SELECT role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild_id, int(message_id), emoji)
            )
            result = cur.fetchone()
            return result[0] if result else None

    def get_dm_setting(self, guild_id):
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute("SELECT dm_enabled FROM rr_settings WHERE guild_id = ?", (guild_id,))
            row = cur.fetchone()
            return row[0] == 1 if row else True

    def set_dm_setting(self, guild_id, value):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT OR REPLACE INTO rr_settings (guild_id, dm_enabled) VALUES (?, ?)", (guild_id, value))

    # FIXED: message_id: str kiya gaya hai taaki slash command interface crash na ho
    @commands.hybrid_command(name="createrr", help="Create a reaction role.", usage="createrr <channel> <message_id> <emoji> <role>")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(message_id="The ID of the message (Copy-Paste from Discord)")
    async def createrr(self, ctx: Context, channel: discord.TextChannel, message_id: str, emoji: str, role: discord.Role):
        try:
            # Backend par string ko integer banaya
            real_msg_id = int(message_id.strip())
            message = await channel.fetch_message(real_msg_id)
            
            await message.add_reaction(emoji)
            self.add_reaction_role(ctx.guild.id, message.id, emoji, role.id)
            
            await ctx.send(f"✅ Reaction role added: React with {emoji} to get {role.name}", ephemeral=True if ctx.interaction else False)
        except ValueError:
            await ctx.send("❌ Invalid Message ID. Please copy a valid numeric ID.", ephemeral=True if ctx.interaction else False)
        except discord.NotFound:
            await ctx.send("❌ Message not found in that channel.", ephemeral=True if ctx.interaction else False)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="dmrr", help="Enable or disable DM messages for reaction roles.", usage="dmrr <enable|disable>")
    @commands.has_permissions(manage_guild=True)
    async def dmrr(self, ctx: Context, mode: str):
        if mode.lower() not in ["enable", "disable"]:
            await ctx.send("❌ Use `enable` or `disable`.", ephemeral=True if ctx.interaction else False)
            return

        value = 1 if mode.lower() == "enable" else 0
        self.set_dm_setting(ctx.guild.id, value)
        await ctx.send(f"✅ DM messages for reaction roles {'enabled' if value else 'disabled'}.", ephemeral=True if ctx.interaction else False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None or payload.member.bot:
            return

        role_id = self.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            member = payload.member

            if role and member:
                try:
                    await member.add_roles(role, reason="Reaction role added")
                    
                    # FIXED: Reaction removal code yahan se hata diya gaya hai taaki reaction bana rahe

                    # DM if enabled
                    if self.get_dm_setting(payload.guild_id):
                        try:
                            await member.send(f"✅ You received the **{role.name}** role from {guild.name}.")
                        except discord.Forbidden:
                            pass
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id is None:
            return

        role_id = self.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(role_id)
            if role and member:
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                except discord.Forbidden:
                    pass

# Setup
async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
