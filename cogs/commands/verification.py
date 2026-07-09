import discord

from discord.ext import commands

import os

import json

from datetime import datetime

COLOR = 0xFCD005  # Gold Theme

VERIFY_PATH = "data/verification"

os.makedirs(VERIFY_PATH, exist_ok=True)

# JSON SYSTEM

def get_config(gid: int):

    fp = f"{VERIFY_PATH}/{gid}.json"

    if not os.path.exists(fp):

        return {

            "enabled": False,

            "channel": None,

            "role": None,

            "message": "Click the button below to verify yourself.",

            "image": None,

            "icon": None,

            "log": None,

            "button": {"label": "Verify", "emoji": "✔️", "style": "green"},

            "stats": {"verified": 0}

        }

    return json.load(open(fp))

def save_config(gid: int, data: dict):

    fp = f"{VERIFY_PATH}/{gid}.json"

    json.dump(data, open(fp, "w"), indent=4)

BUTTON_STYLES = {

    "green": discord.ButtonStyle.success,

    "red": discord.ButtonStyle.danger,

    "grey": discord.ButtonStyle.secondary,

    "gray": discord.ButtonStyle.secondary,

    "blue": discord.ButtonStyle.primary,

    "blurple": discord.ButtonStyle.primary,

}

# BUTTON VIEW

class VerifyButton(discord.ui.View):

    def __init__(self, gid: int, role_id: int, log: int):

        super().__init__(timeout=None)

        self.gid = gid

        self.role_id = role_id

        self.log_channel = log

        cfg = get_config(gid)

        btn = cfg["button"]

        style = BUTTON_STYLES.get(btn["style"], discord.ButtonStyle.success)

        self.add_item(discord.ui.Button(

            label=btn["label"],

            emoji=btn["emoji"],

            style=style,

            custom_id=f"verify_button_{gid}"

        ))

# BUTTON HANDLER

class VerificationButtonHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, inter: discord.Interaction):
        if not inter.data:
            return
        cid = inter.data.get("custom_id")
        if not cid or not cid.startswith("verify_button_"):
            return

        gid = inter.guild.id
        user = inter.user
        cfg = get_config(gid)

        if not cfg["enabled"]:
            return await inter.response.send_message("Verification is currently disabled.", ephemeral=True)

        role = inter.guild.get_role(cfg["role"])
        if not role:
            return await inter.response.send_message("Verification Role is invalid or missing.", ephemeral=True)

        if role in user.roles:
            return await inter.response.send_message("You are already verified!", ephemeral=True)

        try:
            await user.add_roles(role)
        except:
             return await inter.response.send_message("I cannot give you the role. Please check my permissions.", ephemeral=True)

        cfg["stats"]["verified"] += 1
        save_config(gid, cfg)

        # LOG
        if cfg.get("log"):
            ch = inter.guild.get_channel(cfg["log"])
            if ch:
                embed = discord.Embed(
                    description=f"<:tick:1327829594954530896> **Verified:** {user.mention} (`{user.id}`)",
                    color=0x43B581
                )
                embed.set_author(name=f"{user}", icon_url=user.display_avatar.url)
                embed.timestamp = datetime.utcnow()
                try:
                    await ch.send(embed=embed)
                except:
                    pass

        # Nicer Success Message
        embed = discord.Embed(
            description=f"<:tick:1327829594954530896> Successfully verified as **{role.name}**!",
            color=0x43B581
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

# BUILD PANEL

async def build_panel(guild):
    cfg = get_config(guild.id)
    
    embed = discord.Embed(
        title="<:verified:1327829594954530896> Verification Required",
        description=cfg["message"].replace("{server}", guild.name),
        color=COLOR
    )
    
    if cfg.get("icon"):
        embed.set_thumbnail(url=cfg["icon"])
    
    if cfg.get("image"):
        embed.set_image(url=cfg["image"])
        
    embed.set_footer(text=f"{guild.name} • Secure Verification", icon_url=guild.icon.url if guild.icon else None)
    
    view = VerifyButton(
        gid=guild.id,
        role_id=cfg["role"],
        log=cfg.get("log")
    )
    return embed, view

# SEND PANEL

async def send_panel(guild):

    cfg = get_config(guild.id)

    if not cfg["enabled"]:

        return

    ch = guild.get_channel(cfg["channel"])

    if not ch:

        return

    embed, view = await build_panel(guild)

    try:

        return await ch.send(embed=embed, view=view)

    except:

        return None

# REFRESH PANEL

async def refresh_panel(guild):

    cfg = get_config(guild.id)

    ch = guild.get_channel(cfg["channel"]) if cfg["channel"] else None

    if not ch:

        return False

    # Delete old bot messages

    async for msg in ch.history(limit=30):

        if msg.author == guild.me:

            try:

                await msg.delete()

            except:

                pass

    await send_panel(guild)

    return True

# COMMANDS

class Verification(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="verification")

    async def verification(self, ctx, option=None, channel: discord.TextChannel=None, role: discord.Role=None):

        gid = ctx.guild.id

        cfg = get_config(gid)

        # HELP MENU

        if option is None:
            embed = discord.Embed(title="🛡️ Verification System", description="Secure your server with one-click verification.", color=COLOR)
            
            embed.add_field(
                name="Setup",
                value=(
                    f"`{ctx.prefix}verification enable <#channel> <@role>`\n"
                    f"`{ctx.prefix}verification disable`\n"
                    f"`{ctx.prefix}verification config`"
                ),
                inline=False
            )
            embed.add_field(
                name="Customization",
                value=(
                    f"`{ctx.prefix}verification message <text>`\n"
                    f"`{ctx.prefix}verification image <url>`\n"
                    f"`{ctx.prefix}verification icon <url>`\n"
                    f"`{ctx.prefix}verification button <style> <label> <emoji>`"
                ),
                inline=False
            )
            embed.add_field(
                name="Utility",
                value=(
                    f"`{ctx.prefix}verification log <#channel>`\n"
                    f"`{ctx.prefix}verification stats`\n"
                    f"`{ctx.prefix}verification refresh`"
                ),
                inline=False
            )
            return await ctx.reply(embed=embed)

        option = option.lower()

        # ENABLE

        if option == "enable":

            if not channel or not role:

                return await ctx.send("Usage: `$verification enable <channel> <role>`")

            cfg["enabled"] = True

            cfg["channel"] = channel.id

            cfg["role"] = role.id

            save_config(gid, cfg)

            await refresh_panel(ctx.guild)

            return await ctx.send(f"✅ Enabled in {channel.mention} using role {role.mention}")

        # DISABLE

        if option == "disable":

            cfg["enabled"] = False

            save_config(gid, cfg)

            return await ctx.send("❌ Disabled.")

        # CONFIG OVERVIEW

        if option == "config":

            e = discord.Embed(title="Verification Config", color=COLOR)

            e.add_field(name="Enabled", value=str(cfg["enabled"]))

            e.add_field(name="Channel", value=f"<#{cfg['channel']}>" if cfg["channel"] else "None")

            e.add_field(name="Role", value=f"<@&{cfg['role']}>" if cfg["role"] else "None")

            e.add_field(name="Message", value=cfg["message"])

            e.add_field(name="Image", value=cfg["image"] or "None")

            e.add_field(name="Icon", value=cfg["icon"] or "None")

            e.add_field(name="Button", value=f"{cfg['button']}")

            e.add_field(name="Log", value=f"<#{cfg['log']}>" if cfg["log"] else "None")

            e.add_field(name="Verified", value=cfg["stats"]["verified"])

            await ctx.send(embed=e)

            return

        # MESSAGE

        if option == "message":

            msg = ctx.message.content.replace("$verification message", "").strip()

            cfg["message"] = msg

            save_config(gid, cfg)

            return await ctx.send("Message updated.")

        # IMAGE

        if option == "image":

            url = ctx.message.content.replace("$verification image", "").strip()

            cfg["image"] = url

            save_config(gid, cfg)

            return await ctx.send("Image updated.")

        if option == "resetimage":

            cfg["image"] = None

            save_config(gid, cfg)

            return await ctx.send("Image removed.")

        # ICON

        if option == "icon":

            url = ctx.message.content.replace("$verification icon", "").strip()

            cfg["icon"] = url

            save_config(gid, cfg)

            return await ctx.send("Icon updated.")

        if option == "reseticon":

            cfg["icon"] = None

            save_config(gid, cfg)

            return await ctx.send("Icon removed.")

        # BUTTON

        if option == "button":

            args = ctx.message.content.split()

            if len(args) < 5:

                return await ctx.send("Usage: `$verification button <style> <label> <emoji>`")

            style, label, emoji = args[2], args[3], args[4]

            if style not in BUTTON_STYLES:

                return await ctx.send("Invalid style.")

            cfg["button"] = {"style": style, "label": label, "emoji": emoji}

            save_config(gid, cfg)

            return await ctx.send("Button updated.")

        # LOG CHANNEL

        if option == "log":

            if not channel:

                return await ctx.send("Usage: `$verification log <channel>`")

            cfg["log"] = channel.id

            save_config(gid, cfg)

            return await ctx.send(f"Log channel set to {channel.mention}")

        # STATS

        if option == "stats":

            return await ctx.send(f"Verified Users: **{cfg['stats']['verified']}**")

        if option == "resetstats":

            cfg["stats"]["verified"] = 0

            save_config(gid, cfg)

            return await ctx.send("Stats reset.")

        if option == "refresh":

            await refresh_panel(ctx.guild)

            return await ctx.send("Refreshed.")

        return await ctx.send("Invalid option.")

# LOAD COG
async def setup(bot):

    await bot.add_cog(Verification(bot))

    await bot.add_cog(VerificationButtonHandler(bot))

    # persistent buttons

    for guild in bot.guilds:

        cfg = get_config(guild.id)

        if cfg["enabled"] and cfg["role"]:

            bot.add_view(VerifyButton(

                gid=guild.id,

                role_id=cfg["role"],

                log=cfg.get("log")

            ))