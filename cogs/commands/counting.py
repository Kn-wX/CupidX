from __future__ import annotations
from utils.detectfile import *
import json
import os
from typing import Dict, Any

import discord
from discord.ext import commands

from discord.ui import LayoutView, Container, TextDisplay, Separator

# ====================== CONSTANTS ======================

DATA_FILE = "data/counting_data.json"

EMOJI_TICK = "<:nex_Tick:1422411439049674815>"
EMOJI_CROSS = "<:nextra_cross:1422411673544822905>"
EMOJI_WARN = "<:warning:1422425521379217438>"
EMOJI_DOT = "<a:dot:1443525009590194241>"

# ====================== V2 CARD HELPER ======================

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view

# ====================== DATA HANDLERS ======================

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f, indent=4)
    
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ====================== COG ======================

class Counting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()

    def get_server(self, guild: discord.Guild) -> Dict[str, Any]:
        gid = str(guild.id)
        if gid not in self.data:
            self.data[gid] = {
                "channel": None,
                "current": 1,
                "last_user": None,
                "highscore": 0,
                "enabled": True,
                "rewards": [],
                "logs": [],
                "stats": {}
            }
            save_data(self.data)
        return self.data[gid]

    # ====================== ROOT GROUP ======================

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def count(self, ctx: commands.Context) -> None:
        body = (
            "🔢 **Counting Commands**\n\n"
            f"{EMOJI_DOT} `{ctx.prefix}count setchannel #channel`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count enable/disable`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count reset`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count status`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count reward add/remove/list`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count leaderboard`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count logs`"
        )
        await ctx.reply(view=v2_card("Counting – Commands", body))

    # ====================== BASIC ADMIN ======================

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def setchannel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        s = self.get_server(ctx.guild)
        s["channel"] = channel.id
        save_data(self.data)
        await ctx.reply(view=v2_card("📌 Channel Set", f"Counting channel: {channel.mention}"))

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def set(self, ctx: commands.Context, number: int) -> None:
        s = self.get_server(ctx.guild)
        s["current"] = number
        save_data(self.data)
        await ctx.reply(view=v2_card("🔢 Number Set", f"Current number forced to **{number}**"))

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def setstart(self, ctx: commands.Context, number: int) -> None:
        s = self.get_server(ctx.guild)
        s["current"] = number
        save_data(self.data)
        await ctx.reply(view=v2_card("🟢 Start Number", f"Starting number set to **{number}**"))

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def enable(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        s["enabled"] = True
        save_data(self.data)
        await ctx.reply(view=v2_card("🟩 Enabled", "Counting is now **enabled**!"))

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        s["enabled"] = False
        save_data(self.data)
        await ctx.reply(view=v2_card("🟥 Disabled", "Counting is now **disabled**!"))

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def reset(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        s["current"] = 1
        s["last_user"] = None
        save_data(self.data)
        await ctx.reply(view=v2_card("♻ Reset", "Counting reset to **1**"))

    @count.command()
    async def status(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        channel = ctx.guild.get_channel(s["channel"]) or "Not set"
        body = (
            f"**Channel:** {channel.mention}\n"
            f"**Current:** {s['current']}\n"
            f"**Highscore:** {s['highscore']}\n"
            f"**Enabled:** {'✅ Yes' if s['enabled'] else '❌ No'}"
        )
        await ctx.reply(view=v2_card("📊 Status", body))

    # ====================== REWARDS ======================

    @count.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def reward(self, ctx: commands.Context) -> None:
        body = (
            f"{EMOJI_DOT} `{ctx.prefix}count reward add 100 @role`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count reward remove 100`\n"
            f"{EMOJI_DOT} `{ctx.prefix}count reward list`"
        )
        await ctx.reply(view=v2_card("🎁 Rewards", body))

    @reward.command()
    async def add(self, ctx: commands.Context, number: int, *, role: discord.Role) -> None:
        s = self.get_server(ctx.guild)
        s["rewards"].append({"number": number, "role": role.id})
        save_data(self.data)
        await ctx.reply(view=v2_card("🎉 Reward Added", f"At **{number}**, give <@&{role.id}>"))

    @reward.command()
    async def remove(self, ctx: commands.Context, number: int) -> None:
        s = self.get_server(ctx.guild)
        s["rewards"] = [r for r in s["rewards"] if r["number"] != number]
        save_data(self.data)
        await ctx.reply(view=v2_card("❌ Reward Removed", f"Removed reward for **{number}**"))

    @reward.command()
    async def list(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        if not s["rewards"]:
            await ctx.reply(view=v2_card("📭 Rewards", "No rewards set"))
            return
        
        rewards_list = "\n".join([f"{EMOJI_DOT} **{r['number']}** → <@&{r['role']}>" for r in s["rewards"]])
        await ctx.reply(view=v2_card("🎁 Rewards List", rewards_list))

    # ====================== LEADERBOARD ======================

    @count.command()
    async def leaderboard(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        stats = s["stats"]
        
        if not stats:
            await ctx.reply(view=v2_card("📭 Leaderboard", "No counting data yet"))
            return
        
        sorted_stats = sorted(stats.items(), key=lambda x: x[1].get("correct", 0), reverse=True)
        top_10 = []
        
        for i, (user_id, data) in enumerate(sorted_stats[:10], 1):
            top_10.append(f"{i}. <@{user_id}> — **{data.get('correct', 0)}** correct")
        
        body = "\n".join(top_10)
        await ctx.reply(view=v2_card("🏆 Top Counters", body))

    # ====================== LOGS ======================

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx: commands.Context) -> None:
        s = self.get_server(ctx.guild)
        if not s["logs"]:
            await ctx.reply(view=v2_card("📭 Logs", "No logs yet"))
            return
        
        recent_logs = "\n".join(s["logs"][-10:])
        await ctx.reply(view=v2_card("🗂 Last 10 Actions", recent_logs))

    # ====================== FIX ======================

    @count.command()
    @commands.has_permissions(manage_guild=True)
    async def fix(self, ctx: commands.Context, number: int) -> None:
        s = self.get_server(ctx.guild)
        s["current"] = number
        save_data(self.data)
        await ctx.reply(view=v2_card("🔧 Fixed", f"Count fixed to **{number}**"))

    # ====================== COUNTING LISTENER ======================

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message) -> None:
        if msg.author.bot or not msg.guild:
            return

        s = self.get_server(msg.guild)
        if not s["enabled"] or s["channel"] != msg.channel.id:
            return

        try:
            num = int(msg.content)
        except ValueError:
            await msg.delete()
            return

        if s["last_user"] == msg.author.id:
            await msg.delete()
            return

        if num == s["current"]:
            # Correct count
            s["current"] += 1
            s["last_user"] = msg.author.id
            
            # Update stats
            stats = s["stats"].setdefault(str(msg.author.id), {"correct": 0})
            stats["correct"] += 1
            
            # Highscore
            if num > s["highscore"]:
                s["highscore"] = num
            
            # Rewards
            for r in s["rewards"]:
                if r["number"] == num:
                    role = msg.guild.get_role(r["role"])
                    if role:
                        try:
                            await msg.author.add_roles(role)
                        except discord.Forbidden:
                            pass
            
            s["logs"].append(f"{EMOJI_TICK} {msg.author} counted {num}")
            save_data(self.data)
            return

        # Wrong number
        await msg.delete()
        s["logs"].append(f"{EMOJI_CROSS} {msg.author} failed with {num}")
        s["current"] = 1
        s["last_user"] = None
        save_data(self.data)
        
        await msg.channel.send(
            view=v2_card("❌ Count Ruined", f"{msg.author.mention} ruined it at **{num}**!\nRestarting from **1**.")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Counting(bot))
