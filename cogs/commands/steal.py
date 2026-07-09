import discord
from discord.ext import commands
from discord.ui import View
import requests
from io import BytesIO
import re
from utils.Tools import *

class Steal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="steal",
        help="Reply to a message to steal up to 25 emojis or stickers",
        aliases=["eadd"]
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_emojis=True)
    async def steal(self, ctx):

        if not ctx.message.reference:
            return await ctx.send(embed=discord.Embed(
                title="Steal",
                description="Reply to a message containing emojis or stickers (max 25).",
                color=0x2f3136
            ))

        ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        attachments = ref_message.attachments[:25]
        stickers = ref_message.stickers[:25]
        emojis = re.findall(r'<a?:\w+:\d+>', ref_message.content)[:25]

        if not attachments and not stickers and not emojis:
            return await ctx.send(embed=discord.Embed(
                title="Steal",
                description="No emoji or sticker found in replied message.",
                color=0x2f3136
            ))

        await self.create_buttons(ctx, attachments, stickers, emojis)

    # ---------------- EMOJI ADD ---------------- #

    async def add_emoji_silent(self, guild, url, name, animated):
        try:
            if not self.has_emoji_slot(guild, animated):
                return False

            sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)[:32]
            response = requests.get(url)

            await guild.create_custom_emoji(
                name=sanitized_name,
                image=response.content
            )
            return True
        except:
            return False

    # ---------------- STICKER ADD ---------------- #

    async def add_sticker_silent(self, guild, url, name):
        try:
            if len(guild.stickers) >= self.get_max_sticker_count(guild):
                return False

            sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)[:32]
            response = requests.get(url)
            img = BytesIO(response.content)

            await guild.create_sticker(
                name=sanitized_name,
                description="Added by CupidX",
                file=discord.File(img, filename="sticker.png"),
                emoji="⭐"
            )
            return True
        except:
            return False

    # ---------------- SLOT SYSTEM ---------------- #

    def has_emoji_slot(self, guild, animated):
        normal = [e for e in guild.emojis if not e.animated]
        animated_e = [e for e in guild.emojis if e.animated]
        max_normal, max_animated = self.get_max_emoji_count(guild)

        return len(animated_e) < max_animated if animated else len(normal) < max_normal

    def get_max_emoji_count(self, guild):
        if guild.premium_tier == 3:
            return 250, 250
        elif guild.premium_tier == 2:
            return 150, 150
        elif guild.premium_tier == 1:
            return 100, 100
        return 50, 50

    def get_max_sticker_count(self, guild):
        if guild.premium_tier == 3:
            return 60
        elif guild.premium_tier == 2:
            return 30
        elif guild.premium_tier == 1:
            return 15
        return 5

    # ---------------- PANEL ---------------- #

    async def create_buttons(self, ctx, attachments, stickers, emojis):

        normal = [e for e in ctx.guild.emojis if not e.animated]
        animated_e = [e for e in ctx.guild.emojis if e.animated]
        max_normal, max_animated = self.get_max_emoji_count(ctx.guild)

        found_count = len(emojis) + len(attachments) + len(stickers)

        description = (
            f"**Found {found_count} emoji(s)**\n\n"
            f"➡ **Emojis:** {len(normal)}/{max_normal} static, "
            f"{len(animated_e)}/{max_animated} animated\n"
            f"➡ **Stickers:** {len(ctx.guild.stickers)}/{self.get_max_sticker_count(ctx.guild)}"
        )

        embed = discord.Embed(
            title="🧩 Steal from Message",
            description=description,
            color=0x2f3136
        )

        class StealView(View):
            def __init__(self, cog):
                super().__init__(timeout=60)
                self.cog = cog

            @discord.ui.button(label="Add as Emoji", style=discord.ButtonStyle.secondary)
            async def emoji_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)

                await interaction.response.defer()

                added = 0
                failed = 0

                for emote in emojis:
                    name = emote.split(':')[1]
                    emoji_id = emote.split(':')[2][:-1]
                    animated = emote.startswith('<a')

                    url = f'https://cdn.discordapp.com/emojis/{emoji_id}.gif' if animated \
                        else f'https://cdn.discordapp.com/emojis/{emoji_id}.png'

                    success = await self.cog.add_emoji_silent(ctx.guild, url, name, animated)
                    added += success
                    failed += not success

                # 🔥 REMOVE PANEL
                await interaction.message.edit(view=None)

                result = discord.Embed(
                    description=f"✅ Added **{added}** emoji(s), **{failed}** failed.",
                    color=0x2f3136
                )

                await interaction.followup.send(embed=result)

            @discord.ui.button(label="Add as Sticker", style=discord.ButtonStyle.secondary)
            async def sticker_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)

                await interaction.response.defer()

                added = 0
                failed = 0

                for sticker in stickers:
                    success = await self.cog.add_sticker_silent(
                        ctx.guild,
                        sticker.url,
                        sticker.name
                    )
                    added += success
                    failed += not success

                # 🔥 REMOVE PANEL
                await interaction.message.edit(view=None)

                result = discord.Embed(
                    description=f"✅ Added **{added}** sticker(s), **{failed}** failed.",
                    color=0x2f3136
                )

                await interaction.followup.send(embed=result)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)

                await interaction.message.edit(view=None)
                await interaction.response.send_message("Cancelled.", ephemeral=True)

        await ctx.send(embed=embed, view=StealView(self))


async def setup(bot):
    await bot.add_cog(Steal(bot))