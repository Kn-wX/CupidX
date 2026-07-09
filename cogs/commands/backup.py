import discord
from discord.ext import commands
import aiosqlite
import json
import datetime
import asyncio
import aiohttp
from typing import Optional, List
from core import Cog, Context
from utils import Paginator, DescriptionEmbedPaginator
from discord.ui import View, Button

class BackupConfirmView(View):
    def __init__(self, ctx: Context):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Confirm Restore", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.guild.owner:
            return await interaction.response.send_message("Only the server owner can confirm the restoration.", ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.guild.owner:
            return await interaction.response.send_message("Only the server owner can cancel.", ephemeral=True)
        self.value = False
        self.stop()

class Backup(Cog):
    def __init__(self, client):
        self.client = client
        self.db_path = 'db/backup.db'
        self.premium_db_path = 'db/premium.db'
        self.client.loop.create_task(self.setup_database())

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    guild_id INTEGER,
                    name TEXT,
                    data TEXT,
                    created_at TEXT,
                    PRIMARY KEY (guild_id, name)
                )
            ''')
            await db.commit()

    async def is_premium(self, guild_id: int) -> bool:
        async with aiosqlite.connect(self.premium_db_path) as db:
            async with db.execute("SELECT 1 FROM premium_guilds WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone() is not None

    @commands.group(name="backup", invoke_without_command=True)
    async def backup_group(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🛡️ Server Backup",
                description="Backup and restore your server settings, roles, and channels.",
                color=0xFCD005
            )
            embed.add_field(name="Commands", value=(
                f"`{ctx.prefix}backup create <name>` - Create a backup\n"
                f"`{ctx.prefix}backup delete <name>` - Delete a backup\n"
                f"`{ctx.prefix}backup restore <name>` - Restore a backup\n"
                f"`{ctx.prefix}backup list` - List your backups"
            ), inline=False)
            await ctx.reply(embed=embed)

    @backup_group.command(name="create")
    async def backup_create(self, ctx: Context, *, name: str):
        if ctx.author != ctx.guild.owner:
            return await ctx.reply("<:CupidXWarning:1474348304186867784> Only the server owner can create backups.")
        
        if not await self.is_premium(ctx.guild.id):
            return await ctx.reply("<:CupidXWarning:1474348304186867784> This is a premium-only command.")

        async with ctx.typing():
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM backups WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                    count = (await cursor.fetchone())[0]
                    if count >= 3:
                        return await ctx.reply("<:CupidXWarning:1474348304186867784> You have reached the backup limit (3 per server).")

            def scrape_overwrites(channel):
                overwrites = []
                for target, ow in channel.overwrites.items():
                    if isinstance(target, discord.Role):
                        overwrites.append({
                            "type": "role",
                            "name": target.name,
                            "allow": ow.pair()[0].value,
                            "deny": ow.pair()[1].value
                        })
                return overwrites

            # Scrape data
            data = {
                "name": ctx.guild.name,
                "icon": str(ctx.guild.icon.url) if ctx.guild.icon else None,
                "banner": str(ctx.guild.banner.url) if ctx.guild.banner else None,
                "roles": [],
                "categories": [],
                "channels": []
            }

            # Roles (skip @everyone and managed roles)
            for role in reversed(ctx.guild.roles):
                if role.is_default() or role.managed: continue
                data["roles"].append({
                    "name": role.name,
                    "color": role.color.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable,
                    "permissions": role.permissions.value
                })

            # Channels and Categories
            for category in ctx.guild.categories:
                cat_data = {
                    "name": category.name,
                    "overwrites": scrape_overwrites(category),
                    "channels": []
                }
                for channel in category.channels:
                    ch_data = {
                        "name": channel.name,
                        "type": str(channel.type),
                        "overwrites": scrape_overwrites(channel),
                        "position": channel.position
                    }
                    if isinstance(channel, discord.TextChannel):
                        ch_data["topic"] = channel.topic
                        ch_data["nsfw"] = channel.nsfw
                    elif isinstance(channel, discord.VoiceChannel):
                        ch_data["bitrate"] = channel.bitrate
                        ch_data["user_limit"] = channel.user_limit
                    cat_data["channels"].append(ch_data)
                data["categories"].append(cat_data)

            # Channels without category
            for channel in ctx.guild.channels:
                if channel.category is None:
                    ch_data = {
                        "name": channel.name,
                        "type": str(channel.type),
                        "overwrites": scrape_overwrites(channel),
                        "position": channel.position
                    }
                    data["channels"].append(ch_data)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO backups (guild_id, name, data, created_at) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, name, json.dumps(data), datetime.datetime.utcnow().isoformat())
                )
                await db.commit()

        await ctx.reply(f"<:CupidXtick1:1474369967271968949> Successfully created backup: **{name}**")

    @backup_group.command(name="list")
    async def backup_list(self, ctx: Context):
        if ctx.author != ctx.guild.owner:
            return await ctx.reply("<:CupidXWarning:1474348304186867784> Only the server owner can view backups.")

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT name, created_at FROM backups WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.reply("No backups found for this server.")

        entries = []
        for name, created_at in rows:
            ts = int(datetime.datetime.fromisoformat(created_at).timestamp())
            entries.append(f"**{name}** - <t:{ts}:R>")

        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Server Backups [{len(rows)}/3]",
            per_page=10,
            color=0xFCD005
        ), ctx=ctx)
        await paginator.paginate()

    @backup_group.command(name="delete")
    async def backup_delete(self, ctx: Context, *, name: str):
        if ctx.author != ctx.guild.owner:
            return await ctx.reply("<:CupidXWarning:1474348304186867784> Only the server owner can delete backups.")

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM backups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name))
            if cursor.rowcount == 0:
                return await ctx.reply(f"Backup **{name}** not found.")
            await db.commit()

        await ctx.reply(f"<:CupidXtick1:1474369967271968949> Deleted backup: **{name}**")

    @backup_group.command(name="restore")
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def backup_restore(self, ctx: Context, *, name: str):
        if ctx.author != ctx.guild.owner:
            return await ctx.reply("<:CupidXWarning:1474348304186867784> Only the server owner can restore backups.")
        
        if not await self.is_premium(ctx.guild.id):
            return await ctx.reply("<:CupidXWarning:1474348304186867784> This is a premium-only command.")

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT data FROM backups WHERE guild_id = ? AND name = ?", (ctx.guild.id, name)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply(f"Backup **{name}** not found.")
                data = json.loads(row[0])

        confirm_view = BackupConfirmView(ctx)
        confirm_embed = discord.Embed(
            title="⚠️ CRITICAL WARNING",
            description=(
                "Restoring a backup is a **destructive action**.\n"
                "The bot will attempt to **DELETE ALL** current channels and roles to recreate the saved state.\n"
                "Are you absolutely sure you want to proceed?"
            ),
            color=discord.Color.red()
        )
        msg = await ctx.reply(embed=confirm_embed, view=confirm_view)
        await confirm_view.wait()

        if confirm_view.value is not True:
            return await msg.edit(content="Restoration cancelled.", embed=None, view=None)

        await msg.edit(content="Restoration in progress... This may take a few minutes.", embed=None, view=None)

        async def safe_api(coro, delay: float = 0.6):
            max_backoff = 30.0
            retried = False
            while True:
                try:
                    result = await coro
                    await asyncio.sleep(delay)
                    return result
                except discord.HTTPException as e:
                    if e.status == 429 and not retried:
                        wait = min(float(getattr(e, "retry_after", None) or 5) + 1.0, max_backoff)
                        retried = True
                        await asyncio.sleep(wait)
                        continue
                    return None
                except Exception:
                    return None

        try:
            if data.get("icon"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(data["icon"]) as resp:
                        if resp.status == 200:
                            await safe_api(ctx.guild.edit(icon=await resp.read()))

            if data.get("banner"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(data["banner"]) as resp:
                        if resp.status == 200:
                            await safe_api(ctx.guild.edit(banner=await resp.read()))

            for channel in ctx.guild.channels:
                await safe_api(channel.delete(reason="Server Restoration"), delay=0.6)

            for role in ctx.guild.roles:
                if not role.is_default() and not role.managed and role < ctx.guild.me.top_role:
                    await safe_api(role.delete(reason="Server Restoration"), delay=0.6)

            role_map = {}
            for r_data in data["roles"]:
                new_role = await safe_api(
                    ctx.guild.create_role(
                        name=r_data["name"],
                        color=discord.Color(r_data["color"]),
                        hoist=r_data["hoist"],
                        mentionable=r_data["mentionable"],
                        permissions=discord.Permissions(r_data["permissions"]),
                        reason="Server Restoration"
                    ),
                    delay=0.7
                )
                if new_role:
                    role_map[r_data["name"]] = new_role

            def get_overwrites(ov_data):
                overwrites = {}
                for ov in ov_data:
                    if ov["type"] == "role":
                        target = role_map.get(ov["name"])
                        if target:
                            overwrites[target] = discord.PermissionOverwrite.from_pair(
                                discord.Permissions(ov["allow"]),
                                discord.Permissions(ov["deny"])
                            )
                return overwrites

            for cat_data in data["categories"]:
                category = await safe_api(
                    ctx.guild.create_category(
                        name=cat_data["name"],
                        overwrites=get_overwrites(cat_data["overwrites"]),
                        reason="Server Restoration"
                    ),
                    delay=0.7
                )
                if not category:
                    continue
                for ch_data in cat_data["channels"]:
                    if ch_data["type"] == "text":
                        await safe_api(
                            category.create_text_channel(
                                name=ch_data["name"],
                                topic=ch_data.get("topic"),
                                nsfw=ch_data.get("nsfw", False),
                                overwrites=get_overwrites(ch_data["overwrites"]),
                                reason="Server Restoration"
                            ),
                            delay=0.7
                        )
                    elif ch_data["type"] == "voice":
                        await safe_api(
                            category.create_voice_channel(
                                name=ch_data["name"],
                                bitrate=ch_data.get("bitrate"),
                                user_limit=ch_data.get("user_limit"),
                                overwrites=get_overwrites(ch_data["overwrites"]),
                                reason="Server Restoration"
                            ),
                            delay=0.7
                        )

            for ch_data in data["channels"]:
                if ch_data["type"] == "text":
                    await safe_api(
                        ctx.guild.create_text_channel(
                            name=ch_data["name"],
                            overwrites=get_overwrites(ch_data["overwrites"]),
                            reason="Server Restoration"
                        ),
                        delay=0.7
                    )
                elif ch_data["type"] == "voice":
                    await safe_api(
                        ctx.guild.create_voice_channel(
                            name=ch_data["name"],
                            overwrites=get_overwrites(ch_data["overwrites"]),
                            reason="Server Restoration"
                        ),
                        delay=0.7
                    )

        except Exception as e:
            try:
                await ctx.guild.owner.send(f"An error occurred during restoration: {e}")
            except:
                pass

async def setup(client):
    await client.add_cog(Backup(client))
