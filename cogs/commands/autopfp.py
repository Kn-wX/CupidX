import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
import random
from discord.ui import LayoutView, Container, TextDisplay, Separator

# ========================= EMOJIS & COLORS =========================
emojitick = "<:CupidXtick1:1474369967271968949>"
emojicross = "<:CupidXCross:1473996646873436336>"
emojiwarn = "<:CupidXWarning:1474348304186867784>"
emojidot = "<a:CupidXdot:1473986328126558209>"

color_primary = 0x134E5E
color_dark = 0x2F3136

DATA_FILE = "data/autopfp_data.json"


# ========================= V2 CARD HELPER =========================
def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    c.add_item(Separator())
    view.add_item(c)
    return view


# ========================= STORAGE HELPERS =========================
def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f, indent=4)
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ========================= COG =========================
class AutoPFP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()
        self.autopfp_loop.start()

    # ---------------- CONFIG ACCESS ----------------
    def get_server(self, guild: discord.Guild) -> dict:
        gid = str(guild.id)
        if gid not in self.data:
            self.data[gid] = {
                "enabled": False,
                "channel": None,
                "interval": 60,  # seconds
                "last": 0,
            }
            save_data(self.data)
        return self.data[gid]

    # ---------------- PFP SOURCES ----------------
    async def get_random_pfp(self) -> str | None:
        anime_sources = [
            "https://api.waifu.pics/sfw/waifu",
            "https://api.waifu.pics/sfw/neko",
            "https://api.catboys.com/img",
            "https://nekos.best/api/v2/neko",
        ]
        aesthetic_sources = [
            "https://raw.githubusercontent.com/AestheticPFP/collection/main/list.json"
        ]

        choice_type = random.choice(["anime", "aesthetic"])

        async with aiohttp.ClientSession() as session:
            if choice_type == "anime":
                url = random.choice(anime_sources)
                async with session.get(url) as r:
                    data = await r.json()
                    if isinstance(data, dict):
                        if "url" in data:
                            return data["url"]
                        if "message" in data:
                            return data["message"]
                        if "results" in data and data["results"]:
                            return data["results"][0].get("url")
            else:
                async with session.get(aesthetic_sources[0]) as r:
                    data = await r.json()
                    if isinstance(data, list) and data:
                        return random.choice(data)

        return None

    # ========================= COMMANDS =========================
    @commands.hybrid_group(
        name="autopfp",
        invoke_without_command=True,
        help="Automatically drop random PFPs in a channel.",
    )
    @commands.guild_only()
    async def autopfp(self, ctx: commands.Context):
        prefix = ctx.prefix
        cfg = self.get_server(ctx.guild)
        status = "Active" if cfg.get("enabled") else "Disabled"
        channel = ctx.guild.get_channel(cfg.get("channel") or 0)
        interval = cfg.get("interval", 60)

        body = (
            f"Serve a steady stream of anime / aesthetic profile pictures in a chosen channel.\n\n"
            f"**Current status**\n"
            f"{emojidot} State: **{status}**\n"
            f"{emojidot} Channel: {channel.mention if channel else '`Not set`'}\n"
            f"{emojidot} Interval: **{interval} seconds**\n\n"
            f"**Sub‑commands**\n"
            f"{emojidot} `{prefix}autopfp enable #channel` – start sending PFPS\n"
            f"{emojidot} `{prefix}autopfp disable` – stop the loop\n"
            f"{emojidot} `{prefix}autopfp interval <seconds>` – change the delay"
        )
        await ctx.send(view=v2_card("AutoPFP Control", body))

    @autopfp.command(name="enable")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def autopfp_enable(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = self.get_server(ctx.guild)
        cfg["enabled"] = True
        cfg["channel"] = channel.id
        cfg["last"] = 0
        save_data(self.data)

        body = (
            f"{emojitick} AutoPFP has been **enabled**.\n\n"
            f"Channel: {channel.mention}\n"
            f"Interval: **{cfg['interval']} seconds**\n\n"
            "The next picture will appear once the interval timer completes."
        )
        await ctx.send(view=v2_card("AutoPFP Enabled", body))

    @autopfp.command(name="disable")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def autopfp_disable(self, ctx: commands.Context):
        cfg = self.get_server(ctx.guild)
        if not cfg.get("enabled"):
            body = (
                f"{emojiwarn} AutoPFP is already **disabled** here.\n\n"
                f"Use `{ctx.prefix}autopfp enable #channel` to start it."
            )
            return await ctx.send(view=v2_card("Nothing To Disable", body))

        cfg["enabled"] = False
        save_data(self.data)

        body = (
            f"{emojicross} AutoPFP has been **stopped** for **{ctx.guild.name}**.\n\n"
            "No more PFPs will be posted until you enable it again."
        )
        await ctx.send(view=v2_card("AutoPFP Disabled", body))

    @autopfp.command(name="interval")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def autopfp_interval(self, ctx: commands.Context, seconds: int):
        if seconds < 10:
            body = (
                f"{emojiwarn} Interval must be at least **10 seconds**.\n\n"
                "Keep it reasonable to avoid rate limits."
            )
            return await ctx.send(view=v2_card("Interval Too Low", body))

        cfg = self.get_server(ctx.guild)
        cfg["interval"] = seconds
        cfg["last"] = 0
        save_data(self.data)

        body = (
            f"{emojitick} Interval updated.\n\n"
            f"AutoPFP will now post every **{seconds} seconds** "
            "in the configured channel."
        )
        await ctx.send(view=v2_card("Interval Updated", body))

    # ========================= BACKGROUND LOOP =========================
    @tasks.loop(seconds=5)
    async def autopfp_loop(self):
        for gid, cfg in list(self.data.items()):
            if not cfg.get("enabled"):
                continue

            channel_id = cfg.get("channel")
            interval = cfg.get("interval", 60)
            last = cfg.get("last", 0) + 5
            cfg["last"] = last

            if last < interval:
                continue

            cfg["last"] = 0
            save_data(self.data)

            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                continue

            url = await self.get_random_pfp()
            if not url:
                continue

            embed = discord.Embed(
                title="🖼 Daily PFP Drop",
                color=color_dark,
                description="Here's something new for your profile or server aesthetics.",
            )
            embed.set_image(url=url)
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                continue

    @autopfp_loop.before_loop
    async def before_autopfp(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoPFP(bot))
