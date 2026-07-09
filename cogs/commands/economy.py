from __future__ import annotations

import discord
from discord.ext import commands
from discord.ext.commands import Context
import json
import os
import datetime
import random
from typing import Optional, List

from discord.ui import LayoutView, Container, TextDisplay, Separator

DB_PATH = "db"
DB_FILE = os.path.join(DB_PATH, "economy.json")

# Admin user IDs
ADMIN_IDS = [1086563807314313266, 1378341015181856768]

# Shop items
SHOP_ITEMS = {
    "apple": {"price": 50, "description": "A juicy apple. Eat to feel refreshed."},
    "sword": {"price": 1000, "description": "A small sword. Useful for roleplay or quests."},
    "lucky_ticket": {"price": 250, "description": "A ticket that increases lottery chances."},
    "energy_drink": {"price": 150, "description": "Use to reduce work cooldown."},
}

# Rewards
REWARDS = {
    "daily": 100,
    "weekly": 500,
    "monthly": 2000,
    "work_min": 50,
    "work_max": 250,
    "beg_min": 5,
    "beg_max": 60,
    "rob_success_min": 10,
    "rob_success_max": 300,
    "lottery_cost": 100,
    "lottery_reward": 5000
}

EMOJI_TICK = "<:nex_Tick:1422411439049674815>"
EMOJI_CROSS = "<:nextra_cross:1422411673544822905>"
EMOJI_DOT = "<a:dot:1443525009590194241>"

def v2_card(title: str, body: str) -> LayoutView:
    """Creates a Components v2 card with title and body text."""
    view = LayoutView()
    c = Container()
    c.add_item(TextDisplay(f"## {title}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(body))
    view.add_item(c)
    return view

def ensure_db_dir():
    if not os.path.exists(DB_PATH):
        os.makedirs(DB_PATH, exist_ok=True)

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_db_dir()
        self.file_path = DB_FILE
        self.load_data()
        self._cooldowns = {
            "work": {},
            "rob": {},
            "beg": {},
            "claim": {}
        }

    # ---------- Storage ----------
    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    self.data = json.load(f)
                if "users" not in self.data or not isinstance(self.data["users"], dict):
                    self.data["users"] = {}
            except (json.JSONDecodeError, IOError):
                self.data = {"users": {}}
        else:
            self.data = {"users": {}, "transactions": []}
            self.save_data()

    def save_data(self):
        tmp = self.file_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=4)
        os.replace(tmp, self.file_path)

    # ---------- User helpers ----------
    def _create_user_if_missing(self, user_id: str, username: Optional[str] = None):
        if user_id not in self.data["users"]:
            now = datetime.datetime.utcnow().isoformat()
            self.data["users"][user_id] = {
                "username": username or user_id,
                "registered_at": now,
                "last_claimed_daily": "",
                "last_claimed_weekly": "",
                "last_claimed_monthly": "",
                "coins": 0,
                "bank": 0,
                "inventory": [],
                "transactions": [],
                "stats": {
                    "worked": 0,
                    "begs": 0,
                    "wins": 0,
                    "losses": 0
                }
            }

    def _get_user(self, user: discord.User):
        uid = str(user.id)
        self._create_user_if_missing(uid, str(user))
        return self.data["users"][uid]

    def _record_transaction(self, uid_from: Optional[str], uid_to: Optional[str], amount: int, reason: str):
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "from": uid_from,
            "to": uid_to,
            "amount": amount,
            "reason": reason
        }
        if "transactions" not in self.data:
            self.data["transactions"] = []
        self.data["transactions"].append(entry)

    def is_admin(self, ctx: Context) -> bool:
        return ctx.author.id in ADMIN_IDS

    # ---------- Commands ----------
    @commands.command(name="economyhelp", aliases=["ecohelp"])
    async def economyhelp(self, ctx: Context):
        p = ctx.prefix
        body = (
            f"**All economy commands:**\n\n"
            f"## Basics\n"
            f"{EMOJI_DOT} `{p}register` – Register account\n"
            f"{EMOJI_DOT} `{p}balance` / `{p}bal` – Check wallet\n"
            f"{EMOJI_DOT} `{p}profile` – Show econ profile\n"
            f"{EMOJI_DOT} `{p}economyhelp` – This help\n\n"
            f"## Rewards\n"
            f"{EMOJI_DOT} `{p}daily` – {REWARDS['daily']} coins\n"
            f"{EMOJI_DOT} `{p}weekly` – {REWARDS['weekly']} coins\n"
            f"{EMOJI_DOT} `{p}monthly` – {REWARDS['monthly']} coins\n\n"
            f"## Money\n"
            f"{EMOJI_DOT} `{p}work` – Earn coins\n"
            f"{EMOJI_DOT} `{p}beg` – Small tip\n"
            f"{EMOJI_DOT} `{p}transfer @user amt` – Send coins\n"
            f"{EMOJI_DOT} `{p}deposit amt` – To bank\n"
            f"{EMOJI_DOT} `{p}withdraw amt` – From bank\n\n"
            f"## Shop\n"
            f"{EMOJI_DOT} `{p}shop` – View items\n"
            f"{EMOJI_DOT} `{p}buy item` – Purchase\n"
            f"{EMOJI_DOT} `{p}inventory` – Your items"
        )
        await ctx.reply(view=v2_card("💰 Economy Help", body))

    @commands.command(name="register")
    async def register(self, ctx: Context):
        uid = str(ctx.author.id)
        if uid in self.data["users"]:
            await ctx.reply(view=v2_card("👤 Already Registered", 
                f"{EMOJI_WARN} You already have an account, {ctx.author.mention}."))
            return

        self._create_user_if_missing(uid, str(ctx.author))
        self.save_data()
        await ctx.reply(view=v2_card("✅ Registered", 
            f"{EMOJI_TICK} {ctx.author.mention}, your economy account created!\nStarting with **0 coins**"))

    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        user = self._get_user(member)
        coins = user.get("coins", 0)
        bank = user.get("bank", 0)
        await ctx.reply(view=v2_card(f"💰 {member.display_name}'s Balance",
            f"**Wallet:** {coins} coins\n**Bank:** {bank} coins"))

    @commands.command(name="ecoprofile", aliases=["econprofile", "moneyprofile"])
    async def ecoprofile(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        u = self._get_user(member)
        body = (
            f"{EMOJI_DOT} **Username:** {u.get('username', str(member))}\n"
            f"{EMOJI_DOT} **Wallet:** {u.get('coins', 0)} coins\n"
            f"{EMOJI_DOT} **Bank:** {u.get('bank', 0)} coins\n"
            f"{EMOJI_DOT} **Registered:** {u.get('registered_at', 'Unknown')}"
        )
        await ctx.reply(view=v2_card(f"🪪 Profile – {member.display_name}", body))

    # ---------- Claim commands ----------
    @commands.command(name="daily")
    async def daily(self, ctx: Context):
        uid = str(ctx.author.id)
        user = self._get_user(ctx.author)
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        if user.get("last_claimed_daily") == today:
            await ctx.reply(view=v2_card("⏳ Daily Claim", 
                f"{EMOJI_WARN} Already claimed today."))
            return

        user["last_claimed_daily"] = today
        user["coins"] = user.get("coins", 0) + REWARDS["daily"]
        self._record_transaction(None, uid, REWARDS["daily"], "daily")
        self.save_data()
        await ctx.reply(view=v2_card("🎁 Daily Claimed", 
            f"{EMOJI_TICK} **{REWARDS['daily']}** coins!\nCome back tomorrow!"))

    @commands.command(name="weekly")
    async def weekly(self, ctx: Context):
        uid = str(ctx.author.id)
        user = self._get_user(ctx.author)
        current_week = datetime.datetime.utcnow().strftime("%Y-W%U")

        if user.get("last_claimed_weekly") == current_week:
            await ctx.reply(view=v2_card("⏳ Weekly Claim", 
                f"{EMOJI_WARN} Already claimed this week."))
            return

        user["last_claimed_weekly"] = current_week
        user["coins"] = user.get("coins", 0) + REWARDS["weekly"]
        self._record_transaction(None, uid, REWARDS["weekly"], "weekly")
        self.save_data()
        await ctx.reply(view=v2_card("🎉 Weekly Claimed", 
            f"{EMOJI_TICK} **{REWARDS['weekly']}** coins!\nGood job!"))

    @commands.command(name="monthly")
    async def monthly(self, ctx: Context):
        uid = str(ctx.author.id)
        user = self._get_user(ctx.author)
        current_month = datetime.datetime.utcnow().strftime("%Y-%m")

        if user.get("last_claimed_monthly") == current_month:
            await ctx.reply(view=v2_card("⏳ Monthly Claim", 
                f"{EMOJI_WARN} Already claimed this month."))
            return

        user["last_claimed_monthly"] = current_month
        user["coins"] = user.get("coins", 0) + REWARDS["monthly"]
        self._record_transaction(None, uid, REWARDS["monthly"], "monthly")
        self.save_data()
        await ctx.reply(view=v2_card("🏅 Monthly Claimed", 
            f"{EMOJI_TICK} **{REWARDS['monthly']}** coins!\nWell done!"))

    # ---------- Work / Beg ----------
    @commands.command(name="work")
    async def work(self, ctx: Context):
        uid = str(ctx.author.id)
        now = datetime.datetime.utcnow()
        cooldown = 60 * 30  # 30 minutes

        last = self._cooldowns["work"].get(uid)
        if last and (now - last).total_seconds() < cooldown:
            remain = int(cooldown - (now - last).total_seconds())
            await ctx.reply(view=v2_card("⏳ Work Cooldown", 
                f"{EMOJI_WARN} Wait **{remain}** seconds before working again."))
            return

        earned = random.randint(REWARDS["work_min"], REWARDS["work_max"])
        user = self._get_user(ctx.author)
        user["coins"] = user.get("coins", 0) + earned
        user["stats"]["worked"] = user["stats"].get("worked", 0) + 1
        self._cooldowns["work"][uid] = now
        self._record_transaction(None, uid, earned, "work")
        self.save_data()
        await ctx.reply(view=v2_card("💼 Work Complete", 
            f"{EMOJI_TICK} Earned **{earned}** coins!"))

    @commands.command(name="beg")
    async def beg(self, ctx: Context):
        uid = str(ctx.author.id)
        now = datetime.datetime.utcnow()
        cooldown = 60 * 5  # 5 minutes

        last = self._cooldowns["beg"].get(uid)
        if last and (now - last).total_seconds() < cooldown:
            remain = int(cooldown - (now - last).total_seconds())
            await ctx.reply(view=v2_card("⏳ Beg Cooldown", 
                f"{EMOJI_WARN} Wait **{remain}** seconds before begging again."))
            return

        gained = random.randint(REWARDS["beg_min"], REWARDS["beg_max"])
        user = self._get_user(ctx.author)
        user["coins"] = user.get("coins", 0) + gained
        user["stats"]["begs"] = user["stats"].get("begs", 0) + 1
        self._cooldowns["beg"][uid] = now
        self._record_transaction(None, uid, gained, "beg")
        self.save_data()
        await ctx.reply(view=v2_card("🙏 Beg Result", 
            f"{EMOJI_TICK} Someone gave you **{gained}** coins!"))

    # ---------- Transfer / Bank ----------
    @commands.command(name="transfer")
    async def transfer(self, ctx: Context, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be greater than 0."))
            return

        sender = self._get_user(ctx.author)
        receiver = self._get_user(member)

        if sender.get("coins", 0) < amount:
            await ctx.reply(view=v2_card("❌ Insufficient Funds", 
                f"{EMOJI_CROSS} Not enough coins to transfer."))
            return

        sender["coins"] -= amount
        receiver["coins"] += amount
        self._record_transaction(str(ctx.author.id), str(member.id), amount, "transfer")
        self.save_data()
        await ctx.reply(view=v2_card("💸 Transfer Complete", 
            f"{EMOJI_TICK} Sent **{amount}** coins to {member.mention}."))

    @commands.command(name="deposit")
    async def deposit(self, ctx: Context, amount: str):
        user = self._get_user(ctx.author)
        coins = user.get("coins", 0)

        if amount.lower() == "all":
            amt = coins
        else:
            try:
                amt = int(amount)
            except ValueError:
                await ctx.reply(view=v2_card("❌ Invalid Amount", 
                    f"{EMOJI_CROSS} Provide a number or 'all'."))
                return

        if amt <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be greater than 0."))
            return

        if coins < amt:
            await ctx.reply(view=v2_card("❌ Not Enough Coins", 
                f"{EMOJI_CROSS} Not enough wallet coins."))
            return

        user["coins"] -= amt
        user["bank"] = user.get("bank", 0) + amt
        self._record_transaction(str(ctx.author.id), str(ctx.author.id), amt, "deposit")
        self.save_data()
        await ctx.reply(view=v2_card("🏦 Deposit Successful", 
            f"{EMOJI_TICK} Deposited **{amt}** coins to bank."))

    @commands.command(name="withdraw")
    async def withdraw(self, ctx: Context, amount: str):
        user = self._get_user(ctx.author)
        bank = user.get("bank", 0)

        if amount.lower() == "all":
            amt = bank
        else:
            try:
                amt = int(amount)
            except ValueError:
                await ctx.reply(view=v2_card("❌ Invalid Amount", 
                    f"{EMOJI_CROSS} Provide a number or 'all'."))
                return

        if amt <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be greater than 0."))
            return

        if bank < amt:
            await ctx.reply(view=v2_card("❌ Not Enough Bank Coins", 
                f"{EMOJI_CROSS} Not enough bank coins."))
            return

        user["bank"] -= amt
        user["coins"] = user.get("coins", 0) + amt
        self._record_transaction(str(ctx.author.id), str(ctx.author.id), amt, "withdraw")
        self.save_data()
        await ctx.reply(view=v2_card("🏧 Withdraw Successful", 
            f"{EMOJI_TICK} Withdrew **{amt}** coins to wallet."))

    @commands.command(name="bank")
    async def bank(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        user = self._get_user(member)
        await ctx.reply(view=v2_card(f"🏦 {member.display_name}'s Bank",
            f"**Wallet:** {user.get('coins', 0)} coins\n**Bank:** {user.get('bank', 0)} coins"))

    # ---------- Shop / Inventory ----------
    @commands.command(name="shop")
    async def shop(self, ctx: Context):
        lines = []
        for key, v in SHOP_ITEMS.items():
            lines.append(f"{EMOJI_DOT} **{key.capitalize()}** – {v['price']} coins\n   {v['description']}")
        body = "\n".join(lines) + f"\n\nUse `{ctx.prefix}buy <item>`"
        await ctx.reply(view=v2_card("🏪 Shop", body))

    @commands.command(name="buy")
    async def buy(self, ctx: Context, item_name: str):
        item_name = item_name.lower()
        if item_name not in SHOP_ITEMS:
            await ctx.reply(view=v2_card("❌ Item Not Found", 
                f"{EMOJI_CROSS} Item does not exist in shop."))
            return

        user = self._get_user(ctx.author)
        price = SHOP_ITEMS[item_name]["price"]

        if user.get("coins", 0) < price:
            await ctx.reply(view=v2_card("❌ Not Enough Coins", 
                f"{EMOJI_CROSS} Need **{price}** coins for {item_name}."))
            return

        user["coins"] -= price
        if "inventory" not in user:
            user["inventory"] = []
        user["inventory"].append(item_name)
        self._record_transaction(None, str(ctx.author.id), price, f"buy:{item_name}")
        self.save_data()
        await ctx.reply(view=v2_card("🛒 Purchase Successful", 
            f"{EMOJI_TICK} Bought **{item_name.capitalize()}** for **{price}** coins."))

    @commands.command(name="sell")
    async def sell(self, ctx: Context, item_name: str):
        item_name = item_name.lower()
        user = self._get_user(ctx.author)
        inventory = user.get("inventory", [])

        if item_name not in inventory:
            await ctx.reply(view=v2_card("❌ Item Not In Inventory", 
                f"{EMOJI_CROSS} You don't own that item."))
            return

        price = SHOP_ITEMS.get(item_name, {}).get("price", 0)
        sell_price = max(1, int(price * 0.5))
        inventory.remove(item_name)
        user["coins"] = user.get("coins", 0) + sell_price
        self._record_transaction(str(ctx.author.id), None, sell_price, f"sell:{item_name}")
        self.save_data()
        await ctx.reply(view=v2_card("💱 Sold Item", 
            f"{EMOJI_TICK} Sold **{item_name.capitalize()}** for **{sell_price}** coins."))

    @commands.command(name="inventory")
    async def inventory(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        user = self._get_user(member)
        items = user.get("inventory", [])

        if not items:
            await ctx.reply(view=v2_card("🎒 Inventory Empty", 
                f"{EMOJI_WARN} No items. Visit shop to buy some!"))
            return

        lines = []
        for i in items:
            desc = SHOP_ITEMS.get(i, {}).get("description", "No description.")
            lines.append(f"{EMOJI_DOT} **{i.capitalize()}**\n   {desc}")
        await ctx.reply(view=v2_card(f"🎒 {member.display_name}'s Inventory", "\n".join(lines)))

    @commands.command(name="use")
    async def use(self, ctx: Context, item_name: str):
        item_name = item_name.lower()
        user = self._get_user(ctx.author)
        inv = user.get("inventory", [])

        if item_name not in inv:
            await ctx.reply(view=v2_card("❌ Item Not Found", 
                f"{EMOJI_CROSS} You don't own that item."))
            return

        if item_name == "energy_drink":
            inv.remove(item_name)
            self._cooldowns["work"].pop(str(ctx.author.id), None)
            self.save_data()
            await ctx.reply(view=v2_card("⚡ Energy Drink Used", 
                f"{EMOJI_TICK} Work cooldown reset!"))
            return

        elif item_name == "lucky_ticket":
            inv.remove(item_name)
            bonus = 200
            user["coins"] = user.get("coins", 0) + bonus
            self._record_transaction(None, str(ctx.author.id), bonus, "lucky_ticket_bonus")
            self.save_data()
            await ctx.reply(view=v2_card("🎟️ Lucky Ticket", 
                f"{EMOJI_TICK} Redeemed for **{bonus}** coins!"))
            return

        else:
            inv.remove(item_name)
            self.save_data()
            await ctx.reply(view=v2_card("✅ Item Used", 
                f"{EMOJI_TICK} Used **{item_name}**."))

    # ---------- Gambling / Lottery ----------
    @commands.command(name="gamble")
    async def gamble(self, ctx: Context, amount: int):
        if amount <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be greater than 0."))
            return

        user = self._get_user(ctx.author)
        if user.get("coins", 0) < amount:
            await ctx.reply(view=v2_card("❌ Insufficient Funds", 
                f"{EMOJI_CROSS} Not enough coins to gamble."))
            return

        outcome = random.choice(["win", "lose"])
        if outcome == "win":
            user["coins"] += amount
            user["stats"]["wins"] = user["stats"].get("wins", 0) + 1
            self._record_transaction(None, str(ctx.author.id), amount, "gamble_win")
            self.save_data()
            await ctx.reply(view=v2_card("🎉 Gamble Win", 
                f"{EMOJI_TICK} Won **{amount}** coins!"))
        else:
            user["coins"] -= amount
            user["stats"]["losses"] = user["stats"].get("losses", 0) + 1
            self._record_transaction(str(ctx.author.id), None, amount, "gamble_loss")
            self.save_data()
            await ctx.reply(view=v2_card("😢 Gamble Loss", 
                f"{EMOJI_CROSS} Lost **{amount}** coins.\nBetter luck next time!"))

    @commands.command(name="lottery")
    async def lottery(self, ctx: Context):
        user = self._get_user(ctx.author)
        cost = REWARDS["lottery_cost"]

        if user.get("coins", 0) < cost:
            await ctx.reply(view=v2_card("❌ Cannot Enter Lottery", 
                f"{EMOJI_CROSS} Need **{cost}** coins to enter."))
            return

        user["coins"] -= cost
        win = random.randint(1, 50) == 1

        if win:
            reward = REWARDS["lottery_reward"]
            user["coins"] += reward
            self._record_transaction(None, str(ctx.author.id), reward, "lottery_win")
            self.save_data()
            await ctx.reply(view=v2_card("🎊 Lottery Winner!", 
                f"{EMOJI_TICK} Congratulations!\nWon **{reward}** coins!"))
        else:
            self._record_transaction(str(ctx.author.id), None, cost, "lottery_ticket")
            self.save_data()
            await ctx.reply(view=v2_card("🎟️ Lottery Entry", 
                f"{EMOJI_WARN} No win this time.\nBetter luck next draw!"))

    # ---------- Leaderboard & Stats ----------
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx: Context):
        entries = []
        for uid, u in self.data["users"].items():
            try:
                uid_int = int(uid)
            except:
                continue
            member = ctx.guild.get_member(uid_int)
            if member:
                entries.append((member.display_name, u.get("coins", 0)))

        entries.sort(key=lambda x: x[1], reverse=True)
        top = entries[:10]

        if not top:
            await ctx.reply(view=v2_card("🏆 Leaderboard", 
                f"{EMOJI_WARN} No registered users found."))
            return

        lines = [f"{i+1}. **{name}** – {amt} coins" for i, (name, amt) in enumerate(top)]
        await ctx.reply(view=v2_card("🏆 Leaderboard – Top Wallets", "\n".join(lines)))

    @commands.command(name="economystats")
    async def stats(self, ctx: Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        u = self._get_user(member)
        s = u.get("stats", {})
        body = (
            f"{EMOJI_DOT} **Worked:** {s.get('worked', 0)} times\n"
            f"{EMOJI_DOT} **Begs:** {s.get('begs', 0)}\n"
            f"{EMOJI_DOT} **Wins:** {s.get('wins', 0)}\n"
            f"{EMOJI_DOT} **Losses:** {s.get('losses', 0)}"
        )
        await ctx.reply(view=v2_card(f"📊 Stats – {member.display_name}", body))

    # ---------- Transactions ----------
    @commands.command(name="transactions")
    async def transactions(self, ctx: Context, limit: int = 10):
        if "transactions" not in self.data or not self.data["transactions"]:
            await ctx.reply(view=v2_card("📜 Transactions", 
                f"{EMOJI_WARN} No transactions recorded yet."))
            return

        recent = self.data["transactions"][-limit:]
        lines = []
        for t in reversed(recent):
            ts = t.get("timestamp", "unknown")[:10]
            frm = t.get("from") or "SYSTEM"
            to = t.get("to") or "SYSTEM"
            amt = t.get("amount", 0)
            reason = t.get("reason", "")
            lines.append(f"`{ts}` {frm} → {to}: **{amt}** ({reason})")

        await ctx.reply(view=v2_card("📜 Recent Transactions", "\n".join(lines)))

    # ---------- Admin Commands ----------
    @commands.command(name="addcoins")
    async def addcoins(self, ctx: Context, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        if amount <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be > 0."))
            return

        u = self._get_user(member)
        u["coins"] = u.get("coins", 0) + amount
        self._record_transaction(None, str(member.id), amount, "admin_add")
        self.save_data()
        await ctx.reply(view=v2_card("✅ Added Coins", 
            f"{EMOJI_TICK} Added **{amount}** coins to {member.mention}."))

    @commands.command(name="removecoins")
    async def removecoins(self, ctx: Context, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        if amount <= 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be > 0."))
            return

        u = self._get_user(member)
        if u.get("coins", 0) < amount:
            await ctx.reply(view=v2_card("❌ Not Enough Coins", 
                f"{EMOJI_CROSS} User doesn't have enough coins."))
            return

        u["coins"] -= amount
        self._record_transaction(str(member.id), None, amount, "admin_remove")
        self.save_data()
        await ctx.reply(view=v2_card("✅ Removed Coins", 
            f"{EMOJI_TICK} Removed **{amount}** coins from {member.mention}."))

    @commands.command(name="setcoins")
    async def setcoins(self, ctx: Context, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        if amount < 0:
            await ctx.reply(view=v2_card("❌ Invalid Amount", 
                f"{EMOJI_CROSS} Amount must be >= 0."))
            return

        u = self._get_user(member)
        u["coins"] = amount
        self._record_transaction(None, str(member.id), amount, "admin_set")
        self.save_data()
        await ctx.reply(view=v2_card("✅ Set Coins", 
            f"{EMOJI_TICK} Set {member.mention}'s coins to **{amount}**."))

    @commands.command(name="resetuser")
    async def resetuser(self, ctx: Context, member: discord.Member):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        uid = str(member.id)
        if uid in self.data["users"]:
            self.data["users"].pop(uid)
            self.save_data()
            await ctx.reply(view=v2_card("♻️ User Reset", 
                f"{EMOJI_TICK} Reset economy data for {member.mention}."))
        else:
            await ctx.reply(view=v2_card("❌ Not Found", 
                f"{EMOJI_CROSS} User has no economy data."))

    @commands.command(name="clearleaderboard")
    async def clearleaderboard(self, ctx: Context):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        for u in self.data["users"].values():
            u["coins"] = 0
        self.save_data()
        await ctx.reply(view=v2_card("🧹 Leaderboard Cleared", 
            f"{EMOJI_TICK} All wallet coins set to 0."))

    # ---------- Game Integration ----------
    @commands.command(name="gamebonus")
    async def gamebonus(self, ctx: Context, game_name: str, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            await ctx.reply(view=v2_card("🔒 Admin Only", 
                f"{EMOJI_CROSS} Restricted to bot admins."))
            return

        if amount <= 0:
            await ctx.reply(view=v2_card("❌ Invalid", 
                f"{EMOJI_CROSS} Amount must be > 0."))
            return

        user = self._get_user(member)
        user["coins"] = user.get("coins", 0) + amount
        self._record_transaction(None, str(member.id), amount, f"gamebonus:{game_name}")
        self.save_data()
        await ctx.reply(view=v2_card("🎮 Game Bonus", 
            f"{EMOJI_TICK} Granted **{amount}** coins to {member.mention}\nfor **{game_name}**."))

    @commands.command(name="about")
    async def about(self, ctx: Context):
        body = (
            f"{EMOJI_DOT} **Currency:** coins 💰\n"
            f"{EMOJI_DOT} **Storage:** {self.file_path}"
        )
        await ctx.reply(view=v2_card("ℹ️ Economy System", body))

    def cog_unload(self):
        try:
            self.save_data()
        except Exception:
            pass

def setup(bot: commands.Bot):
    bot.add_cog(Economy(bot))

async def async_setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
