import discord
from discord.ext import commands
from discord import PermissionOverwrite
import aiosqlite
from core import Context
from core.Cog import Cog
from core.cupidx import cupidx

DATABASE_PATH = "db/j2c.db"

# ══════════════════════════
# MODALS
# ══════════════════════════

class LimitModal(discord.ui.Modal, title="👥 Set User Limit"):
    limit = discord.ui.TextInput(
        label="User Limit (0 = unlimited)",
        placeholder="Example: 5",
        max_length=2,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Defer immediately — prevents "Interaction Failed"
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ You must be in your voice channel!", ephemeral=True)
                return
            val = int(self.limit.value)
            if val < 0 or val > 99:
                await interaction.followup.send("⚠️ Limit must be between **0** and **99**.", ephemeral=True)
                return
            await interaction.user.voice.channel.edit(user_limit=val)
            await interaction.followup.send(
                f"👥 User limit set to `{'Unlimited' if val == 0 else val}`",
                ephemeral=True
            )
        except ValueError:
            await interaction.followup.send("⚠️ Enter a valid number.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to edit this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.followup.send(f"❌ Unexpected error: `{error}`", ephemeral=True)
        except Exception:
            pass


class RenameModal(discord.ui.Modal, title="✏️ Rename Your Channel"):
    name = discord.ui.TextInput(
        label="New Channel Name",
        placeholder="Example: Gaming Room",
        max_length=100,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ You must be in your voice channel!", ephemeral=True)
                return
            new_name = self.name.value.strip()
            if not new_name:
                await interaction.followup.send("⚠️ Channel name cannot be empty.", ephemeral=True)
                return
            await interaction.user.voice.channel.edit(name=new_name)
            await interaction.followup.send(f"✏️ Renamed to **{new_name}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to rename this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.followup.send(f"❌ Unexpected error: `{error}`", ephemeral=True)
        except Exception:
            pass


class BitrateModal(discord.ui.Modal, title="🎵 Set Bitrate"):
    bitrate = discord.ui.TextInput(
        label="Bitrate in kbps (8 – 384)",
        placeholder="Example: 64",
        max_length=3,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ You must be in your voice channel!", ephemeral=True)
                return
            br = int(self.bitrate.value)
            if not (8 <= br <= 384):
                await interaction.followup.send("⚠️ Bitrate must be between **8** and **384** kbps.", ephemeral=True)
                return
            await interaction.user.voice.channel.edit(bitrate=br * 1000)
            await interaction.followup.send(f"🎵 Bitrate set to **{br}kbps**", ephemeral=True)
        except ValueError:
            await interaction.followup.send("⚠️ Enter a valid number.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to edit this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.followup.send(f"❌ Unexpected error: `{error}`", ephemeral=True)
        except Exception:
            pass


# ══════════════════════════
# PANEL VIEW (PERSISTENT)
# ══════════════════════════

class Panel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # KEY FIX: interaction_check sirf True/False return kare
    # response yahan send karo, button callback mein NAHI
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in **your voice channel** to use these controls!",
                ephemeral=True
            )
            return False
        return True

    # ── Privacy Buttons ──

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="j2c_lock", row=0)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.voice.channel.set_permissions(
                interaction.guild.default_role, connect=False
            )
            await interaction.followup.send("🔒 Channel **locked** — only allowed users can join.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to lock this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @discord.ui.button(label="Unlock", emoji="🔓", style=discord.ButtonStyle.success, custom_id="j2c_unlock", row=0)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.voice.channel.set_permissions(
                interaction.guild.default_role, connect=True
            )
            await interaction.followup.send("🔓 Channel **unlocked** — anyone can join.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to unlock this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @discord.ui.button(label="Hide", emoji="👁️", style=discord.ButtonStyle.danger, custom_id="j2c_hide", row=0)
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.voice.channel.set_permissions(
                interaction.guild.default_role, view_channel=False
            )
            await interaction.followup.send("👁️ Channel **hidden** — it won't show in channel list.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to hide this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @discord.ui.button(label="Unhide", emoji="👁", style=discord.ButtonStyle.success, custom_id="j2c_show", row=0)
    async def show(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.voice.channel.set_permissions(
                interaction.guild.default_role, view_channel=True
            )
            await interaction.followup.send("👁 Channel **visible** — everyone can see it.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to show this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    # ── Settings Buttons ──

    @discord.ui.button(label="Limit", emoji="👥", style=discord.ButtonStyle.primary, custom_id="j2c_limit", row=1)
    async def limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        # send_modal is its own response — do NOT defer before this
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Rename", emoji="✏️", style=discord.ButtonStyle.primary, custom_id="j2c_rename", row=1)
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(label="Bitrate", emoji="🎵", style=discord.ButtonStyle.primary, custom_id="j2c_bitrate", row=1)
    async def bitrate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BitrateModal())


# ══════════════════════════
# MAIN COG
# ══════════════════════════

class Join2Create(Cog):
    def __init__(self, bot: cupidx):
        self.bot = bot
        self.cache = {}
        bot.loop.create_task(self.init_db())

    # ── DB INIT ──

    async def init_db(self):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS j2c_config (
                    guild_id        INTEGER PRIMARY KEY,
                    enabled         INTEGER DEFAULT 0,
                    category_id     INTEGER,
                    base_channel_id INTEGER,
                    panel_channel_id INTEGER,
                    panel_message_id INTEGER
                )
            """)

            # Migration: handle old column names
            async with db.execute("PRAGMA table_info(j2c_config)") as cur:
                columns = [row[1] for row in await cur.fetchall()]

            if "base_channel_id" not in columns:
                if "channel_id" in columns:
                    await db.execute("ALTER TABLE j2c_config RENAME COLUMN channel_id TO base_channel_id")
                else:
                    await db.execute("ALTER TABLE j2c_config ADD COLUMN base_channel_id INTEGER")

            if "panel_channel_id" not in columns:
                if "control_channel_id" in columns:
                    await db.execute("ALTER TABLE j2c_config RENAME COLUMN control_channel_id TO panel_channel_id")
                else:
                    await db.execute("ALTER TABLE j2c_config ADD COLUMN panel_channel_id INTEGER")

            await db.commit()

        # Register persistent view AFTER db is ready
        self.bot.add_view(Panel())

    # ── DB HELPERS ──

    async def get_config(self, guild_id: int) -> dict:
        if guild_id in self.cache:
            return self.cache[guild_id]
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT enabled, category_id, base_channel_id, panel_channel_id, panel_message_id "
                "FROM j2c_config WHERE guild_id = ?",
                (guild_id,)
            ) as cur:
                row = await cur.fetchone()
        data = {
            "enabled":   row[0] if row else 0,
            "category":  row[1] if row else None,
            "base":      row[2] if row else None,
            "panel_ch":  row[3] if row else None,
            "panel_msg": row[4] if row else None,
        }
        self.cache[guild_id] = data
        return data

    async def save_config(self, guild_id: int, data: dict):
        self.cache[guild_id] = data
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT INTO j2c_config
                    (guild_id, enabled, category_id, base_channel_id, panel_channel_id, panel_message_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    category_id=excluded.category_id,
                    base_channel_id=excluded.base_channel_id,
                    panel_channel_id=excluded.panel_channel_id,
                    panel_message_id=excluded.panel_message_id
            """, (guild_id, data["enabled"], data["category"],
                  data["base"], data["panel_ch"], data["panel_msg"]))
            await db.commit()

    async def delete_config(self, guild_id: int):
        self.cache.pop(guild_id, None)
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM j2c_config WHERE guild_id=?", (guild_id,))
            await db.commit()

    # ── VOICE LISTENER ──

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        config = await self.get_config(member.guild.id)
        if not config["enabled"]:
            return

        base_id  = config["base"]
        category = member.guild.get_channel(config["category"])

        # User joined the base "Join To Create" channel
        if after.channel and after.channel.id == base_id:
            try:
                new_vc = await member.guild.create_voice_channel(
                    name=f"🔊 {member.display_name}'s Room",
                    category=category,
                    overwrites={
                        member.guild.default_role: PermissionOverwrite(connect=False),
                        member: PermissionOverwrite(
                            connect=True,
                            manage_channels=True,
                            move_members=True
                        )
                    }
                )
                await member.move_to(new_vc)
            except Exception:
                pass

        # Auto-delete empty temp channels
        if category:
            for vc in list(category.voice_channels):
                if vc.id == base_id:
                    continue
                if len(vc.members) == 0:
                    try:
                        await vc.delete()
                    except Exception:
                        pass

    # ── COMMANDS ──

    @commands.group(name="j2c", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def j2c(self, ctx: Context):
        """J2C help menu."""
        embed = discord.Embed(
            title="🔊 Join2Create — Help",
            description="Auto voice channel creation system for your server.",
            color=0xFCD005
        )
        embed.add_field(
            name="⚙️ Commands",
            value=(
                f"`{ctx.prefix}j2c setup` — Create J2C channels & panel\n"
                f"`{ctx.prefix}j2c reset` — Remove all J2C channels\n"
                f"`{ctx.prefix}j2c config` — View current configuration"
            ),
            inline=False
        )
        embed.add_field(
            name="🎛️ Panel Buttons",
            value=(
                "🔒 Lock / 🔓 Unlock — Control who can join\n"
                "👁️ Hide / 👁 Unhide — Control visibility\n"
                "👥 Limit — Set max users\n"
                "✏️ Rename — Change channel name\n"
                "🎵 Bitrate — Adjust audio quality"
            ),
            inline=False
        )
        embed.set_footer(text="© CupidX HQ")
        await ctx.reply(embed=embed)

    @j2c.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def j2c_setup(self, ctx: Context):
        config = await self.get_config(ctx.guild.id)
        if config["enabled"]:
            return await ctx.send("⚠️ J2C is **already set up** on this server!")

        msg = await ctx.send("⚙️ Setting up Join2Create...")
        try:
            category = await ctx.guild.create_category("🔊 Voice Channels")
            base     = await ctx.guild.create_voice_channel("➕ Join To Create", category=category)
            panel_ch = await ctx.guild.create_text_channel("🎛️ vc-controls", category=category)

            await panel_ch.set_permissions(ctx.guild.default_role, send_messages=False, add_reactions=False)

            embed = discord.Embed(
                title="🔊 Voice Channel Controls",
                description=(
                    "Join **➕ Join To Create** to get your own private voice channel.\n"
                    "Then use the buttons below to manage it."
                ),
                color=0x2b2d31
            )
            embed.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            embed.add_field(
                name="🔒 Privacy",
                value="`Lock` / `Unlock` — Who can join\n`Hide` / `Unhide` — Visibility",
                inline=True
            )
            embed.add_field(
                name="⚙️ Settings",
                value="`Limit` — Max users\n`Rename` — Channel name\n`Bitrate` — Audio quality",
                inline=True
            )
            embed.set_footer(text="© CupidX — Join2Create System")

            panel_msg = await panel_ch.send(embed=embed, view=Panel())

            await self.save_config(ctx.guild.id, {
                "enabled":   1,
                "category":  category.id,
                "base":      base.id,
                "panel_ch":  panel_ch.id,
                "panel_msg": panel_msg.id
            })
            await msg.edit(content=(
                f"✅ **J2C setup complete!**\n"
                f"Users join {base.mention} to create their own VC.\n"
                f"Controls are in {panel_ch.mention}."
            ))
        except discord.Forbidden:
            await msg.edit(content="❌ I don't have permission to create channels.")
        except Exception as e:
            await msg.edit(content=f"❌ Setup failed: `{e}`")

    @j2c.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def j2c_reset(self, ctx: Context):
        config = await self.get_config(ctx.guild.id)
        if not config["enabled"]:
            return await ctx.send("⚠️ J2C is **not set up** on this server.")

        deleted = 0
        for ch_id in [config["panel_ch"], config["base"], config["category"]]:
            ch = ctx.guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.delete()
                    deleted += 1
                except Exception:
                    pass

        await self.delete_config(ctx.guild.id)
        await ctx.send(f"♻️ **J2C reset complete.** ({deleted} channels removed)")

    @j2c.command(name="config")
    @commands.has_permissions(administrator=True)
    async def j2c_config(self, ctx: Context):
        config = await self.get_config(ctx.guild.id)
        if not config["enabled"]:
            return await ctx.send("⚠️ J2C is **not set up** on this server.")

        cat   = ctx.guild.get_channel(config["category"])
        base  = ctx.guild.get_channel(config["base"])
        panel = ctx.guild.get_channel(config["panel_ch"])

        embed = discord.Embed(title="🔊 J2C Configuration", color=0xFCD005)
        embed.add_field(name="📁 Category",       value=str(cat)           if cat   else "❌ Not found", inline=False)
        embed.add_field(name="➕ Base VC",         value=base.mention       if base  else "❌ Not found", inline=True)
        embed.add_field(name="🎛️ Control Panel",  value=panel.mention      if panel else "❌ Not found", inline=True)
        embed.add_field(name="✅ Status",          value="Active" if config["enabled"] else "Disabled",  inline=True)
        embed.set_footer(text="© CupidX HQ")
        await ctx.reply(embed=embed)

    # ── ERROR HANDLERS ──

    @j2c.error
    async def j2c_error(self, ctx: Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need **Administrator** permission to use J2C commands.")

    @j2c_setup.error
    async def setup_error(self, ctx: Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need **Administrator** permission to setup J2C.")

    @j2c_reset.error
    async def reset_error(self, ctx: Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need **Administrator** permission to reset J2C.")


async def setup(bot: cupidx):
    await bot.add_cog(Join2Create(bot))
