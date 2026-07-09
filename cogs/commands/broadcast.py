import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import List
from utils.config import OWNER_IDS

def is_owner():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in OWNER_IDS
    return app_commands.check(predicate)

class Broadcast(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="broadcast", description="Broadcast a message to all servers (Owner Only)")
    @app_commands.describe(guild_id="Optional: ID of a specific guild to broadcast to")
    @is_owner()
    async def broadcast(self, interaction: discord.Interaction, message: str, guild_id: str = None):
        
        targets = []
        if guild_id:
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    await interaction.response.send_message("<:CupidXCross:1473996646873436336> Guild not found.", ephemeral=True)
                    return
                targets = [guild]
            except ValueError:
                await interaction.response.send_message("<:CupidXCross:1473996646873436336> Invalid Guild ID format.", ephemeral=True)
                return
        else:
            targets = list(self.bot.guilds)

        total_guilds = len(targets)
        est_time_sec = total_guilds * 2.5
        est_time_str = f"{int(est_time_sec // 60)}m {int(est_time_sec % 60)}s" if est_time_sec >= 60 else f"{est_time_sec}s"
        
        embed = discord.Embed(title="📢 Broadcast Started", color=discord.Color.blue())
        embed.add_field(name="Total Guilds", value=str(total_guilds))
        embed.add_field(name="Estimated Time", value=est_time_str)
        embed.add_field(name="Progress", value=f"0 / {total_guilds}")
        embed.add_field(name="Status", value="Initializing...")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
        success_count = 0
        failure_count = 0
        failed_guilds: List[str] = []
        
        for i, guild in enumerate(targets, 1):
            target_channel = None
            
            # 1. Try to find announcement channel (must be public)
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.is_news():
                     # Check if @everyone can view
                     if channel.permissions_for(guild.default_role).view_channel:
                         target_channel = channel
                         break
            
            # 2. If no announcement channel, find first available PUBLIC text channel
            if not target_channel:
                for channel in guild.text_channels:
                    # Check bot permissions AND public access
                    bot_perms = channel.permissions_for(guild.me)
                    public_perms = channel.permissions_for(guild.default_role)
                    
                    if bot_perms.send_messages and bot_perms.view_channel and public_perms.view_channel:
                        target_channel = channel
                        break
            
            status_text = ""
            if target_channel:
                try:
                    await target_channel.send(message)
                    success_count += 1
                    status_text = f"Sent to {guild.name}"
                except Exception as e:
                    failure_count += 1
                    failed_guilds.append(f"{guild.name} (Error: {str(e)})")
                    status_text = f"Failed {guild.name}"
            else:
                failure_count += 1
                failed_guilds.append(f"{guild.name} (No suitable channel)")
                status_text = f"Skipped {guild.name}"
            
            # Update Embed
            embed.set_field_at(2, name="Progress", value=f"{i} / {total_guilds}")
            embed.set_field_at(3, name="Status", value=status_text)
            
            # Only edit every update (since 2.5s delay is slow enough to not hit rate limits)
            try:
                await interaction.edit_original_response(embed=embed)
            except:
                pass

            # Rate limit safe behavior
            await asyncio.sleep(2.5)
            
        # Summary
        summary_title = "<:CupidXtick1:1474369967271968949> Broadcast Complete"
        summary_color = discord.Color.green()
        
        final_embed = discord.Embed(title=summary_title, color=summary_color)
        final_embed.add_field(name="Total Guilds", value=str(total_guilds))
        final_embed.add_field(name="Success", value=str(success_count))
        final_embed.add_field(name="Failures", value=str(failure_count))
        
        if failed_guilds:
            # Truncate if too long
            failed_list = "\n".join(failed_guilds[:10])
            if len(failed_guilds) > 10:
                failed_list += f"\n...and {len(failed_guilds) - 10} more."
            final_embed.add_field(name="Failed Guilds", value=failed_list, inline=False)
            
        try:
            await interaction.edit_original_response(embed=final_embed)
        except:
            pass

    @broadcast.error
    async def broadcast_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("<:CupidXWarning:1474348304186867784> You are not authorized to use this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"<:CupidXCross:1473996646873436336> An error occurred: {str(error)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcast(bot))
    print("Loaded Broadcast Cog")
