import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.config import OWNER_IDS
import aiosqlite
from utils.detectfile import *

# QR_IMAGE_URL imported from utils.detectfile

FREE_CLAIM_CHANNEL_ID = 1487370590930206871

# ================================================================
#  PLAN DATA — edit prices / descriptions here only
# ================================================================
PLANS = [
    {
        "id":    "trial",
        "emoji": "<a:Star_Blue:1487146818553778389>",
        "label": "7 Day Trial",
        "price": "FREE",
        "desc":  "Try premium for 7 days at no cost.",
        "color": 0x57F287,
    },
    {
        "id":    "30day",
        "emoji": "<:16218booster:1486976482118205553>",
        "label": "30 Days",
        "price": "₹90",
        "desc":  "1 month of full premium access.",
        "color": 0x5865F2,
    },
    {
        "id":    "3month",
        "emoji": "<:54538booster:1486976516964487310>",
        "label": "3 Months",
        "price": "₹200",
        "desc":  "3 months — best value for active servers.",
        "color": 0xFCD005,
    },
    {
        "id":    "1year",
        "emoji": "<:fire:1487022213256319077>",
        "label": "1 Year",
        "price": "₹800",
        "desc":  "12 months of uninterrupted premium.",
        "color": 0xED4245,
    },
    {
        "id":    "lifetime",
        "emoji": "<:crown:1486975202125680753>",
        "label": "Lifetime",
        "price": "₹5,000",
        "desc":  "Pay once. Stay premium forever.",
        "color": 0xFF73FA,
    },
]

FEATURES = [
    ("<a:cupidxcongratulations:1474783458676179176>", "24/7 Music Mode"),
    ("<:CupidXCommands:1475152376737566722>",         "Server Backup & Restore"),
    ("<:CupidXBots:1475367184854290584>",             "Message Leaderboards"),
    ("<a:Star_Blue:1487146818553778389>",             "Exclusive Admin Tools"),
    ("<:CupidXuser:1475151935379341382>",             "Custom Bot Profile"),
    ("<:flower:1487021616612511846>",                 "Priority Support"),
]


# ================================================================
#  HELPER — build plan embed (QR for paid, channel redirect for trial)
# ================================================================
def _build_plan_embed(plan: dict) -> discord.Embed:
    if plan["id"] == "trial":
        embed = discord.Embed(
            title=f"{plan['emoji']} {plan['label']} — {plan['price']}",
            description=(
                f"**{plan['desc']}**\n\n"
                f"<a:Star_Blue:1487146818553778389> This plan is completely **FREE**!\n\n"
                f"<:CupidXtick1:1474369967271968949> To claim your free trial, visit\n"
                f"<#1487370590930206871> and claim it from there.\n\n"
                f"> No payment required — just go to the channel and claim! 🎉"
            ),
            color=plan["color"],
        )
        embed.set_footer(text="💎 CupidX Premium • Powered by Knowx")
        return embed

    # Paid plans — show QR
    embed = discord.Embed(
        title=f"{plan['emoji']} {plan['label']} — {plan['price']}",
        description=(
            f"**{plan['desc']}**\n\n"
            f"<:CupidXMail:1475192722578215083> Scan the QR code below using **GPay / PhonePe / Paytm / UPI**.\n\n"
            f"<:CupidXtick1:1474369967271968949> After payment, **screenshot** the receipt and contact the **server owner** with:\n"
            f"```\nPlan: {plan['label']}\nAmount: {plan['price']}\nServer ID: <your server id>\n```"
        ),
        color=plan["color"],
    )
    embed.set_image(url=QR_IMAGE_URL)
    embed.set_footer(text="💎 CupidX Premium • Powered by Knowx")
    return embed


# ================================================================
#  HELPER — build the main perk embed
# ================================================================
def _build_perk_embed() -> discord.Embed:
    embed = discord.Embed(
        title="<:16218booster:1486976482118205553> CupidX Premium",
        description=(
            "<:crown:1486975202125680753> **Unlock the full power of CupidX for your server.**\n"
            "Choose a plan below and pay via UPI / GPay.\n\u200b"
        ),
        color=0xFCD005,
    )

    plans_text = ""
    for p in PLANS:
        plans_text += f"{p['emoji']} **{p['label']}** — `{p['price']}`\n{p['desc']}\n\n"
    embed.add_field(
        name="<:CupidXfile:1479528347506835556> Plans & Pricing",
        value=plans_text.strip(),
        inline=False,
    )

    features_text = "\n".join(f"{emoji} {feat}" for emoji, feat in FEATURES)
    embed.add_field(
        name="<a:Star_Blue:1487146818553778389> What You Get",
        value=features_text,
        inline=False,
    )

    embed.add_field(
        name="<:CupidXMail:1475192722578215083> How to Buy",
        value=(
            "1️⃣ Click **💎 Buy Premium** and select your plan.\n"
            "2️⃣ Scan the **QR code** and complete UPI payment.\n"
            "3️⃣ Send the **screenshot + Server ID** to the owner.\n"
            "4️⃣ Premium will be **activated within 24 hours**.\n\n"
            "<a:Star_Blue:1487146818553778389> **7 Day Trial** is completely FREE — "
            "claim it from <#1487370590930206871>!"
        ),
        inline=False,
    )

    embed.set_footer(text="💎 CupidX Premium System • Powered by Knowx")
    return embed


# ================================================================
#  PERSISTENT PLAN SELECT — shown on main channel message
#  custom_id required for persistence across bot restarts
# ================================================================
class PlanSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{p['label']} — {p['price']}",
                description=p["desc"],
                value=p["id"],
            )
            for p in PLANS
        ]
        super().__init__(
            placeholder="📋 Select a plan to purchase...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="persistent_plan_select",
        )

    async def callback(self, interaction: discord.Interaction):
        chosen_id = self.values[0]
        plan = next((p for p in PLANS if p["id"] == chosen_id), None)
        if not plan:
            return await interaction.response.send_message(
                "Something went wrong. Please try again.", ephemeral=True
            )
        embed = _build_plan_embed(plan)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ================================================================
#  BUY VIEW — persistent, survives bot restart
# ================================================================
class BuyView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(PlanSelect())

    @discord.ui.button(
        label="💎 Buy Premium",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_buy_button",
        row=1,
    )
    async def buy(self, interaction: discord.Interaction, button: Button):
        embed = _build_perk_embed()
        view = EphemeralPlanView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="📞 Contact Owner",
        style=discord.ButtonStyle.gray,
        custom_id="persistent_contact_button",
        row=1,
    )
    async def contact(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="<:CupidXuser:1475151935379341382> Contact for Premium",
            description=(
                "To activate your premium after payment:\n\n"
                "<:CupidXtick1:1474369967271968949> DM the **bot owner** directly.\n"
                "<:CupidXCommands:1475152376737566722> Send your **payment screenshot** + **Server ID**.\n"
                "<a:CupidXtimer:1475327919558496370> Premium will be activated **within 24 hours**."
            ),
            color=0xFCD005,
        )
        embed.set_footer(text="💎 CupidX Premium • Powered by Knowx")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ================================================================
#  EPHEMERAL PLAN SELECT — custom_id set so it survives bot restart
# ================================================================
class EphemeralPlanSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{p['label']} — {p['price']}",
                description=p["desc"],
                value=p["id"],
            )
            for p in PLANS
        ]
        super().__init__(
            placeholder="📋 Select a plan to see payment details...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="persistent_ephemeral_plan_select",
        )

    async def callback(self, interaction: discord.Interaction):
        chosen_id = self.values[0]
        plan = next((p for p in PLANS if p["id"] == chosen_id), None)
        if not plan:
            return await interaction.response.send_message(
                "Something went wrong.", ephemeral=True
            )
        embed = _build_plan_embed(plan)
        try:
            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EphemeralPlanView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(EphemeralPlanSelect())


# ================================================================
#  MAIN COG
# ================================================================
class React(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/np.db"

    # ================== PREMIUM COMMAND ==================

    @commands.command(name="perk")
    async def perk(self, ctx):
        embed = _build_perk_embed()
        await ctx.send(embed=embed, view=BuyView(self.bot))

    # ================== OWNER / STAFF REACTION SYSTEM ==================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot or not message.guild:
            return

        for owner_id in OWNER_IDS:
            if f"<@{owner_id}>" in message.content or f"<@!{owner_id}>" in message.content:

                owner_emojis = [
                    "<:CupidX1Owner:1474455304774094848>",
                    "<:cupixstaff:1474453722946863295>",
                    "<:cupidxRedCrown:1474432762504282152>",
                ]

                for emoji in owner_emojis:
                    try:
                        await message.add_reaction(emoji)
                    except Exception:
                        pass
                return

        # ===== STAFF DETECT FROM DATABASE =====
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT id FROM staff") as cursor:
                    staff_ids = [row[0] for row in await cursor.fetchall()]
        except Exception:
            staff_ids = []

        for staff_id in staff_ids:
            if f"<@{staff_id}>" in message.content or f"<@!{staff_id}>" in message.content:

                staff_emojis = [
                    "<:cupixstaff:1474453722946863295>",
                    "<:cupidxRedCrown:1474432762504282152>",
                ]

                for emoji in staff_emojis:
                    try:
                        await message.add_reaction(emoji)
                    except Exception:
                        pass
                return


# ================================================================
#  SETUP — register all persistent views on bot start / restart
# ================================================================
async def setup(bot):
    bot.add_view(BuyView(bot))
    bot.add_view(EphemeralPlanView(bot))
    await bot.add_cog(React(bot))
)
