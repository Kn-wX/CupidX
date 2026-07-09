import discord
from discord.ext import commands
from discord.ui import View, Select
from deep_translator import GoogleTranslator

# ── Supported Languages ──
LANGUAGES = {
    "🇬🇧 English":     "en",
    "🇮🇳 Hindi":       "hi",
    "🇸🇦 Arabic":      "ar",
    "🇫🇷 French":      "fr",
    "🇩🇪 German":      "de",
    "🇪🇸 Spanish":     "es",
    "🇵🇹 Portuguese":  "pt",
    "🇷🇺 Russian":     "ru",
    "🇯🇵 Japanese":    "ja",
    "🇰🇷 Korean":      "ko",
    "🇨🇳 Chinese":     "zh-CN",
    "🇮🇹 Italian":     "it",
    "🇹🇷 Turkish":     "tr",
    "🇧🇩 Bengali":     "bn",
    "🇵🇰 Urdu":        "ur",
    "🇮🇩 Indonesian":  "id",
    "🇹🇭 Thai":        "th",
    "🇳🇱 Dutch":       "nl",
    "🇵🇱 Polish":      "pl",
    "🇸🇪 Swedish":     "sv",
}

# Split into two pages for the Select (max 25 options)
LANG_PAGE_1 = list(LANGUAGES.items())[:25]


class LanguageSelect(Select):
    def __init__(self, original_text: str, author_id: int):
        self.original_text = original_text
        self.author_id = author_id

        options = [
            discord.SelectOption(label=name, value=code)
            for name, code in LANG_PAGE_1
        ]

        super().__init__(
            placeholder="🌐 Choose target language...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="translate_lang_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "⛔ Only the command author can select a language.",
                ephemeral=True
            )
            return

        target_code = self.values[0]
        target_name = next(n for n, c in LANGUAGES.items() if c == target_code)

        await interaction.response.defer()

        try:
            translated = GoogleTranslator(source="auto", target=target_code).translate(self.original_text)

            embed = discord.Embed(
                title=f"🌐 Translation — {target_name}",
                color=0x00b0f4
            )
            embed.add_field(name="📝 Original", value=f"> {self.original_text}", inline=False)
            embed.add_field(name=f"✅ Translated", value=f"> {translated}", inline=False)
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )

            # Disable the select after use
            view = View()
            done_select = LanguageSelect(self.original_text, self.author_id)
            done_select.disabled = True
            view.add_item(done_select)

            await interaction.edit_original_response(content=None, embed=embed, view=view)

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Translation failed: `{str(e)}`",
                embed=None,
                view=None
            )


class TranslateView(View):
    def __init__(self, text: str, author_id: int):
        super().__init__(timeout=60)
        self.add_item(LanguageSelect(text, author_id))

    async def on_timeout(self):
        # Disable all items on timeout
        for item in self.children:
            item.disabled = True


class TranslateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="tr",
        aliases=["lang"],
        help="Translate any text into your chosen language.",
        usage="tr <text>"
    )
    async def translate(self, ctx: commands.Context, *, text: str = None):
        if not text:
            embed = discord.Embed(title="🌐 Translate Commands", color=0x00b0f4)
            embed.add_field(name="Commands", value=(
                f"`{ctx.prefix}tr <text>` — Translate to any language (dropdown)\n"
                f"`{ctx.prefix}hinglish <text>` — Hinglish to English"
            ), inline=False)
            embed.add_field(name="Languages", value="English, Hindi, Arabic, French, German, Spanish, Japanese, Korean, Chinese, Urdu + more", inline=False)
            embed.set_footer(text="© CupidX HQ")
            return await ctx.reply(embed=embed, ephemeral=True if ctx.interaction else False)

        embed = discord.Embed(
            title="🌐 Select Target Language",
            description=f"📝 **Text to translate:**\n> {text}\n\nChoose a language below:",
            color=0x00b0f4
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        view = TranslateView(text, ctx.author.id)

        msg = await ctx.reply(
            embed=embed,
            view=view,
            ephemeral=True if ctx.interaction else False
        )

        # Disable on timeout
        await view.wait()
        try:
            done_select = LanguageSelect(text, ctx.author.id)
            done_select.disabled = True
            timeout_view = View()
            timeout_view.add_item(done_select)
            await msg.edit(view=timeout_view)
        except Exception:
            pass

    # Keep original hinglish command as well
    @commands.hybrid_command(
        name="hinglish",
        help="Translate Hinglish to English.",
        usage="hinglish <text>"
    )
    async def hinglish(self, ctx: commands.Context, *, text: str = None):
        if not text:
            return await ctx.reply(
                "⚠️ Please provide some Hinglish text to translate.",
                ephemeral=True if ctx.interaction else False
            )

        msg = await ctx.reply(
            "🔄 Translating Hinglish...",
            ephemeral=True if ctx.interaction else False
        )

        try:
            translated = GoogleTranslator(source="auto", target="en").translate(text)

            embed = discord.Embed(
                title="🗣️ Hinglish → English",
                color=0x00b0f4
            )
            embed.add_field(name="📝 Original", value=f"> {text}", inline=False)
            embed.add_field(name="✅ Translated", value=f"> {translated}", inline=False)
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )
            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await msg.edit(content=f"❌ Translation failed: `{str(e)}`")


async def setup(bot):
    await bot.add_cog(TranslateCog(bot))
