from __future__ import annotations
import asyncio
import datetime
import time
import io
import math
import random
from typing import Optional, Union, Callable, List

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import Context
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils.Tools import blacklist_check, ignore_check
from utils.detectfile import *
from discord.ui import (
    LayoutView, Container, TextDisplay, Separator, Button,
    View
)

# ══════════════════════════════════════════════
#   EMOJIS
# ══════════════════════════════════════════════
E = {
    "tick":     EMOJI_TICK,
    "cross":    EMOJI_CROSS,
    "warn":     EMOJI_FIRE,
    "dot":      EMOJI_DOT2,
    "arrow":    EMOJI_ARROW,
    "shield":   EMOJI_SHIELD,
    "crown":    EMOJI_CROWN,
    "star":     EMOJI_STARS,
    "fire":     EMOJI_FIRE,
    "bot":      EMOJI_ROBOT,
    "user":     EMOJI_USER,
    "link":     EMOJI_BOND2,
    "timer":    EMOJI_TIMER2,
    "loading":  EMOJI_LOADING,
    "settings": "<:cog:1487152125069889677>",
    "premium":  EMOJI_DIAMOND,
    "members":  EMOJI_PROFILE,
    "channel":  EMOJI_APP2,
    "role":     EMOJI_ROLE,
    "boost":    EMOJI_ANNOUNCE,
    "lock":     EMOJI_KEY,
    "home":     EMOJI_UTILITY4B,
    "stats":    EMOJI_SYSTEM,
    "uptime":   EMOJI_TELESCOPE2,
    "github":   EMOJI_ROBOT2,
    "image":    EMOJI_STAR2,
    "add":      EMOJI_ADD,
}

start_time = time.time()


# ══════════════════════════════════════════════
#   BASE V2 CARD
# ══════════════════════════════════════════════
def v2_card(title: str, body: str) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view


# ══════════════════════════════════════════════
#   PAGINATED LIST VIEW
# ══════════════════════════════════════════════
class ListView(discord.ui.View):
    def __init__(self, pages: List[str], *, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        self.prev_button.disabled = True
        if len(self.pages) <= 1:
            self.next_button.disabled = True

    def _get_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            description=self.pages[self.current_page],
            color=0x000000
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        return embed

    def _update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._get_page_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._get_page_embed(), view=self)

    @discord.ui.button(label="⏹️ Close", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="**📋 List closed**", embed=None, view=None)


# ══════════════════════════════════════════════
#   COG
# ══════════════════════════════════════════════
class Extra(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── INTERNAL HELPERS ──

    def _format_list_page(self, items: List[str], page_num: int, total_pages: int, title: str) -> str:
        start_idx  = page_num * 8
        page_items = items[start_idx:start_idx + 8]
        page_text  = f"**{title}**\n*Page {page_num + 1}/{total_pages}*\n\n"
        for i, item in enumerate(page_items, start=start_idx + 1):
            page_text += f"`{i}.` {item}\n"
        return page_text

    async def _create_paginated_list(self, ctx: Context, items: list, format_item: Callable[[object], str], title: str):
        if not items:
            embed = discord.Embed(
                description=f"{E['cross']}  No **{title.lower()}** found.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        formatted_items = [format_item(item) for item in items]
        total_pages     = (len(formatted_items) + 7) // 8
        pages           = [
            self._format_list_page(formatted_items, p, total_pages, title)
            for p in range(total_pages)
        ]
        view = ListView(pages)
        await ctx.reply(embed=view._get_page_embed(), view=view)

    # ══════════════════════════════
    #   BANNER
    # ══════════════════════════════
    @commands.group(name="banner", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def banner(self, ctx: Context):
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(
            title=f"{E['image']}  Banner Commands",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['arrow']}  Subcommands",
            value=(
                f"{E['dot']} `banner server` — Server banner preview\n"
                f"{E['dot']} `banner user [user]` — User profile banner"
            ),
            inline=False
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @banner.command(name="server")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def banner_server(self, ctx: Context):
        if not ctx.guild.banner:
            embed = discord.Embed(
                description=f"{E['cross']}  **{ctx.guild.name}** has no custom banner set.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        banner = ctx.guild.banner
        embed = discord.Embed(
            title=f"{E['image']}  Server Banner — {ctx.guild.name}",
            color=0x000000
        )
        embed.set_image(url=banner.url)
        embed.add_field(
            name=f"{E['link']}  Download",
            value=(
                f"[PNG]({banner.with_format('png').url})  •  "
                f"[JPG]({banner.with_format('jpg').url})  •  "
                f"[WEBP]({banner.with_format('webp').url})"
            ),
            inline=False
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=banner.with_format('png').url))
        view.add_item(discord.ui.Button(label="JPG", style=discord.ButtonStyle.link, url=banner.with_format('jpg').url))
        view.add_item(discord.ui.Button(label="WEBP", style=discord.ButtonStyle.link, url=banner.with_format('webp').url))
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, view=view)

    @banner.command(name="user")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    async def banner_user(self, ctx: Context, member: Optional[Union[discord.Member, discord.User]] = None):
        member = member or ctx.author
        try:
            user = await self.bot.fetch_user(member.id)
        except Exception:
            embed = discord.Embed(description=f"{E['cross']}  Failed to fetch user profile.", color=0x000000)
            return await ctx.reply(embed=embed)

        if not user.banner:
            embed = discord.Embed(
                description=f"{E['cross']}  **{member.display_name}** has no profile banner.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        embed = discord.Embed(
            title=f"{E['image']}  Banner — {member.display_name}",
            color=0x000000
        )
        embed.set_image(url=user.banner.url)
        embed.add_field(
            name=f"{E['link']}  Download",
            value=(
                f"[PNG]({user.banner.with_format('png').url})  •  "
                f"[JPG]({user.banner.with_format('jpg').url})  •  "
                f"[WEBP]({user.banner.with_format('webp').url})"
            ),
            inline=False
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="PNG", style=discord.ButtonStyle.link, url=user.banner.with_format('png').url))
        view.add_item(discord.ui.Button(label="JPG", style=discord.ButtonStyle.link, url=user.banner.with_format('jpg').url))
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   UPTIME
    # ══════════════════════════════
    @commands.command(name="uptime")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def uptime(self, ctx: Context):
        uptime_s   = int(time.time() - start_time)
        delta      = datetime.timedelta(seconds=uptime_s)
        started_ts = int(start_time)
        duration   = (
            f"{delta.days}d {delta.seconds // 3600:02}h "
            f"{delta.seconds % 3600 // 60:02}m {delta.seconds % 60:02}s"
        )
        guilds = len(self.bot.guilds)
        users  = sum(g.member_count for g in self.bot.guilds if g.member_count)
        bot_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title=f"{E['uptime']}  Bot Uptime",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['timer']}  Duration",
            value=(
                f"{E['arrow']} **Up for:** `{duration}`\n"
                f"{E['dot']} **Since:** <t:{started_ts}:F>\n"
                f"(<t:{started_ts}:R>)"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['stats']}  Live Stats",
            value=(
                f"{E['timer']} **Ping:** `{bot_ms}ms`\n"
                f"{E['members']} **Users:** `{users:,}`\n"
                f"{E['home']} **Servers:** `{guilds:,}`"
            ),
            inline=True
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   SERVER INFO
    # ══════════════════════════════
    @commands.command(name="serverinfo", aliases=["sinfo", "si"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild

        premium_status = f"{E['cross']} Not Premium"
        premium_cog    = self.bot.get_cog("Premium")
        if premium_cog:
            try:
                if await premium_cog.is_premium(guild.id):
                    premium_status = f"{E['tick']} Premium Active"
            except Exception:
                premium_status = f"{E['warn']} Error"

        total_members = guild.member_count
        bots          = len([m for m in guild.members if m.bot])
        humans        = total_members - bots
        text_ch       = len(guild.text_channels)
        voice_ch      = len(guild.voice_channels)
        created_ts    = int(guild.created_at.timestamp())

        loading = discord.Embed(
            description=f"{E['loading']}  Fetching server info...",
            color=0x000000
        )
        msg = await ctx.reply(embed=loading, mention_author=False)
        await asyncio.sleep(1)
        await msg.delete()

        embed = discord.Embed(
            title=f"{E['home']}  {guild.name}",
            description=(
                f"{E['arrow']} **Server ID:** `{guild.id}`\n"
                f"{E['timer']} **Created:** <t:{created_ts}:D> (<t:{created_ts}:R>)\n"
                f"{E['shield']} **Verification:** `{str(guild.verification_level).title()}`"
            ),
            color=0x000000
        )
        embed.add_field(
            name=f"{E['crown']}  Owner",
            value=f"{guild.owner.mention}\n`{guild.owner.id}`",
            inline=True
        )
        embed.add_field(
            name=f"{E['members']}  Members",
            value=(
                f"{E['arrow']} Total: `{total_members:,}`\n"
                f"{E['user']}  Humans: `{humans:,}`\n"
                f"{E['bot']}  Bots: `{bots:,}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['channel']}  Channels",
            value=(
                f"{E['arrow']} Total: `{len(guild.channels):,}`\n"
                f"{EMOJI_MAIL} Text: `{text_ch:,}`\n"
                f"{EMOJI_ANNOUNCE} Voice: `{voice_ch:,}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['boost']}  Boosts",
            value=(
                f"{E['star']} Count: `{guild.premium_subscription_count}`\n"
                f"{E['fire']} Tier: `{guild.premium_tier}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['stats']}  Assets",
            value=(
                f"{E['role']}  Roles: `{len(guild.roles)}`\n"
                f"{EMOJI_ADD} Emojis: `{len(guild.emojis)}`\n"
                f"{EMOJI_WARN2} Stickers: `{len(guild.stickers)}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['premium']}  Bot Premium",
            value=premium_status,
            inline=True
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        banner_url = guild.banner.url if guild.banner else BANNER_URL_ALT
        embed.set_image(url=banner_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, allowed_mentions=discord.AllowedMentions(users=False))

    # ══════════════════════════════
    #   USER INFO
    # ══════════════════════════════
    @commands.command(name="userinfo", aliases=["whois", "ui"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    async def userinfo(self, ctx: Context, member: Optional[discord.Member] = None):
        member     = member or ctx.author
        created    = f"<t:{int(member.created_at.timestamp())}:D> (<t:{int(member.created_at.timestamp())}:R>)"
        joined     = (
            f"<t:{int(member.joined_at.timestamp())}:D> (<t:{int(member.joined_at.timestamp())}:R>)"
            if member.joined_at else "N/A"
        )
        roles      = [r for r in member.roles if not r.is_default()]
        top_role   = roles[-1].mention if roles else "None"
        role_count = len(roles)

        badges = []
        if member.public_flags.early_supporter:      badges.append("👶 Early Supporter")
        if member.public_flags.hypesquad_balance:    badges.append("⚖️ HypeSquad Balance")
        if member.public_flags.hypesquad_bravery:    badges.append("🦁 HypeSquad Bravery")
        if member.public_flags.hypesquad_brilliance: badges.append("💡 HypeSquad Brilliance")
        if member.public_flags.bug_hunter:           badges.append("🐛 Bug Hunter")
        if member.public_flags.active_developer:     badges.append("💻 Active Developer")
        if member.bot:                               badges.append("🤖 Bot")
        if member.premium_since:                     badges.append("🚀 Server Booster")
        badges_str = "  ".join(badges) if badges else "None"

        status_map = {
            discord.Status.online:         "🟢 Online",
            discord.Status.idle:           "🟡 Idle",
            discord.Status.do_not_disturb: "🔴 Do Not Disturb",
            discord.Status.offline:        "⚫ Offline",
        }
        status = status_map.get(member.status, "⚫ Offline")

        embed = discord.Embed(
            title=f"{E['user']}  {member.display_name}",
            description=(
                f"{E['arrow']} **Username:** `{member.name}`\n"
                f"{E['arrow']} **ID:** `{member.id}`\n"
                f"{E['dot']} **Status:** {status}"
            ),
            color=0x000000
        )
        embed.add_field(
            name=f"{E['timer']}  Dates",
            value=f"{EMOJI_TIMER2} **Created:** {created}\n📥 **Joined:** {joined}",
            inline=False
        )
        embed.add_field(
            name=f"{E['role']}  Roles",
            value=(
                f"{E['star']} **Count:** `{role_count}`\n"
                f"{E['crown']} **Top Role:** {top_role}"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['shield']}  Badges",
            value=badges_str,
            inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   ROLE INFO
    # ══════════════════════════════
    @commands.command(name="roleinfo", aliases=["ri"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def roleinfo(self, ctx: Context, role: discord.Role):
        pos        = len(ctx.guild.roles) - role.position
        created_ts = int(role.created_at.timestamp())
        color_hex  = str(role.color) if role.color.value else "#000000"

        embed = discord.Embed(
            title=f"{E['role']}  Role Info — {role.name}",
            color=role.color if role.color.value else 0x000000,
        )
        embed.add_field(
            name=f"{E['arrow']}  General",
            value=(
                f"{E['dot']} **ID:** `{role.id}`\n"
                f"{E['dot']} **Color:** `{color_hex}`\n"
                f"{E['timer']} **Created:** <t:{created_ts}:D> (<t:{created_ts}:R>)"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['stats']}  Details",
            value=(
                f"{E['members']} **Members:** `{len(role.members)}`\n"
                f"📍 **Position:** `#{pos}`\n"
                f"{E['lock']} **Managed:** `{'Yes' if role.managed else 'No'}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['settings']}  Flags",
            value=(
                f"{EMOJI_ANNOUNCE} **Mentionable:** {E['tick'] if role.mentionable else E['cross']}\n"
                f"🏷️ **Hoisted:** {E['tick'] if role.hoist else E['cross']}\n"
                f"{E['shield']} **Integration:** {E['tick'] if role.is_integration() else E['cross']}"
            ),
            inline=True
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   BOOST COUNT
    # ══════════════════════════════
    @commands.command(name="boostcount", aliases=["bc", "boosts"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def boostcount(self, ctx: Context):
        guild    = ctx.guild
        boosts   = guild.premium_subscription_count
        tier     = guild.premium_tier
        boosters = guild.premium_subscribers

        needed      = {0: 2, 1: 7, 2: 14, 3: 0}
        next_needed = needed.get(tier, 0)
        progress    = f"`{boosts}/{next_needed}` to next tier" if next_needed else "**Max Tier Reached!** 🎉"

        embed = discord.Embed(
            title=f"{E['boost']}  Server Boosts — {guild.name}",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['star']}  Stats",
            value=(
                f"{E['fire']} **Total Boosts:** `{boosts}`\n"
                f"{E['crown']} **Boost Tier:** `{tier}`\n"
                f"{E['members']} **Boosters:** `{len(boosters)}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['arrow']}  Progress",
            value=(
                f"{E['dot']} **Next Tier:** {progress}\n"
                f"{E['tick']}  **Current Tier:** `Level {tier}`"
            ),
            inline=True
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   LIST GROUP
    # ══════════════════════════════
    @commands.group(name="list", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_group(self, ctx: Context):
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(
            title=f"{E['stats']}  List Commands",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['arrow']}  Available",
            value=(
                f"{E['dot']} `list boosters` — Active server boosters\n"
                f"{E['dot']} `list bans` — Banned users\n"
                f"{E['dot']} `list inrole <role>` — Role members\n"
                f"{E['dot']} `list emojis` — Custom emojis\n"
                f"{E['dot']} `list roles` — All roles\n"
                f"{E['dot']} `list bots` — Server bots\n"
                f"{E['dot']} `list admins` — Admin users\n"
                f"{E['dot']} `list moderators` — Mod users\n"
                f"{E['dot']} `list invoice` — VC users\n"
                f"{E['dot']} `list early` — Early supporters"
            ),
            inline=False
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @list_group.command(name="boosters")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_boosters(self, ctx: Context):
        boosters = list(ctx.guild.premium_subscribers)
        await self._create_paginated_list(
            ctx, boosters,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"🚀 Boosters ({len(boosters)} total)",
        )

    @list_group.command(name="bans")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(view_audit_log=True)
    @commands.bot_has_permissions(view_audit_log=True)
    async def list_bans(self, ctx: Context):
        bans = [b async for b in ctx.guild.bans()]
        await self._create_paginated_list(
            ctx, bans,
            lambda b: f"{b.user} (`{b.user.id}`)",
            f"🔨 Bans ({len(bans)} total)",
        )

    @list_group.command(name="inrole")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_inrole(self, ctx: Context, role: discord.Role):
        members = role.members
        await self._create_paginated_list(
            ctx, members,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"📋 {role.name} Members ({len(members)} total)",
        )

    @list_group.command(name="emojis")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_emojis(self, ctx: Context):
        emojis = ctx.guild.emojis
        await self._create_paginated_list(
            ctx, emojis,
            lambda e: f"{e} (`{e.id}`)",
            f"😀 Emojis ({len(emojis)} total)",
        )

    @list_group.command(name="roles")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_roles(self, ctx: Context):
        roles = [r for r in ctx.guild.roles if not r.is_default()]
        await self._create_paginated_list(
            ctx, roles,
            lambda r: f"{r.mention} (`{r.id}`)",
            f"📋 Roles ({len(roles)} total)",
        )

    @list_group.command(name="bots")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_bots(self, ctx: Context):
        bots = [m for m in ctx.guild.members if m.bot]
        await self._create_paginated_list(
            ctx, bots,
            lambda b: f"{b.mention} (`{b.id}`)",
            f"🤖 Bots ({len(bots)} total)",
        )

    @list_group.command(name="admins")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_admins(self, ctx: Context):
        admins = [m for m in ctx.guild.members if m.guild_permissions.administrator]
        await self._create_paginated_list(
            ctx, admins,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"👑 Admins ({len(admins)} total)",
        )

    @list_group.command(name="moderators", aliases=["mods"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_moderators(self, ctx: Context):
        mods = [
            m for m in ctx.guild.members
            if (m.guild_permissions.ban_members or m.guild_permissions.kick_members)
            and not m.bot
        ]
        await self._create_paginated_list(
            ctx, mods,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"🛡️ Moderators ({len(mods)} total)",
        )

    @list_group.command(name="invoice", aliases=["invc"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_invoice(self, ctx: Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description=f"{E['cross']}  You are not in a voice channel.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)
        members = ctx.author.voice.channel.members
        await self._create_paginated_list(
            ctx, members,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"🔊 {ctx.author.voice.channel.name} ({len(members)} total)",
        )

    @list_group.command(name="early", aliases=["sup"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_early(self, ctx: Context):
        early = [m for m in ctx.guild.members if m.public_flags.early_supporter]
        await self._create_paginated_list(
            ctx, early,
            lambda m: f"{m.mention} (`{m.id}`)",
            f"🌟 Early Supporters ({len(early)} total)",
        )

    # ══════════════════════════════
    #   PING IMAGE GENERATOR
    # ══════════════════════════════
    def _make_ping_image(self, api_ms: int, bot_ms: int, uptime_str: str, avatar_bytes: bytes | None, username: str) -> io.BytesIO:
        W, H = 1100, 430
        img  = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        for x in range(0, W, 42):
            draw.line([(x, 0), (x, H)], fill=(255, 80, 0, 7), width=1)
        for y in range(0, H, 42):
            draw.line([(0, y), (W, y)], fill=(255, 80, 0, 7), width=1)

        try:
            font_big    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
            font_med    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
            font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
            font_title  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
            font_label  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            font_name   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            font_status = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        except Exception:
            font_big = font_med = font_small = font_title = font_label = font_name = font_status = ImageFont.load_default()

        tx, ty = 30, 20
        title_parts = [
            ("Powered By ",  (255, 255, 255, 255)),
            ("Q",            (255, 60,  0,   255)),
            ("y",            (255, 100, 0,   255)),
            ("r",            (255, 150, 10,  255)),
            ("o",            (255, 80,  0,   255)),
            ("n",            (255, 50,  0,   255)),
            (" Development", (255, 180, 60,  255)),
        ]
        for text, color in title_parts:
            draw.text((tx, ty), text, font=font_title, fill=color)
            tx += draw.textlength(text, font=font_title)

        def draw_lat_box(bx, by, bw, bh, label, value_ms, line_col, glow_col):
            draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=14,
                                   fill=(6, 6, 6, 255), outline=(*glow_col, 55), width=1)
            draw.text((bx+18, by+15), label.upper(), font=font_label, fill=(*glow_col, 170))
            val_str = str(value_ms)
            draw.text((bx+18, by+36), val_str, font=font_big, fill=(255, 255, 255, 255))
            val_w = draw.textlength(val_str, font=font_big)
            draw.text((bx+22+val_w, by+62), "ms", font=font_med, fill=(170, 170, 170, 255))

            pts_count = 50
            gx0, gx1  = bx+12, bx+bw-12
            gy0 = by+bh-16
            gy1 = by+bh-90
            gw  = gx1 - gx0
            rng = random.Random(value_ms * 17 + len(label))
            pts, v = [], float(value_ms)
            for _ in range(pts_count):
                v += rng.uniform(-10, 10)
                v  = max(value_ms-22, min(value_ms+22, v))
                pts.append(v)
            lo, hi = min(pts)-4, max(pts)+4
            def ny(val):
                return gy0 - ((val - lo) / (hi - lo + 1e-9)) * (gy0 - gy1)
            coords = [(gx0 + i/(pts_count-1)*gw, ny(p)) for i, p in enumerate(pts)]
            poly   = coords + [(gx1, gy0), (gx0, gy0)]
            draw.polygon(poly, fill=(*glow_col, 40))
            for i in range(len(coords)-1):
                draw.line([coords[i], coords[i+1]], fill=(*line_col, 215), width=2)
            ex, ey = coords[-1]
            draw.ellipse([ex-6, ey-6, ex+6, ey+6], fill=(*line_col, 255))

        ORANGE = (255, 100, 0)
        CYAN   = (0,   200, 255)
        draw_lat_box(28,  68, 390, 310, "API Latency", api_ms, ORANGE, ORANGE)
        draw_lat_box(438, 68, 390, 310, "Bot Latency", bot_ms, CYAN,   CYAN)

        AV_CX, AV_CY, AV_R = 928, 200, 85
        glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        for r_extra, alpha in [(80,10),(60,18),(44,30),(30,50),(18,75),(10,110)]:
            gd.ellipse([AV_CX-AV_R-r_extra, AV_CY-AV_R-r_extra,
                        AV_CX+AV_R+r_extra, AV_CY+AV_R+r_extra],
                       fill=(255, 80, 0, alpha))
        glow_b = glow_layer.filter(ImageFilter.GaussianBlur(radius=20))
        img    = Image.alpha_composite(img, glow_b)
        draw   = ImageDraw.Draw(img)

        if avatar_bytes:
            try:
                av   = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AV_R*2, AV_R*2))
                mask = Image.new("L", (AV_R*2, AV_R*2), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, AV_R*2, AV_R*2], fill=255)
                av.putalpha(mask)
                img.paste(av, (AV_CX-AV_R, AV_CY-AV_R), av)
                draw = ImageDraw.Draw(img)
            except Exception:
                draw.ellipse([AV_CX-AV_R, AV_CY-AV_R, AV_CX+AV_R, AV_CY+AV_R], fill=(18, 18, 18, 255))
        else:
            draw.ellipse([AV_CX-AV_R, AV_CY-AV_R, AV_CX+AV_R, AV_CY+AV_R], fill=(18, 18, 18, 255))

        for t, a in [(7,15),(5,50),(3,130),(2,220),(1,255)]:
            draw.ellipse([AV_CX-AV_R-t, AV_CY-AV_R-t, AV_CX+AV_R+t, AV_CY+AV_R+t],
                         outline=(255, 100, 0, a), width=2)

        pool   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd     = ImageDraw.Draw(pool)
        pd.ellipse([AV_CX-80, AV_CY+AV_R-5, AV_CX+80, AV_CY+AV_R+50], fill=(255, 70, 0, 70))
        pool_b = pool.filter(ImageFilter.GaussianBlur(radius=25))
        img    = Image.alpha_composite(img, pool_b)
        draw   = ImageDraw.Draw(img)

        DX, DY = AV_CX+AV_R-12, AV_CY+AV_R-12
        draw.ellipse([DX-10, DY-10, DX+10, DY+10], fill=(0, 0, 0, 255))
        draw.ellipse([DX-7,  DY-7,  DX+7,  DY+7],  fill=(255, 100, 0, 255))

        nw = draw.textlength(username, font=font_name)
        draw.text((AV_CX - nw//2, AV_CY+AV_R+16), username, font=font_name, fill=(255, 255, 255, 255))
        ow = draw.textlength("ONLINE", font=font_status)
        draw.text((AV_CX - ow//2, AV_CY+AV_R+36), "ONLINE", font=font_status, fill=(255, 100, 0, 255))

        ut = f"System Uptime: {uptime_str}"
        uw = draw.textlength(ut, font=font_small)
        draw.text(((W - uw)//2, H-28), ut, font=font_small, fill=(130, 65, 0, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    # ══════════════════════════════
    #   PING
    # ══════════════════════════════
    @commands.command(name="ping", aliases=["latency"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def ping(self, ctx: Context):
        loading = discord.Embed(
            description=f"{E['loading']}  Measuring ping...",
            color=0x000000
        )
        loading_msg = await ctx.reply(embed=loading, mention_author=False)

        start  = time.perf_counter()
        tmp    = await ctx.channel.send("\u200b")
        api_ms = round((time.perf_counter() - start) * 1000)
        await tmp.delete()

        await asyncio.sleep(1)
        await loading_msg.delete()

        bot_ms   = round(self.bot.latency * 1000)
        uptime_s = int(time.time() - start_time)
        delta    = datetime.timedelta(seconds=uptime_s)
        uptime_str = (
            f"{delta.days}d "
            f"{delta.seconds // 3600:02}h "
            f"{delta.seconds % 3600 // 60:02}m "
            f"{delta.seconds % 60:02}s"
        )

        avatar_bytes = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(ctx.author.display_avatar.with_format("png").with_size(128))) as r:
                    if r.status == 200:
                        avatar_bytes = await r.read()
        except Exception:
            pass

        buf  = await self.bot.loop.run_in_executor(
            None, self._make_ping_image,
            api_ms, bot_ms, uptime_str, avatar_bytes, ctx.author.display_name
        )
        await ctx.reply(file=discord.File(buf, filename="ping.png"))

    # ══════════════════════════════
    #   PERMISSIONS
    # ══════════════════════════════
    @commands.command(name="permissions", aliases=["perms"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def permissions(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        perms  = member.guild_permissions

        ALL_PERMS = {
            "administrator":        "Administrator",
            "manage_guild":         "Manage Server",
            "manage_roles":         "Manage Roles",
            "manage_channels":      "Manage Channels",
            "manage_messages":      "Manage Messages",
            "manage_nicknames":     "Manage Nicknames",
            "manage_emojis":        "Manage Emojis",
            "manage_webhooks":      "Manage Webhooks",
            "ban_members":          "Ban Members",
            "kick_members":         "Kick Members",
            "mute_members":         "Mute Members",
            "deafen_members":       "Deafen Members",
            "move_members":         "Move Members",
            "mention_everyone":     "Mention Everyone",
            "view_audit_log":       "View Audit Log",
            "send_messages":        "Send Messages",
            "embed_links":          "Embed Links",
            "attach_files":         "Attach Files",
            "read_message_history": "Read History",
            "use_external_emojis":  "External Emojis",
            "add_reactions":        "Add Reactions",
            "connect":              "Connect VC",
            "speak":                "Speak VC",
        }

        granted = []
        denied  = []
        for perm_attr, perm_name in ALL_PERMS.items():
            if getattr(perms, perm_attr, False):
                granted.append(f"{E['tick']} {perm_name}")
            else:
                denied.append(f"{E['cross']} {perm_name}")

        embed = discord.Embed(
            title=f"{E['lock']}  Permissions — {member.display_name}",
            description=(
                f"{E['user']}  {member.mention}  `{member.id}`\n"
                f"{E['role']}  **Top Role:** {member.top_role.mention if not member.top_role.is_default() else 'None'}"
            ),
            color=0x000000
        )
        embed.add_field(
            name=f"{E['tick']}  Granted ({len(granted)})",
            value="\n".join(granted[:12]) or "None",
            inline=True
        )
        embed.add_field(
            name=f"{E['cross']}  Denied ({len(denied)})",
            value="\n".join(denied[:12]) or "None",
            inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   JOINED-AT
    # ══════════════════════════════
    @commands.command(name="joined-at")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    async def joined_at(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        joined = member.joined_at
        if not joined:
            embed = discord.Embed(
                description=f"{E['cross']}  Join date unavailable for **{member.display_name}**.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        joined_ts  = int(joined.timestamp())
        created_ts = int(member.created_at.timestamp())
        all_members = sorted([m for m in ctx.guild.members if m.joined_at], key=lambda m: m.joined_at)
        join_pos    = next((i+1 for i, m in enumerate(all_members) if m.id == member.id), "?")

        embed = discord.Embed(
            title=f"{E['timer']}  Join Info — {member.display_name}",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['arrow']}  Joined Server",
            value=f"<t:{joined_ts}:F>\n(<t:{joined_ts}:R>)",
            inline=True
        )
        embed.add_field(
            name=f"{E['user']}  Account Created",
            value=f"<t:{created_ts}:F>\n(<t:{created_ts}:R>)",
            inline=True
        )
        embed.add_field(
            name=f"{E['star']}  Join Position",
            value=f"`#{join_pos}` of `{ctx.guild.member_count:,}` members",
            inline=False
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   GITHUB
    # ══════════════════════════════
    @commands.command(name="github")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def github(self, ctx: Context, *, query: str):
        loading = discord.Embed(
            description=f"{E['loading']}  Searching GitHub...",
            color=0x000000
        )
        msg = await ctx.reply(embed=loading, mention_author=False)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/search/repositories",
                params={"q": query},
            ) as resp:
                data = await resp.json()

        await msg.delete()

        if not data.get("items"):
            embed = discord.Embed(
                description=f"{E['cross']}  No results found for `{query}`",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        repo       = data["items"][0]
        created_ts = int(datetime.datetime.strptime(repo["created_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp())
        updated_ts = int(datetime.datetime.strptime(repo["updated_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp())

        embed = discord.Embed(
            title=f"{E['github']}  {repo['full_name']}",
            url=repo["html_url"],
            description=repo.get("description") or "No description provided.",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['stats']}  Stats",
            value=(
                f"⭐ **Stars:** `{repo['stargazers_count']:,}`\n"
                f"🍴 **Forks:** `{repo['forks_count']:,}`\n"
                f"👁️ **Watchers:** `{repo['watchers_count']:,}`\n"
                f"🐛 **Issues:** `{repo['open_issues_count']:,}`"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['arrow']}  Info",
            value=(
                f"{E['user']} **Owner:** `{repo['owner']['login']}`\n"
                f"💾 **Language:** `{repo.get('language') or 'Unknown'}`\n"
                f"{E['timer']} **Created:** <t:{created_ts}:D>\n"
                f"🔄 **Updated:** <t:{updated_ts}:R>"
            ),
            inline=True
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="View on GitHub", style=discord.ButtonStyle.link, url=repo["html_url"]))
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, view=view)

    # ══════════════════════════════
    #   CHANNEL INFO
    # ══════════════════════════════
    @commands.hybrid_command(name="channelinfo", aliases=["cinfo", "ci"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def channelinfo(self, ctx: Context, channel: Optional[discord.TextChannel] = None):
        channel    = channel or ctx.channel
        slowmode   = f"`{channel.slowmode_delay}s`" if channel.slowmode_delay else "`Off`"
        created_ts = int(channel.created_at.timestamp())
        cat        = channel.category.name if channel.category else "None"
        topic      = (channel.topic[:80] + "...") if channel.topic and len(channel.topic) > 80 else (channel.topic or "No topic set")

        embed = discord.Embed(
            title=f"{E['channel']}  Channel Info — #{channel.name}",
            description=f"> {topic}",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['arrow']}  General",
            value=(
                f"{E['dot']} **ID:** `{channel.id}`\n"
                f"{E['dot']} **Category:** `{cat}`\n"
                f"{E['timer']} **Created:** <t:{created_ts}:D> (<t:{created_ts}:R>)"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['settings']}  Settings",
            value=(
                f"⏱️ **Slowmode:** {slowmode}\n"
                f"🔞 **NSFW:** {E['tick'] if channel.nsfw else E['cross']}\n"
                f"📌 **Position:** `#{channel.position}`"
            ),
            inline=True
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    # ══════════════════════════════
    #   VC INFO
    # ══════════════════════════════
    @commands.hybrid_command(name="vcinfo")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def vcinfo(self, ctx: Context, channel: Optional[discord.VoiceChannel] = None):
        vc = channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not vc:
            embed = discord.Embed(
                description=f"{E['cross']}  No voice channel specified or you're not in one.",
                color=0x000000
            )
            return await ctx.reply(embed=embed)

        created_ts = int(vc.created_at.timestamp())
        limit      = f"`{vc.user_limit}`" if vc.user_limit else "`Unlimited`"
        cat        = vc.category.name if vc.category else "None"

        embed = discord.Embed(
            title=f"🔊  VC Info — {vc.name}",
            color=0x000000
        )
        embed.add_field(
            name=f"{E['arrow']}  General",
            value=(
                f"{E['dot']} **ID:** `{vc.id}`\n"
                f"{E['dot']} **Category:** `{cat}`\n"
                f"{E['timer']} **Created:** <t:{created_ts}:D> (<t:{created_ts}:R>)"
            ),
            inline=True
        )
        embed.add_field(
            name=f"{E['stats']}  Details",
            value=(
                f"{E['members']} **Users:** `{len(vc.members)}`\n"
                f"🔊 **Bitrate:** `{vc.bitrate // 1000}kbps`\n"
                f"👥 **Limit:** {limit}"
            ),
            inline=True
        )
        if vc.members:
            member_list = " ".join(m.mention for m in vc.members[:10])
            if len(vc.members) > 10:
                member_list += f" +{len(vc.members)-10} more"
            embed.add_field(
                name=f"{E['user']}  Connected Members",
                value=member_list,
                inline=False
            )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Extra(bot))
