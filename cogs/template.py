import discord
from discord.ext import commands
from discord import app_commands
import asyncio

class TemplateConfirmView(discord.ui.View):
    def __init__(self, ctx_or_inter, template_code):
        super().__init__(timeout=60)
        self.ctx_or_inter = ctx_or_inter
        self.template_code = template_code

    @discord.ui.button(label="Confirm & Apply", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Security: Only the Server Owner can confirm
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Error: Only the Server Owner can confirm this!", ephemeral=True)
        
        await interaction.response.edit_message(content="<a:CupidXloading:1474386958741536891> **Processing... 1.5s delay added per channel for safety.**", view=None)
        
        try:
            template = await interaction.client.fetch_guild_template(self.template_code)
            guild = interaction.guild

            for channel in guild.channels:
                try: 
                    await channel.delete()
                    await asyncio.sleep(1.5)
                except: continue
            
            await template.create_guild(name=guild.name) 
            await interaction.followup.send("✅ **Success: Template applied!**")
        except Exception as e:
            await interaction.followup.send(f"❌ **Error:** `{e}`")

class Template(commands.Cog):
    def __init__(self, client):
        self.client = client

    # --- PREFIX COMMAND ($applytemplate) ---
    @commands.command(name="applytemplate")
    @commands.has_permissions(administrator=True)
    async def prefix_apply(self, ctx, link: str):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply("❌ **Owner Only:** This command is restricted to the Server Owner.")
        
        if len(ctx.guild.channels) > 50:
            return await ctx.reply(f"❌ **Safety Block:** Server has {len(ctx.guild.channels)} channels. Max limit is 50.")

        code = link.split('/')[-1]
        view = TemplateConfirmView(ctx, code)
        embed = discord.Embed(title="CupidX Security", description=f"Applying Template: `{code}`\nClick below to confirm.", color=0x134E5E)
        await ctx.reply(embed=embed, view=view)

    # --- SLASH COMMAND (/applytemplate) ---
    @app_commands.command(name="applytemplate", description="Apply a server template (Owner Only)")
    @app_commands.describe(link="Template link")
    async def slash_apply(self, interaction: discord.Interaction, link: str):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ **Owner Only!**", ephemeral=True)

        if len(interaction.guild.channels) > 50:
            return await interaction.response.send_message(f"❌ **Safety Block:** Too many channels ({len(interaction.guild.channels)}).", ephemeral=True)

        code = link.split('/')[-1]
        view = TemplateConfirmView(interaction, code)
        await interaction.response.send_message(f"⚠️ **Confirm Template:** `{code}`?", view=view)

async def setup(client):
    await client.add_cog(Template(client))
