from utils import getConfig
import discord
from discord.ext import commands
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button
from utils.Tools import get_ignore_data
import aiosqlite
from utils.config import WEBSITE, SUPPORT_SERVER, BOT_INVITE

class Mention(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFCD005
        self.bot_name = "CupidX"

    async def is_blacklisted(self, message: discord.Message) -> bool:
        async with aiosqlite.connect("db/block.db") as db:
            cursor = await db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?",
                (message.guild.id,),
            )
            if await cursor.fetchone():
                return True

            cursor = await db.execute(
                "SELECT 1 FROM user_blacklist WHERE user_id = ?",
                (message.author.id,),
            )
            if await cursor.fetchone():
                return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if await self.is_blacklisted(message):
            return

        ignore_data = await get_ignore_data(message.guild.id)
        if str(message.author.id) in ignore_data["user"] or str(message.channel.id) in ignore_data["channel"]:
            return

        if message.reference and message.reference.resolved:
            if isinstance(message.reference.resolved, discord.Message):
                if message.reference.resolved.author.id == self.bot.user.id:
                    return

        data = await getConfig(message.guild.id)
        prefix = data["prefix"]

        # Only respond when just the bot is mentioned
        if self.bot.user in message.mentions and len(message.content.strip().split()) == 1:
            total_cmds = len(self.bot.commands)
            ping = round(self.bot.latency * 1000)

            desc = (
    f"### <a:emojisetting:1476854070412316713> **Elevate Your Server with CupidX**\n"
    f"Hey {message.author.mention}\nI'm your all-in-one assistant, engineered to provide **unbreakable security** and **next-gen utility** for your community.\n\n"
    f"<a:CupidXdot:1473986328126558209> **Bot Statistics**\n"
    f"> <:CupidXarrow:1474383919725150362> **Current Prefix:** `{prefix}`\n"
    f"> <:CupidXarrow:1474383919725150362> **Modules Loaded:** `{total_cmds}` commands\n"
    f"> <:CupidXarrow:1474383919725150362> **Connection:** `{ping}ms` (Ultra Fast)\n\n"
    f"<a:CupidXdot:1473986328126558209> **Featured Modules:**\n"
    f"<:arrow:1473152805853335746> Explore `Antinuke`, `Automod`, and `AI Chat` by typing **`{prefix}help`**"
)

            view = LayoutView()

            container = Container()
            container.add_item(TextDisplay(f"**{message.guild.name}**"))
            container.add_item(Separator())
            container.add_item(TextDisplay(desc))
            container.add_item(Separator())

            row = ActionRow()
            row.add_item(
                Button(
                    label="Invite",
                    style=discord.ButtonStyle.primary,
                    custom_id="mention_invite",
                )
            )
            row.add_item(
                Button(
                    label="Support",
                    style=discord.ButtonStyle.success,
                    custom_id="mention_support",
                )
            )
            row.add_item(
                Button(
                    label="Web",
                    style=discord.ButtonStyle.link,
                    url=WEBSITE,
                )
            )

            container.add_item(row)
            view.add_item(container)

            msg = await message.channel.send(view=view)

            async def invite_cb(inter: discord.Interaction):
                if inter.user.id != message.author.id:
                    await inter.response.send_message("This menu isn’t for you.", ephemeral=True)
                    return
                await inter.response.send_message(
                    f"[Invite]({BOT_INVITE}) CupidX with this link",
                    ephemeral=True,
                )

            async def support_cb(inter: discord.Interaction):
                if inter.user.id != message.author.id:
                    await inter.response.send_message("This menu isn’t for you.", ephemeral=True)
                    return
                await inter.response.send_message(
                    f"Join the [Support Server]({SUPPORT_SERVER})",
                    ephemeral=True,
                )

            row.children[0].callback = invite_cb
            row.children[1].callback = support_cb


async def setup(bot: commands.Bot):
    await bot.add_cog(Mention(bot))
))
