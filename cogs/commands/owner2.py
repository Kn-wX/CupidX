import discord
from utils.detectfile import *
from discord.ext import commands
from discord.ui import Button, View
from discord import Member
from utils import Paginator, DescriptionEmbedPaginator
from datetime import timedelta
import asyncio

# ─────────────────────────────────────────────
#  EMOJI CONSTANTS
# ─────────────────────────────────────────────

EMOJI_TICK  = "<:CupidXtick1:1474369967271968949>"
EMOJI_CROSS = "<:CupidXCross:1473996646873436336>"
EMOJI_WARN  = "<:CupidXWarning:1474348304186867784>"
EMOJI_DOT   = "<a:CupidXdot:1473986328126558209>"

NO_PING = discord.AllowedMentions.none()

# ─────────────────────────────────────────────
#  REUSABLE VIEWS (fixes Interaction Failed)
# ─────────────────────────────────────────────

class ConfirmView(View):
    """Yes / No confirmation view with proper timeout handling."""

    def __init__(self, author: discord.Member, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.author  = author
        self.value   = None  # True = confirmed, False = cancelled

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "This confirmation is not for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="✅")
    async def yes_btn(self, interaction: discord.Interaction, button: Button):
        self.value = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="❌")
    async def no_btn(self, interaction: discord.Interaction, button: Button):
        self.value = False
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        self.stop()


class ResultView(View):
    """Success / Failure list buttons shown after a global action."""

    def __init__(self, author: discord.Member, ctx, success: list, failure: list,
                 action: str, extra_stop_user_id: int = None):
        super().__init__(timeout=60.0)
        self.author            = author
        self.ctx               = ctx
        self.success           = success
        self.failure           = failure
        self.action            = action
        self.extra_stop_uid    = extra_stop_user_id

        if extra_stop_user_id:
            stop_btn = Button(label="Stop Freezing", style=discord.ButtonStyle.danger, emoji="🛑")
            stop_btn.callback = self._stop_freeze
            self.add_item(stop_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Successful", style=discord.ButtonStyle.green, emoji="✅")
    async def list_success(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        entries = [f"{i+1}. {name}" for i, name in enumerate(self.success)]
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries, description="",
                title=f"Successful {self.action} [{len(self.success)}]",
                color=0x134E5E, per_page=10
            ),
            ctx=self.ctx
        )
        await paginator.paginate()

    @discord.ui.button(label="Failed", style=discord.ButtonStyle.red, emoji="❌")
    async def list_failure(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        entries = [f"{i+1}. {name}" for i, name in enumerate(self.failure)]
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries, description="",
                title=f"Failed {self.action} [{len(self.failure)}]",
                color=0x134E5E, per_page=10
            ),
            ctx=self.ctx
        )
        await paginator.paginate()

    async def _stop_freeze(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if hasattr(interaction.client, "frozen_nicknames"):
            interaction.client.frozen_nicknames.pop(self.extra_stop_uid, None)
        await interaction.followup.send(
            f"{EMOJI_TICK} Nickname freezing stopped.", ephemeral=True
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        self.stop()


# ─────────────────────────────────────────────
#  EMBED BUILDERS
# ─────────────────────────────────────────────

def confirm_embed(title: str, user: discord.User, mutual_count: int,
                  requestor: discord.Member) -> discord.Embed:
    e = discord.Embed(title=title, color=0x134E5E)
    e.add_field(name="Target",      value=f"{user.mention} (`{user.id}`)", inline=True)
    e.add_field(name="Mutual Servers", value=f"**{mutual_count}**",         inline=True)
    e.add_field(name="Requested by", value=requestor.mention,               inline=False)
    e.set_thumbnail(url=user.display_avatar.url)
    e.set_footer(text="cupidx HQ • Reply within 30s or it will expire.")
    return e


def result_embed(action: str, user: discord.User,
                 success: list, failure: list, mutual_count: int) -> discord.Embed:
    e = discord.Embed(
        title=f"{EMOJI_TICK}  {action} — Complete",
        color=0x134E5E
    )
    e.add_field(name="Target",    value=f"{user.mention} (`{user.id}`)", inline=False)
    e.add_field(name=f"{EMOJI_TICK} Success", value=f"`{len(success)}` / `{mutual_count}` servers", inline=True)
    e.add_field(name=f"{EMOJI_CROSS} Failed",  value=f"`{len(failure)}` servers",                    inline=True)
    e.set_thumbnail(url=user.display_avatar.url)
    e.set_footer(text="cupidx HQ")
    return e


# ─────────────────────────────────────────────
#  COG
# ─────────────────────────────────────────────

class Global(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.local_frozen_nicks  = {}
        self.client.frozen_nicknames = {}

    # ── Help ───────────────────────────────────

    @commands.group(name="global", invoke_without_command=True)
    @commands.is_owner()
    async def global_command(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            embed = discord.Embed(
                title="🌐  Global Administration",
                description="Powerhouse commands for bot-wide user management.",
                color=0x134E5E
            )
            embed.set_author(name="CupidX Help Center",
                             icon_url=self.client.user.display_avatar.url)
            sub_cmds = (
                f"{EMOJI_DOT} `{ctx.prefix}global ban <user>` – Global ban\n"
                f"{EMOJI_DOT} `{ctx.prefix}global kick <user>` – Global kick\n"
                f"{EMOJI_DOT} `{ctx.prefix}global timeout <user>` – Global timeout (28d)\n"
                f"{EMOJI_DOT} `{ctx.prefix}global nick <user> <name>` – Set global nickname\n"
                f"{EMOJI_DOT} `{ctx.prefix}global clearnick <user>` – Clear global nickname\n"
                f"{EMOJI_DOT} `{ctx.prefix}global freezenick <user> <name>` – Freeze nickname\n"
                f"{EMOJI_DOT} `{ctx.prefix}global unfreezenick <user>` – Unfreeze nickname"
            )
            embed.add_field(name="Subcommands", value=sub_cmds, inline=False)
            embed.set_footer(text="cupidx HQ • cupidx",
                             icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed, allowed_mentions=NO_PING)
            ctx.command.reset_cooldown(ctx)

    # ── Global Ban ─────────────────────────────

    @commands.command(name="GB", help="Bans the user from all mutual guilds.")
    @commands.is_owner()
    async def global_ban(self, ctx: commands.Context, user: discord.User,
                         reason: str = "Severe violations of Discord's terms of service."):
        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        msg  = await ctx.reply(
            embed=confirm_embed(f"⚠️  Global Ban — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        await ctx.send(f"{EMOJI_DOT} Processing global ban for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        for guild in mutual_guilds:
            try:
                await guild.ban(user, reason=reason)
                success.append(guild.name)
            except Exception:
                failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Ban", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Bans"),
            allowed_mentions=NO_PING
        )

    # ── Global Kick ────────────────────────────

    @global_command.command(name="kick", help="Kicks the user from all mutual guilds.")
    @commands.is_owner()
    async def global_kick(self, ctx: commands.Context, user: discord.User,
                          reason: str = "Severe violations of Discord's terms of service."):
        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        await ctx.reply(
            embed=confirm_embed(f"⚠️  Global Kick — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        await ctx.send(f"{EMOJI_DOT} Processing global kick for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        for guild in mutual_guilds:
            try:
                await guild.kick(user, reason=reason)
                success.append(guild.name)
            except Exception:
                failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Kick", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Kicks"),
            allowed_mentions=NO_PING
        )

    # ── Global Timeout ─────────────────────────

    @global_command.command(name="timeout",
                            help="Timeouts the user for 28 days in all mutual guilds.")
    @commands.is_owner()
    async def global_timeout(self, ctx: commands.Context, user: discord.User,
                             reason: str = "Severe violations of Discord's terms of service."):
        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        await ctx.reply(
            embed=confirm_embed(f"⚠️  Global Timeout (28d) — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        await ctx.send(f"{EMOJI_DOT} Processing global timeout for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        delta = timedelta(days=28)
        for guild in mutual_guilds:
            member = guild.get_member(user.id)
            if member:
                try:
                    await member.edit(
                        timed_out_until=discord.utils.utcnow() + delta,
                        reason=reason
                    )
                    success.append(guild.name)
                except Exception:
                    failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Timeout", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Timeouts"),
            allowed_mentions=NO_PING
        )

    # ── Global Nick ────────────────────────────

    @global_command.command(name="nick",
                            help="Changes the nickname of a user in all mutual guilds.")
    @commands.is_owner()
    async def global_nick(self, ctx: commands.Context, user: discord.User, *, name: str):
        if len(name) > 32:
            return await ctx.reply(
                f"{EMOJI_WARN} Nickname cannot exceed **32 characters**.",
                allowed_mentions=NO_PING
            )

        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        await ctx.reply(
            embed=confirm_embed(f"⚠️  Global Nick Change — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        await ctx.send(f"{EMOJI_DOT} Processing global nickname change for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        for guild in mutual_guilds:
            try:
                member = guild.get_member(user.id)
                if member:
                    await member.edit(nick=name)
                    success.append(guild.name)
            except Exception:
                failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Nick", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Nick Changes"),
            allowed_mentions=NO_PING
        )

    # ── Global Clearnick ───────────────────────

    @global_command.command(name="clearnick",
                            help="Clears the nickname of a user in all mutual guilds.")
    @commands.is_owner()
    async def global_clearnick(self, ctx: commands.Context, user: discord.User):
        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        await ctx.reply(
            embed=confirm_embed(f"⚠️  Global Clear Nick — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        await ctx.send(f"{EMOJI_DOT} Clearing global nickname for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        for guild in mutual_guilds:
            try:
                member = guild.get_member(user.id)
                if member:
                    await member.edit(nick=None)
                    success.append(guild.name)
            except Exception:
                failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Clearnick", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Nick Clears"),
            allowed_mentions=NO_PING
        )

    # ── Global Freezenick ──────────────────────

    @global_command.command(name="freezenick",
                            help="Freezes a user's nickname in all mutual guilds.")
    @commands.is_owner()
    async def global_freezenick(self, ctx: commands.Context,
                                user: discord.User, *, name: str):
        if len(name) > 32:
            return await ctx.reply(
                f"{EMOJI_WARN} Nickname cannot exceed **32 characters**.",
                allowed_mentions=NO_PING
            )

        if not hasattr(self.client, "frozen_nicknames"):
            self.client.frozen_nicknames = {}

        mutual_guilds = [g for g in self.client.guilds if g.get_member(user.id)]
        mutual_count  = len(mutual_guilds)

        view = ConfirmView(ctx.author)
        await ctx.reply(
            embed=confirm_embed(f"⚠️  Freeze Nick — {user.display_name}?",
                                user, mutual_count, ctx.author),
            view=view,
            allowed_mentions=NO_PING
        )
        await view.wait()

        if not view.value:
            return

        self.client.frozen_nicknames[user.id] = {
            "name":      name,
            "guild_ids": [g.id for g in mutual_guilds],
        }

        await ctx.send(f"{EMOJI_DOT} Freezing nickname for **{user.name}**…",
                       allowed_mentions=NO_PING)
        success, failure = [], []
        for guild in mutual_guilds:
            try:
                member = guild.get_member(user.id)
                if member:
                    await member.edit(nick=name)
                    success.append(guild.name)
            except Exception:
                failure.append(guild.name)

        await ctx.send(
            embed=result_embed("Global Freezenick", user, success, failure, mutual_count),
            view=ResultView(ctx.author, ctx, success, failure, "Nick Freezes",
                            extra_stop_user_id=user.id),
            allowed_mentions=NO_PING
        )
        self.client.loop.create_task(self.nickname_freeze_task(user.id))

    # ── Freeze task ────────────────────────────

    async def nickname_freeze_task(self, user_id: int):
        while user_id in self.client.frozen_nicknames:
            user_data    = self.client.frozen_nicknames[user_id]
            frozen_name  = user_data["name"]
            guild_ids    = user_data["guild_ids"]
            for guild_id in guild_ids:
                guild = self.client.get_guild(guild_id)
                if not guild:
                    continue
                member = guild.get_member(user_id)
                if member and member.nick != frozen_name:
                    try:
                        await member.edit(nick=frozen_name)
                    except Exception:
                        pass
            await asyncio.sleep(10)

    # ── Global Unfreezenick ────────────────────

    @global_command.command(name="unfreezenick",
                            help="Unfreezes a user's nickname in all mutual guilds.")
    @commands.is_owner()
    async def global_unfreezenick(self, ctx: commands.Context, user: discord.User):
        if not hasattr(self.client, "frozen_nicknames"):
            self.client.frozen_nicknames = {}

        if user.id not in self.client.frozen_nicknames:
            return await ctx.reply(
                f"{EMOJI_CROSS} **{user.name}**'s nickname is not being frozen.",
                allowed_mentions=NO_PING
            )

        del self.client.frozen_nicknames[user.id]
        await ctx.reply(
            f"{EMOJI_TICK} Nickname freezing stopped for **{user.name}**.",
            allowed_mentions=NO_PING
        )

    # ── Local Freezenick ───────────────────────

    @commands.command(name="freezenick",
                      help="Freezes a member's nickname in the current server.")
    @commands.has_permissions(manage_nicknames=True)
    async def freeze_nickname(self, ctx: commands.Context,
                              member: Member, *, nickname: str):
        guild_id = ctx.guild.id
        if guild_id not in self.local_frozen_nicks:
            self.local_frozen_nicks[guild_id] = {}

        if member.id in self.local_frozen_nicks[guild_id]:
            return await ctx.reply(
                f"{EMOJI_WARN} {member.mention}'s nickname is already being frozen.",
                allowed_mentions=NO_PING
            )

        try:
            await member.edit(nick=nickname)
            self.local_frozen_nicks[guild_id][member.id] = nickname
            await ctx.reply(
                f"{EMOJI_TICK} Freezing {member.mention}'s nickname as `{nickname}`.",
                allowed_mentions=NO_PING
            )
        except Exception:
            return await ctx.reply(
                f"{EMOJI_CROSS} Could not change {member.mention}'s nickname — insufficient permissions.",
                allowed_mentions=NO_PING
            )

        async def monitor_nickname():
            while member.id in self.local_frozen_nicks.get(guild_id, {}):
                if member.nick != nickname:
                    try:
                        await member.edit(nick=nickname)
                    except Exception:
                        self.local_frozen_nicks[guild_id].pop(member.id, None)
                        await ctx.send(
                            f"{EMOJI_WARN} Stopped monitoring {member.mention}'s nickname — lost permissions.",
                            allowed_mentions=NO_PING
                        )
                        break
                await asyncio.sleep(10)
            if guild_id in self.local_frozen_nicks and not self.local_frozen_nicks[guild_id]:
                del self.local_frozen_nicks[guild_id]

        self.client.loop.create_task(monitor_nickname())

    # ── Local Unfreezenick ─────────────────────

    @commands.command(name="unfreezenick",
                      help="Unfreezes a member's nickname in the current server.")
    @commands.has_permissions(manage_nicknames=True)
    async def unfreeze_nickname(self, ctx: commands.Context, member: Member):
        guild_id = ctx.guild.id
        if guild_id in self.local_frozen_nicks and \
                member.id in self.local_frozen_nicks[guild_id]:
            self.local_frozen_nicks[guild_id].pop(member.id, None)
            if not self.local_frozen_nicks[guild_id]:
                del self.local_frozen_nicks[guild_id]
            await ctx.reply(
                f"{EMOJI_TICK} Stopped freezing {member.mention}'s nickname.",
                allowed_mentions=NO_PING
            )
        else:
            await ctx.reply(
                f"{EMOJI_CROSS} {member.mention}'s nickname is not currently being frozen.",
                allowed_mentions=NO_PING
            )


async def setup(client):
    await client.add_cog(Global(client))
