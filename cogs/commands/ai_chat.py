import os
import json
import aiohttp
import asyncio
import datetime
import discord
from discord.ext import commands
from dotenv import load_dotenv
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
CONFIG_FILE = "ai_config.json"
MEMORY_FILE = "ai_memory.json"
ERROR_FILE = "ai_errors.log"
LOG_FILE = "ai_logs.json"

def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"## {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    view.add_item(container)
    return view

# --------------------------
# JSON UTILS
# --------------------------

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf8") as f:
            json.dump(default, f, indent=4)
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, indent=4)

# --------------------------
# MEMORY SYSTEM
# --------------------------

class Memory:
    def __init__(self):
        self.data = load_json(MEMORY_FILE, {"users": {}, "global": []})
        if "users" not in self.data:
            self.data["users"] = {}
        if "global" not in self.data:
            self.data["global"] = []

    def add(self, uid, msg, reply):
        now = datetime.datetime.utcnow().isoformat()
        entry = {"time": now, "user": msg, "bot": reply}
        if str(uid) not in self.data["users"]:
            self.data["users"][str(uid)] = []
        self.data["users"][str(uid)].append(entry)
        self.data["users"][str(uid)] = self.data["users"][str(uid)][-20:]
        self.data["global"].append(entry)
        self.data["global"] = self.data["global"][-40:]
        save_json(MEMORY_FILE, self.data)

    def get(self, uid):
        u = self.data.get("users", {}).get(str(uid), [])[-5:]
        g = self.data.get("global", [])[-5:]
        def fmt(arr):
            return "\n".join([f"User: {i['user']}\nBot: {i['bot']}" for i in arr])
        return f"--- USER ---\n{fmt(u)}\n\n--- GLOBAL ---\n{fmt(g)}"

# --------------------------
# MAIN COG
# --------------------------

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.memory = Memory()
        self.config = load_json(CONFIG_FILE, {
            "enabled": True,
            "premium": False,
            "auto_channels": [],
            "dm_chat": False,
            "model": "x-ai/grok-4.1-fast:free",
            "stats": {
                "messages": 0,
                "tokens": 0,
                "started": datetime.datetime.utcnow().isoformat()
            }
        })
        # MODEL LIST
        self.models = [
            # FREE
            "mistralai/mistral-small-24b-instruct-2501:free",
            "qwen/qwen3-8b:free",
            "google/gemma-2-9b-it:free",
            "deepseek/deepseek-r1-0528:free",
            # PREMIUM
            "meta-llama/llama-3-70b-instruct",
            "meta-llama/llama-3-8b-instruct",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1",
            "qwen/qwen3-72b-instruct",
            "mistralai/mistral-large",
            "mistralai/mistral-medium",
            "x-ai/grok-beta",
            # EXTRA
            "google/gemini-1.5-flash",
            "google/gemini-1.5-pro",
        ]

    # --------------------------
    # API CALL
    # --------------------------

    async def ask(self, user_id, prompt):
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.config["model"],
            "messages": [
                {"role": "system", "content": "You are an advanced AI assistant."},
                {"role": "system", "content": "Memory:\n" + self.memory.get(user_id)},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 650
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(BASE_URL, json=payload, headers=headers, timeout=20) as r:
                    text = await r.text()
                    try:
                        data = json.loads(text)
                    except:
                        self.log_error(f"Non JSON: {text}")
                        return "API Error (non JSON)."
                    if "error" in data:
                        self.log_error(str(data))
                        return f"API Error: {data['error']}"
                    if "choices" not in data:
                        self.log_error(f"Invalid: {text}")
                        return "API Error: No choices returned."
                    reply = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    self.config["stats"]["messages"] += 1
                    self.config["stats"]["tokens"] += tokens
                    save_json(CONFIG_FILE, self.config)
                    self.memory.add(user_id, prompt, reply)
                    return reply
        except Exception as e:
            self.log_error(str(e))
            return f"API Error: {e}"

    def log_error(self, txt):
        with open(ERROR_FILE, "a", encoding="utf8") as f:
            f.write(f"[{datetime.datetime.utcnow().isoformat()}] {txt}\n")

    # --------------------------
    # CHAT COMMAND
    # --------------------------

    @commands.command()
    async def chat(self, ctx, *, text: str):
        if not self.config["enabled"]:
            card = v2_card("Error", "AI is disabled.")
            return await ctx.send(view=card)
        thinking_card = v2_card("Info", "Thinking...")
        await ctx.send(view=thinking_card)
        reply = await self.ask(ctx.author.id, text)
        reply_card = v2_card("AI Response", reply[:1900])
        await ctx.send(view=reply_card)

    # --------------------------
    # AUTO CHAT
    # --------------------------

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        # Auto Channels
        if msg.channel.id in self.config["auto_channels"]:
            if msg.content.startswith(("$", "!", "/", ".", "-")):
                return
            ctx = await self.bot.get_context(msg)
            if ctx.valid:
                return
            reply = await self.ask(msg.author.id, msg.content)
            card = v2_card("AI Response", reply[:1900])
            return await msg.channel.send(view=card)
        # DM Chat
        if isinstance(msg.channel, discord.DMChannel) and self.config["dm_chat"]:
            reply = await self.ask(msg.author.id, msg.content)
            card = v2_card("AI Response", reply[:1900])
            return await msg.channel.send(view=card)

    # --------------------------
    # MAIN AI GROUP
    # --------------------------

    @commands.group()
    async def ai(self, ctx):
        if not ctx.invoked_subcommand:
            card = v2_card("AI Commands", "model, auto, dm, memory, stats, logs, errors, toggle")
            await ctx.send(view=card)

    # --------------------------
    # TOGGLE AI
    # --------------------------

    @ai.command()
    async def toggle(self, ctx):
        self.config["enabled"] = not self.config["enabled"]
        save_json(CONFIG_FILE, self.config)
        card = v2_card("Toggle AI", f"AI Enabled: {self.config['enabled']}")
        await ctx.send(view=card)

    # --------------------------
    # MODEL SYSTEM
    # --------------------------

    @ai.group()
    async def model(self, ctx):
        if not ctx.invoked_subcommand:
            card = v2_card("Model Commands", "Subcommands: list, set, current")
            await ctx.send(view=card)

    @model.command()
    async def list(self, ctx):
        # Format models list with bullet points for clarity
        models_text = "\n".join(f"- {m}" for m in self.models)
        card = v2_card("Available Models", models_text)
        await ctx.send(view=card)

    @model.command()
    async def set(self, ctx, *, name: str):
        if name not in self.models:
            card = v2_card("Error", "Model not found.")
            return await ctx.send(view=card)
        self.config["model"] = name
        save_json(CONFIG_FILE, self.config)
        card = v2_card("Model Set", f"Model set to `{name}`")
        await ctx.send(view=card)

    @model.command()
    async def current(self, ctx):
        card = v2_card("Current Model", f"Current model: `{self.config['model']}`")
        await ctx.send(view=card)

    # --------------------------
    # AUTO CHAT CHANNEL CONTROL
    # --------------------------

    @ai.group()
    async def auto(self, ctx):
        if not ctx.invoked_subcommand:
            card = v2_card("Auto Commands", "Subcommands: add, remove, list")
            await ctx.send(view=card)

    @auto.command()
    async def add(self, ctx, ch: discord.TextChannel):
        if ch.id in self.config["auto_channels"]:
            card = v2_card("Error", "Already added.")
            return await ctx.send(view=card)
        self.config["auto_channels"].append(ch.id)
        save_json(CONFIG_FILE, self.config)
        card = v2_card("Auto Chat Added", f"Auto chat added to {ch.mention}")
        await ctx.send(view=card)

    @auto.command()
    async def remove(self, ctx, ch: discord.TextChannel):
        if ch.id not in self.config["auto_channels"]:
            card = v2_card("Error", "Not found.")
            return await ctx.send(view=card)
        self.config["auto_channels"].remove(ch.id)
        save_json(CONFIG_FILE, self.config)
        card = v2_card("Auto Chat Removed", f"Removed from {ch.mention}")
        await ctx.send(view=card)

    @auto.command()
    async def list(self, ctx):
        if not self.config["auto_channels"]:
            card = v2_card("No Channels", "No auto-chat channels.")
            await ctx.send(view=card)
            return
        channel_mentions = ", ".join(f"<#{i}>" for i in self.config["auto_channels"])
        card = v2_card("Auto Chat Channels", channel_mentions)
        await ctx.send(view=card)

    # --------------------------
    # DM CHAT
    # --------------------------

    @ai.group()
    async def dm(self, ctx):
        if not ctx.invoked_subcommand:
            card = v2_card("DM Commands", "Subcommands: toggle")
            await ctx.send(view=card)

    @dm.command()
    async def toggle(self, ctx):
        self.config["dm_chat"] = not self.config["dm_chat"]
        save_json(CONFIG_FILE, self.config)
        card = v2_card("DM Chat", f"DM Chat: {self.config['dm_chat']}")
        await ctx.send(view=card)

    # --------------------------
    # MEMORY SYSTEM
    # --------------------------

    @ai.group()
    async def memory(self, ctx):
        if not ctx.invoked_subcommand:
            card = v2_card("Memory Commands", "Subcommands: show @user, clear, clear @user")
            await ctx.send(view=card)

    @memory.command(name="show")
    async def memory_show(self, ctx, user: discord.Member):
        m = self.memory.get(user.id)
        content = m if len(m) <= 1800 else m[:1800] + "\n...[truncated]"
        card = v2_card(f"Memory for {user.display_name}", f"``````")
        await ctx.send(view=card)

    @memory.command(name="clear")
    async def memory_clear(self, ctx, user: discord.Member = None):
        data = load_json(MEMORY_FILE, {"users": {}, "global": []})
        if user is None:
            data["users"] = {}
            data["global"] = []
            save_json(MEMORY_FILE, data)
            self.memory = Memory()
            card = v2_card("Memory Cleared", "All memory cleared.")
            return await ctx.send(view=card)
        uid = str(user.id)
        if uid not in data["users"]:
            card = v2_card("Error", "User has no memory.")
            return await ctx.send(view=card)
        data["users"][uid] = []
        save_json(MEMORY_FILE, data)
        self.memory.data = data
        card = v2_card("Memory Cleared", f"Memory cleared for {user.mention}.")
        await ctx.send(view=card)

    # --------------------------
    # STATS
    # --------------------------

    @ai.command()
    async def stats(self, ctx):
        s = self.config["stats"]
        card = v2_card(
            "Stats",
            f"Messages: {s['messages']}\nTokens: {s['tokens']}\nStarted: {s['started']}"
        )
        await ctx.send(view=card)

    # --------------------------
    # ERRORS
    # --------------------------

    @ai.command()
    async def errors(self, ctx):
        if not os.path.exists(ERROR_FILE):
            card = v2_card("Errors", "No errors logged.")
            return await ctx.send(view=card)
        with open(ERROR_FILE, "r", encoding="utf8") as f:
            e = f.read()
        card = v2_card("Errors", f"``````")
        await ctx.send(view=card)

    # --------------------------
    # LOGS
    # --------------------------

    @ai.command()
    async def logs(self, ctx):
        if not os.path.exists(LOG_FILE):
            card = v2_card("Logs", "No logs.")
            return await ctx.send(view=card)
        with open(LOG_FILE, "r", encoding="utf8") as f:
            l = f.read()
        card = v2_card("Logs", f"Logs length: {len(l)} chars")
        await ctx.send(view=card)

# ------------------------------
# SETUP
# ------------------------------

async def setup(bot):
    await bot.add_cog(AIChat(bot))
