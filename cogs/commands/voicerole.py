import discord

from discord.ext import commands

import json

import os

DATA_FILE = "data/voicerole_data.json"

def load_data():

    if not os.path.exists(DATA_FILE):

        with open(DATA_FILE, "w") as f:

            json.dump({}, f, indent=4)

    with open(DATA_FILE, "r") as f:

        return json.load(f)

def save_data(data):

    with open(DATA_FILE, "w") as f:

        json.dump(data, f, indent=4)

class VoiceRole(commands.Cog):

    """

    VoiceRole System (Flury Style, Prefix Commands)

    """

    def __init__(self, bot):

        self.bot = bot

        self.data = load_data()

    # ======================================================

    # Helpers

    # ======================================================

    def get_server(self, guild: discord.Guild):

        gid = str(guild.id)

        if gid not in self.data:

            self.data[gid] = {

                "bot_roles": [],

                "human_roles": []

            }

            save_data(self.data)

        return self.data[gid]

    # ======================================================

    # PREFIX COMMANDS

    # ======================================================

    @commands.group()

    async def voicerole(self, ctx):

        if ctx.invoked_subcommand is None:

            await ctx.send("🔊 Usage: $voicerole <bot/human/...>")

    # ---------------- BOT ROLES -------------------

    @voicerole.group()

    async def bot(self, ctx):

        if ctx.invoked_subcommand is None:

            await ctx.send("🔧 Bot Subcommands: add/remove/list/reset")

    @bot.command()

    async def add(self, ctx, role: discord.Role):

        s = self.get_server(ctx.guild)

        if role.id in s["bot_roles"]:

            return await ctx.send("⚠ This role is already in bot roles.")

        s["bot_roles"].append(role.id)

        save_data(self.data)

        await ctx.send(f"✅ Added **{role.name}** to bot voiceroles.")

    @bot.command()

    async def remove(self, ctx, role: discord.Role):

        s = self.get_server(ctx.guild)

        if role.id not in s["bot_roles"]:

            return await ctx.send("❌ This role is not in bot roles.")

        s["bot_roles"].remove(role.id)

        save_data(self.data)

        await ctx.send(f"❌ Removed **{role.name}** from bot voiceroles.")

    @bot.command()

    async def list(self, ctx):

        s = self.get_server(ctx.guild)

        if not s["bot_roles"]:

            return await ctx.send("📭 No bot voiceroles set.")

        roles = ", ".join(f"<@&{r}>" for r in s["bot_roles"])

        await ctx.send(f"🤖 **Bot VoiceRoles:**\n{roles}")

    @bot.command()

    async def reset(self, ctx):

        s = self.get_server(ctx.guild)

        s["bot_roles"] = []

        save_data(self.data)

        await ctx.send("♻ Reset bot voiceroles.")

    # ---------------- HUMAN ROLES -------------------

    @voicerole.group()

    async def human(self, ctx):

        if ctx.invoked_subcommand is None:

            await ctx.send("👤 Human Subcommands: add/remove/list/reset")

    @human.command()

    async def add(self, ctx, role: discord.Role):

        s = self.get_server(ctx.guild)

        if role.id in s["human_roles"]:

            return await ctx.send("⚠ This role is already in human roles.")

        s["human_roles"].append(role.id)

        save_data(self.data)

        await ctx.send(f"✅ Added **{role.name}** to human voiceroles.")

    @human.command()

    async def remove(self, ctx, role: discord.Role):

        s = self.get_server(ctx.guild)

        if role.id not in s["human_roles"]:

            return await ctx.send("❌ This role is not in human roles.")

        s["human_roles"].remove(role.id)

        save_data(self.data)

        await ctx.send(f"❌ Removed **{role.name}** from human voiceroles.")

    @human.command()

    async def list(self, ctx):

        s = self.get_server(ctx.guild)

        if not s["human_roles"]:

            return await ctx.send("📭 No human voiceroles set.")

        roles = ", ".join(f"<@&{r}>" for r in s["human_roles"])

        await ctx.send(f"👤 **Human VoiceRoles:**\n{roles}")

    @human.command()

    async def reset(self, ctx):

        s = self.get_server(ctx.guild)

        s["human_roles"] = []

        save_data(self.data)

        await ctx.send("♻ Reset human voiceroles.")

    # ======================================================

    # VC role handling (auto assign)

    # ======================================================

    @commands.Cog.listener()

    async def on_voice_state_update(self, member, before, after):

        # Ignore bots (handled separately)

        if member.bot:

            pass

        s = self.get_server(member.guild)

        bot_roles = s["bot_roles"]

        human_roles = s["human_roles"]

        # User JOINED a voice channel

        if before.channel is None and after.channel is not None:

            # Apply bot roles

            if member.bot:

                for r in bot_roles:

                    role = member.guild.get_role(r)

                    if role:

                        try:

                            await member.add_roles(role)

                        except:

                            pass

                return

            # Apply human roles

            for r in human_roles:

                role = member.guild.get_role(r)

                if role:

                    try:

                        await member.add_roles(role)

                    except:

                        pass

        # User LEFT a voice channel

        if before.channel is not None and after.channel is None:

            # Remove bot roles

            if member.bot:

                for r in bot_roles:

                    role = member.guild.get_role(r)

                    if role:

                        try:

                            await member.remove_roles(role)

                        except:

                            pass

                return

            # Remove human roles

            for r in human_roles:

                role = member.guild.get_role(r)

                if role:

                    try:

                        await member.remove_roles(role)

                    except:

                        pass

async def setup(bot):

    await bot.add_cog(VoiceRole(bot))