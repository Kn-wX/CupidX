import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import time
from utils.ai_utils import poly_image_gen, generate_image_prodia
from prodia.constants import Model
from utils.Tools import *

blacklisted_words = [
    "naked", "nude", "nudes", "teen", "gay", "lesbian", "porn", "xnxx",
    "bitch", "loli", "hentai", "explicit", "pornography", "adult", "XXX",
    "sex", "erotic", "dick", "vagina", "pussy", "lick", "creampie", "nsfw",
    "hardcore", "ass", "anal", "anus", "boobs", "tits", "cum", "cunnilingus",
    "squirt", "penis", "masturbate", "masturbation", "orgasm", "orgy", "fap",
    "fapping", "fuck", "fucking", "handjob", "cowgirl", "doggystyle", "blowjob",
    "boobjob", "boobies", "horny", "nudity"
]

blocked = [
    "minor", "minors", "kid", "kids", "child", "children", "baby", "babies",
    "toddler", "childporn", "todd", "underage"
]


class CooldownManager:
    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.cooldowns = {}

    def check_cooldown(self, user_id: int):
        now = time.time()
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = [now]
            return None
        self.cooldowns[user_id] = [
            t for t in self.cooldowns[user_id] if now - t < self.per
        ]
        if len(self.cooldowns[user_id]) >= self.rate:
            retry_after = self.per - (now - self.cooldowns[user_id][0])
            return retry_after
        self.cooldowns[user_id].append(now)
        return None


cooldown_manager = CooldownManager(rate=1, per=60.0)


class AiStuffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="imagine")
    async def imagine_help(self, ctx):
        """Show imagine command info."""
        embed = discord.Embed(title="🎨 Imagine — AI Image Generator", color=0xFCD005)
        embed.add_field(name="Usage", value="`/imagine` — Slash command only", inline=False)
        embed.add_field(name="Options", value=(
            "`prompt` — Describe the image\n"
            "`model` — 21 AI models to choose from\n"
            "`sampler` — Denoising method\n"
            "`negative` — What to exclude\n"
            "`seed` — For reproducible results"
        ), inline=False)
        embed.add_field(name="Note", value="60s cooldown. NSFW only in NSFW channels.", inline=False)
        embed.set_footer(text="© CupidX HQ")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @app_commands.command(name="imagine", description="🎨 Generate an image using AI")
    @discord.app_commands.choices(
        model=[
            discord.app_commands.Choice(name='✨ Elldreth vivid mix (Landscapes, Stylized characters)', value='ELLDRETHVIVIDMIX'),
            discord.app_commands.Choice(name='💪 Deliberate v2 (Anything you want)', value='DELIBERATE'),
            discord.app_commands.Choice(name='🔮 Dreamshaper (Highly detailed)', value='DREAMSHAPER_6'),
            discord.app_commands.Choice(name='🎼 Lyriel', value='LYRIEL_V16'),
            discord.app_commands.Choice(name='💥 Anything diffusion (Good for anime)', value='ANYTHING_V4'),
            discord.app_commands.Choice(name='🌅 Openjourney (Midjourney alternative)', value='OPENJOURNEY'),
            discord.app_commands.Choice(name='🏞️ Realistic (Lifelike pictures)', value='REALISTICVS_V20'),
            discord.app_commands.Choice(name='👨‍🎨 Portrait (For headshots)', value='PORTRAIT'),
            discord.app_commands.Choice(name='🌟 Rev animated (Illustration, Anime)', value='REV_ANIMATED'),
            discord.app_commands.Choice(name='🤖 Analog', value='ANALOG'),
            discord.app_commands.Choice(name='🌌 AbyssOrangeMix', value='ABYSSORANGEMIX'),
            discord.app_commands.Choice(name='🌌 Dreamlike v1', value='DREAMLIKE_V1'),
            discord.app_commands.Choice(name='🌌 Dreamlike v2', value='DREAMLIKE_V2'),
            discord.app_commands.Choice(name='🌌 Dreamshaper 5', value='DREAMSHAPER_5'),
            discord.app_commands.Choice(name='🌌 MechaMix', value='MECHAMIX'),
            discord.app_commands.Choice(name='🌌 MeinaMix', value='MEINAMIX'),
            discord.app_commands.Choice(name='🌌 Stable Diffusion v14', value='SD_V14'),
            discord.app_commands.Choice(name='🌌 Stable Diffusion v15', value='SD_V15'),
            discord.app_commands.Choice(name="🌌 Shonin's Beautiful People", value='SBP'),
            discord.app_commands.Choice(name="🌌 TheAlly's Mix II", value='THEALLYSMIX'),
            discord.app_commands.Choice(name='🌌 Timeless', value='TIMELESS'),
        ],
        sampler=[
            discord.app_commands.Choice(name='📏 Euler (Recommended)', value='Euler'),
            discord.app_commands.Choice(name='📏 Euler a', value='Euler a'),
            discord.app_commands.Choice(name='📐 Heun', value='Heun'),
            discord.app_commands.Choice(name='💥 DPM++ 2M Karras', value='DPM++ 2M Karras'),
            discord.app_commands.Choice(name='💥 DPM++ SDE Karras', value='DPM++ SDE Karras'),
            discord.app_commands.Choice(name='🔍 DDIM', value='DDIM'),
        ]
    )
    @discord.app_commands.describe(
        prompt="Write an amazing prompt for an image",
        model="Model to generate image",
        sampler="Sampler for denoising",
        negative="What you do NOT want in the image",
    )
    async def imagine(
        self,
        interaction: discord.Interaction,
        prompt: str,
        model: discord.app_commands.Choice[str],
        sampler: discord.app_commands.Choice[str],
        negative: str = None,
        seed: int = None
    ):
        # ── Cooldown check ──
        retry_after = cooldown_manager.check_cooldown(interaction.user.id)
        if retry_after:
            await interaction.response.send_message(
                f"⏳ You're on cooldown. Try again in **{retry_after:.0f}s**.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # ── Content filter ──
        if any(w in prompt.lower() for w in blocked):
            await interaction.followup.send(
                "🚫 That prompt is not allowed. Please use a different one.",
                ephemeral=True
            )
            return

        is_nsfw = any(w in prompt.lower() for w in blacklisted_words)
        if is_nsfw and not interaction.channel.nsfw:
            await interaction.followup.send(
                "🔞 NSFW images can only be generated in **NSFW channels**.",
                ephemeral=True
            )
            return

        # ── Generate ──
        model_uid = Model[model.value].value[0]
        try:
            imagefileobj = await generate_image_prodia(prompt, model_uid, sampler.value, seed, negative)
        except aiohttp.ClientPayloadError:
            await interaction.followup.send(
                "❌ Image generation failed. Please try again later.",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Unexpected error: `{e}`", ephemeral=True)
            return

        # ── Prepare file ──
        display_prompt = f"||{prompt}||" if is_nsfw else prompt
        img_file = discord.File(
            imagefileobj,
            filename="image.png",
            spoiler=is_nsfw,
            description=prompt
        )

        # ── Build embed ──
        embed = discord.Embed(
            title=f"🎨 AI Generated Image",
            color=0xFCD005 if is_nsfw else discord.Color.random()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="📝 Prompt", value=f"> {display_prompt}", inline=False)
        embed.add_field(
            name="⚙️ Details",
            value=(
                f"🖼️ **Model:** `{model.name}`\n"
                f"🎛️ **Sampler:** `{sampler.value}`\n"
                f"🌱 **Seed:** `{seed if seed is not None else 'Random'}`"
            ),
            inline=True
        )
        if negative:
            embed.add_field(name="🚫 Negative Prompt", value=f"> {negative}", inline=False)
        if is_nsfw:
            embed.add_field(name="🔞 NSFW", value="> True", inline=True)
        embed.set_image(url="attachment://image.png")
        embed.set_footer(text="© CupidX HQ", icon_url=self.bot.user.avatar.url)

        await interaction.followup.send(embed=embed, file=img_file, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AiStuffCog(bot))
