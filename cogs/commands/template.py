from __future__ import annotations

import asyncio
import aiohttp
import discord
import aiosqlite
from discord.ext import commands
from discord import app_commands

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
LOADING  = "<a:CupidXloading:1474386958741536891>"
TICK     = "<:CupidXtick1:1474369967271968949>"
CROSS    = "<:CupidXCross:1473996646873436336>"
WARN     = "<:CupidXWarning:1474348304186867784>"
DOT      = "<a:CupidXdot:1473986328126558209>"

ACCENT   = 0x1a1a2e
SUCCESS  = 0x00c853
DANGER   = 0xff1744
WARNING  = 0xffa500

PREMIUM_DB = "db/premium.db"


# ─────────────────────────────────────────────
#  PREMIUM CHECK
# ─────────────────────────────────────────────
async def _is_premium(guild_id: int) -> bool:
    try:
        async with aiosqlite.connect(PREMIUM_DB) as db:
            async with db.execute(
                "SELECT 1 FROM premium_guilds WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                return await cursor.fetchone() is not None
    except Exception:
        return False


def _premium_required_embed() -> discord.Embed:
    return discord.Embed(
        title=f"{CROSS}  Premium Required",
        description=(
            "This command is only available for **Premium Servers**.\n\n"
            "Use `premium redeem <code>` to activate premium,\n"
            "or contact the bot owner to purchase."
        ),
        color=WARNING
    )


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _progress_embed(title: str, description: str, percent: int) -> discord.Embed:
    bar_filled = percent // 10
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    embed = discord.Embed(
        title=f"{LOADING}  {title}",
        description=f"{description}\n\n`[{bar}]` **{percent}%**",
        color=ACCENT
    )
    embed.set_footer(text="CupidX Template System • Please wait…")
    return embed


def _mode_label(apply_channels: bool, apply_roles: bool) -> str:
    if apply_channels and apply_roles:
        return "Channels + Roles"
    elif apply_channels:
        return "Channels Only"
    else:
        return "Roles Only"


def _select_embed(template_code: str, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title=f"{WARN}  Apply Template — Select Mode",
        description=(
            "Choose what you want to apply from the template.\n\n"
            f"{DOT} **Channels + Roles** — Delete & recreate both\n"
            f"{DOT} **Channels Only** — Only channels change, roles stay\n"
            f"{DOT} **Roles Only** — Only roles change, channels stay\n\n"
            "Use the dropdown below to select, then confirm."
        ),
        color=WARNING
    )
    embed.add_field(name="Template Code", value=f"```{template_code}```", inline=False)
    embed.add_field(name="Server", value=f"`{guild.name}`", inline=True)
    embed.add_field(name="Channels", value=f"`{len(guild.channels)}`", inline=True)
    embed.add_field(name="Roles", value=f"`{len(guild.roles) - 1}`", inline=True)
    embed.set_footer(text="Select a mode • Expires in 90s")
    return embed


def _confirm_embed(template_code: str, guild: discord.Guild,
                   apply_channels: bool, apply_roles: bool) -> discord.Embed:
    mode = _mode_label(apply_channels, apply_roles)

    lines = []
    if apply_channels:
        lines.append(f"{DOT} All existing **channels** will be deleted & recreated")
    if apply_roles:
        lines.append(f"{DOT} All existing **roles** will be deleted (except @everyone) & recreated")
    if not apply_channels:
        lines.append(f"{DOT} Existing channels will **not** be touched")
    if not apply_roles:
        lines.append(f"{DOT} Existing roles will **not** be touched")
    lines.append(f"{DOT} This action **cannot be undone**")

    embed = discord.Embed(
        title=f"{WARN}  Confirm Template Application",
        color=DANGER
    )
    embed.add_field(name="Selected Mode", value=f"```{mode}```", inline=False)
    embed.add_field(name="What will happen?", value="\n".join(lines), inline=False)
    embed.add_field(name="Template Code", value=f"```{template_code}```", inline=False)
    embed.add_field(name="Server", value=f"`{guild.name}` — `{guild.id}`", inline=True)
    embed.add_field(name="Channels", value=f"`{len(guild.channels)}`", inline=True)
    embed.add_field(name="Roles", value=f"`{len(guild.roles) - 1}`", inline=True)
    embed.set_footer(text="Only the Server Owner can confirm • Expires in 90s")
    return embed


# ─────────────────────────────────────────────
#  STEP 1 VIEW — Mode Select Dropdown
# ─────────────────────────────────────────────
class TemplateModeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Channels + Roles",
                value="both",
                description="Delete & recreate both channels and roles",
                emoji="🔄"
            ),
            discord.SelectOption(
                label="Channels Only",
                value="channels",
                description="Only channels will change, roles stay as-is",
                emoji="📋"
            ),
            discord.SelectOption(
                label="Roles Only",
                value="roles",
                description="Only roles will change, channels stay as-is",
                emoji="🎭"
            ),
        ]
        super().__init__(
            placeholder="Select what to apply from template…",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: TemplateModeView = self.view
        selected = self.values[0]

        apply_channels = selected in ("both", "channels")
        apply_roles    = selected in ("both", "roles")

        confirm_view = TemplateConfirmView(
            actor_id       = view.actor_id,
            template_code  = view.template_code,
            apply_channels = apply_channels,
            apply_roles    = apply_roles
        )
        embed = _confirm_embed(view.template_code, interaction.guild, apply_channels, apply_roles)

        view.stop()
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class TemplateModeView(discord.ui.View):
    def __init__(self, actor_id: int, template_code: str):
        super().__init__(timeout=90)
        self.actor_id      = actor_id
        self.template_code = template_code
        self.add_item(TemplateModeSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                f"{CROSS} Only the person who ran this command can interact.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✖  Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"{CROSS}  Cancelled",
                description="Template application was cancelled. No changes made.",
                color=DANGER
            ),
            view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ─────────────────────────────────────────────
#  STEP 2 VIEW — Confirm / Cancel / Back
# ─────────────────────────────────────────────
class TemplateConfirmView(discord.ui.View):
    def __init__(self, actor_id: int, template_code: str,
                 apply_channels: bool, apply_roles: bool):
        super().__init__(timeout=90)
        self.actor_id       = actor_id
        self.template_code  = template_code
        self.apply_channels = apply_channels
        self.apply_roles    = apply_roles

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                f"{CROSS} Only the person who ran this command can interact.",
                ephemeral=True
            )
            return False
        return True

    # ── CONFIRM ──
    @discord.ui.button(label="✅  Confirm & Apply", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                f"{CROSS} **Server Owner only** can confirm template application.",
                ephemeral=True
            )

        self.stop()
        for item in self.children:
            item.disabled = True

        # FIX: pehle response edit karo, phir original_response se message fetch karo
        await interaction.response.edit_message(
            embed=_progress_embed("Starting...", "Fetching template data…", 0),
            view=self
        )

        # FIX: interaction.message None hota hai — original_response() use karo
        message = await interaction.original_response()

        await _apply_template(
            interaction    = interaction,
            message        = message,
            template_code  = self.template_code,
            apply_channels = self.apply_channels,
            apply_roles    = self.apply_roles
        )

    # ── BACK ──
    @discord.ui.button(label="◀  Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        mode_view = TemplateModeView(self.actor_id, self.template_code)
        embed = _select_embed(self.template_code, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=mode_view)

    # ── CANCEL ──
    @discord.ui.button(label="✖  Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"{CROSS}  Cancelled",
                description="Template application was cancelled. No changes made.",
                color=DANGER
            ),
            view=None
        )


# ─────────────────────────────────────────────
#  CORE: apply template with mode support
# ─────────────────────────────────────────────
async def _apply_template(
    interaction: discord.Interaction,
    message: discord.Message,
    template_code: str,
    apply_channels: bool,
    apply_roles: bool
):
    guild = interaction.guild

    async def edit(title: str, desc: str, pct: int):
        try:
            await message.edit(embed=_progress_embed(title, desc, pct))
        except Exception:
            pass

    try:
        # ── Step 1: Fetch template ──
        await edit("Fetching Template", "Connecting to Discord template API…", 5)
        try:
            token = interaction.client.http.token
            headers = {"Authorization": f"Bot {token}"}
            api_url = f"https://discord.com/api/v10/guilds/templates/{template_code}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 404:
                        raise ValueError("Template not found. Make sure the link/code is correct.")
                    elif resp.status != 200:
                        raise ValueError(f"Discord API error: HTTP {resp.status}")
                    raw = await resp.json()
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch template: {e}")

        tdata      = raw.get("serialized_source_guild") or raw
        t_channels = tdata.get("channels", [])
        t_roles    = [r for r in tdata.get("roles", []) if str(r.get("id", "")) != "0"]

        if apply_channels and not t_channels:
            raise ValueError("Template mein koi channels nahi mile.")
        if apply_roles and not t_roles:
            raise ValueError("Template mein koi roles nahi mile.")

        del_ch_count = len(guild.channels) if apply_channels else 0
        del_rl_count = len([r for r in guild.roles if not r.is_default()]) if apply_roles else 0
        cre_ch_count = len(t_channels) if apply_channels else 0
        cre_rl_count = len(t_roles)    if apply_roles    else 0
        total_ops = (del_ch_count + del_rl_count + cre_ch_count + cre_rl_count) or 1
        done = 0

        # ── Step 2: Delete channels (only if apply_channels) ──
        channels_sorted = sorted(guild.channels, key=lambda c: (isinstance(c, discord.TextChannel), c.position))
        if apply_channels:
            await edit("Deleting Channels", f"Removing {len(guild.channels)} channels…", 10)
            for ch in channels_sorted:
                try:
                    await ch.delete(reason="CupidX template apply")
                    await asyncio.sleep(0.8)
                except Exception:
                    pass
                done += 1
                pct = int(done / total_ops * 70) + 5
                await edit(
                    "Deleting Channels",
                    f"Deleted `{done}` of `{len(channels_sorted)}` channels…",
                    min(pct, 40)
                )
        else:
            await edit("Skipping Channels", "Channels will not be changed…", 15)
            await asyncio.sleep(0.5)

        # ── Step 3: Delete roles (only if apply_roles) ──
        roles_to_del = [
            r for r in guild.roles
            if not r.is_default() and not r.managed and r < guild.me.top_role
        ]
        if apply_roles:
            await edit("Deleting Roles", f"Removing {len(roles_to_del)} roles…", 42)
            for role in reversed(roles_to_del):
                try:
                    await role.delete(reason="CupidX template apply")
                    await asyncio.sleep(0.6)
                except Exception:
                    pass
                done += 1
                pct = int(done / total_ops * 70) + 5
                await edit(
                    "Deleting Roles",
                    f"Deleted `{done - (len(channels_sorted) if apply_channels else 0)}` of `{len(roles_to_del)}` roles…",
                    min(pct, 55)
                )
        else:
            await edit("Skipping Roles", "Roles will not be changed…", 42)
            await asyncio.sleep(0.5)

        # ── Step 4: Create roles (only if apply_roles) ──
        role_id_map: dict = {}

        if apply_roles:
            await edit("Creating Roles", f"Creating {len(t_roles)} roles from template…", 58)
            for tr in sorted(t_roles, key=lambda r: r.get("position", 0)):
                try:
                    perms     = discord.Permissions(int(tr.get("permissions", 0)))
                    color_val = tr.get("color", 0)
                    color     = discord.Color(color_val) if color_val else discord.Color.default()

                    new_role = await guild.create_role(
                        name        = tr.get("name", "role"),
                        permissions = perms,
                        color       = color,
                        hoist       = tr.get("hoist", False),
                        mentionable = tr.get("mentionable", False),
                        reason      = "CupidX template apply"
                    )
                    role_id_map[tr["id"]] = new_role
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[Template] Role create error: {e} | data: {tr}")
                done += 1
                await edit(
                    "Creating Roles",
                    f"Created `{len(role_id_map)}` of `{len(t_roles)}` roles…",
                    min(int(done / total_ops * 70) + 5, 72)
                )
        else:
            # Roles apply nahi ho rahi — existing roles ko map karo name se
            # taaki channel overwrites kaam karein
            for tr in t_roles:
                t_name = tr.get("name", "")
                match = discord.utils.get(guild.roles, name=t_name)
                if match:
                    role_id_map[tr["id"]] = match

        # ── Step 5: Create channels (only if apply_channels) ──
        cat_id_map: dict = {}
        ch_created = 0

        if apply_channels:
            await edit("Creating Channels", f"Creating {len(t_channels)} channels…", 75)

            categories_data = [c for c in t_channels if c.get("type") == 4]
            others_data     = [c for c in t_channels if c.get("type") != 4]

            # Categories first
            for cat in sorted(categories_data, key=lambda c: c.get("position", 0)):
                try:
                    overwrites = _parse_overwrites(cat, guild, role_id_map)
                    new_cat = await guild.create_category(
                        name       = cat.get("name", "category"),
                        overwrites = overwrites,
                        reason     = "CupidX template apply"
                    )
                    cat_id_map[cat["id"]] = new_cat
                    await asyncio.sleep(0.7)
                except Exception:
                    pass
                done += 1
                await edit(
                    "Creating Categories",
                    f"Created `{len(cat_id_map)}` categories…",
                    min(int(done / total_ops * 70) + 5, 85)
                )

            # Other channels
            for ch in sorted(others_data, key=lambda c: c.get("position", 0)):
                try:
                    parent_id  = ch.get("parent_id")
                    category   = cat_id_map.get(parent_id)
                    overwrites = _parse_overwrites(ch, guild, role_id_map)
                    ch_type    = ch.get("type", 0)

                    kwargs = dict(
                        name       = ch.get("name", "channel"),
                        overwrites = overwrites,
                        category   = category,
                        reason     = "CupidX template apply"
                    )

                    if ch_type == 0:
                        await guild.create_text_channel(
                            topic=ch.get("topic") or "",
                            nsfw=ch.get("nsfw", False),
                            slowmode_delay=ch.get("rate_limit_per_user", 0),
                            **kwargs
                        )
                    elif ch_type == 2:
                        await guild.create_voice_channel(
                            bitrate=ch.get("bitrate", 64000),
                            user_limit=ch.get("user_limit", 0),
                            **kwargs
                        )
                    elif ch_type == 5:
                        await guild.create_text_channel(news=True, **kwargs)
                    elif ch_type == 13:
                        await guild.create_stage_channel(**kwargs)
                    elif ch_type == 15:
                        await guild.create_forum(**kwargs)

                    ch_created += 1
                    await asyncio.sleep(0.7)
                except Exception as e:
                    print(f"[Template] Channel create error: {e} | data: {ch}")
                done += 1
                await edit(
                    "Creating Channels",
                    f"Created `{ch_created}` of `{len(others_data)}` channels…",
                    min(int(done / total_ops * 70) + 5, 95)
                )
        else:
            await edit("Skipping Channel Creation", "Channels were not modified…", 90)
            await asyncio.sleep(0.5)

        # ── Step 6: Done ──
        mode = _mode_label(apply_channels, apply_roles)
        embed = discord.Embed(
            title=f"{TICK}  Template Applied Successfully!",
            color=SUCCESS
        )
        embed.add_field(name="Mode",             value=f"`{mode}`",               inline=False)
        embed.add_field(name="Roles Created",    value=f"`{len(role_id_map)}`",   inline=True)
        embed.add_field(name="Categories",       value=f"`{len(cat_id_map)}`",    inline=True)
        embed.add_field(name="Channels Created", value=f"`{ch_created}`",         inline=True)
        embed.add_field(name="Template",         value=f"```{template_code}```",  inline=False)
        embed.set_footer(text="CupidX Template System • Complete")

        try:
            await message.edit(embed=embed, view=None)
        except Exception:
            pass

    except Exception as e:
        err_embed = discord.Embed(
            title=f"{CROSS}  Error Applying Template",
            description=f"```{e}```",
            color=DANGER
        )
        err_embed.set_footer(text="CupidX Template System")
        try:
            await message.edit(embed=err_embed, view=None)
        except Exception:
            pass


def _parse_overwrites(ch_data: dict, guild: discord.Guild, role_id_map: dict) -> dict:
    overwrites = {}
    for ow in ch_data.get("permission_overwrites", []):
        allow   = discord.Permissions(int(ow.get("allow", 0)))
        deny    = discord.Permissions(int(ow.get("deny", 0)))
        ow_id   = ow.get("id")
        ow_type = ow.get("type")

        if ow_type == 0:
            if str(ow_id) == "0":
                target = guild.default_role
            else:
                target = (
                    role_id_map.get(ow_id)
                    or role_id_map.get(str(ow_id))
                    or role_id_map.get(int(ow_id) if str(ow_id).isdigit() else ow_id)
                )
        else:
            continue

        if target:
            overwrites[target] = discord.PermissionOverwrite.from_pair(allow, deny)

    return overwrites


# ─────────────────────────────────────────────
#  COG
# ─────────────────────────────────────────────
class Template(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    async def _check_premium(self, guild_id: int) -> bool:
        return await _is_premium(guild_id)

    # ── PREFIX: applytemplate <link/code> ──
    @commands.command(name="applytemplate", aliases=["atemp", "applytemp"])
    @commands.guild_only()
    async def prefix_apply(self, ctx: commands.Context, link: str):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply(embed=discord.Embed(
                description=f"{CROSS} **Owner Only:** This command is restricted to the Server Owner.",
                color=DANGER
            ))

        if not await self._check_premium(ctx.guild.id):
            return await ctx.reply(embed=_premium_required_embed())

        code = link.strip("/").split("/")[-1]
        view = TemplateModeView(ctx.author.id, code)
        embed = _select_embed(code, ctx.guild)
        await ctx.reply(embed=embed, view=view)

    # ── SLASH: /applytemplate ──
    @app_commands.command(name="applytemplate", description="Apply a Discord server template (Owner Only • Premium)")
    @app_commands.describe(link="Discord template link or code")
    @app_commands.guild_only()
    async def slash_apply(self, interaction: discord.Interaction, link: str):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{CROSS} **Owner Only:** This command is restricted to the Server Owner.",
                    color=DANGER
                ),
                ephemeral=True
            )

        if not await self._check_premium(interaction.guild.id):
            return await interaction.response.send_message(
                embed=_premium_required_embed(),
                ephemeral=True
            )

        code = link.strip("/").split("/")[-1]
        view = TemplateModeView(interaction.user.id, code)
        embed = _select_embed(code, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    @prefix_apply.error
    async def apply_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=discord.Embed(
                description=f"{CROSS} **Usage:** `{ctx.prefix}applytemplate <discord template link or code>`",
                color=DANGER
            ))


async def setup(client: commands.Bot):
    await client.add_cog(Template(client))
