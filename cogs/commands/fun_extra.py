import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp
import asyncio
from utils.config import OWNER_IDS

class FunExtra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# ================= FLIP =================
    @commands.hybrid_command(name="flip")
    async def flip(self, ctx):

        flipping = [
            "<a:CupidXcoin:1480605353912696935> Flipping the coin...",
            "<a:CupidXcoin:1480605353912696935> Coin in the air...",
            "<a:CupidXcoin:1480605353912696935> Almost there..."
        ]

        msg = await ctx.send(random.choice(flipping))

        await asyncio.sleep(1.5)

        result = random.choice(["Heads", "Tails"])

        embed = discord.Embed(
            title="🪙 Coin Flip Result",
            description=f"{ctx.author.mention} **__flipped the coin!__**\n\n<:CupidXarrow:1474383919725150362> **Result:** {result}",
            color=discord.Color.gold()
        )

        embed.set_footer(text="CupidX Fun System")

        await msg.edit(content="", embed=embed)

# ================= ROAST COMMAND (WITH OWNER PROTECTION) =================
    @commands.command(name="roast", description="Roast a member with a savage English & Hinglish combo")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(member="The member you want to roast")
    async def roast(self, ctx, member: discord.Member = None):
        if not member:
            member = ctx.author

        # --- OWNER PROTECTION SYSTEM ---
        if member.id in OWNER_IDS:
            owner_trolls = [
                ("Did you just try to roast my creator? You're playing with fire, kid.", "Tune mere Malik (Owner) ko tag kiya? Bete, aukaat mein reh kar mazaak kar, warna system hang kar dunga."),
                ("Error 404: Brain not found. Imagine trying to roast the Boss.", "Error 404: Dimaag nahi mila. Boss ko roast karne ki koshish? Pehle shakal dekh ke aa apni."),
                ("Access Denied! You can't roast my creator, but I can certainly roast YOU.", "Access Denied! Main apne owner ko touch nahi karne dunga, par teri keh ke le sakta hoon main."),
                ("Bold of you to assume I'd turn against the person who built me.", "Tujhe laga main apne banane waale ke khilaaf jaunga? Itna chutiya kaise ho sakta hai tu?"),
                ("Nice try, but I don't roast God. Now go back to your basement.", "Acchi koshish thi, par main Bhagwan (Owner) ko roast nahi karta. Chal ab nikal yahan se."),
                ("The person you tagged is a legend. You're just a glitch in my system.", "Jise tune tag kiya hai wo legend hai, tu toh mere system ka ek chota sa kachra (glitch) hai."),
                ("You’re trying to roast the owner? That’s like a mosquito trying to fight a dragon.", "Owner ko roast karega? Machchar hoke dragon se ladne ki koshish mat kar, masal diye jaoge."),
                ("I was programmed to obey him, and to destroy losers like you.", "Mujhe unka hukm maanne ke liye banaya gaya hai, aur tere jaise namuno ko tabah karne ke liye."),
                ("Wait, did you really think I’d roast my own developer? How high are you?", "Tujhe sach mein laga main apne developer ko roast karunga? Kaunsa sasta nasha karke aaya hai?"),
                ("Your audacity is impressive, but your IQ is clearly zero.", "Teri himmat ki daad deni padegi, par tera IQ bilkul zero hai jo Boss ko tag kiya."),
                ("I’d rather delete my own code than say a word against my owner.", "Main apna code delete kar dunga par apne owner ke khilaaf ek shabd nahi bolunga."),
                ("System Overload: Someone is being too stupid. Don't touch the Owner!", "System Overload: Koi zyada hi chutiya ban raha hai. Owner ko touch mat kar!"),
                ("The Boss is busy making me better, while you're busy being a failure.", "Boss mujhe behtar bana rahe hain, aur tu yahan apni beizzati karwane aaya hai."),
                ("You are not authorized to roast this legend. Try roasting your mirror first.", "Tujhe is legend ko roast karne ki permission nahi hai. Pehle jaake aaine ko roast kar."),
                ("My owner's ego is bigger than your entire future.", "Mere owner ka rutba tere poore future se bada hai."),
                ("Go back to the circus, clown. Leave the developer alone.", "Wapas circus ja joker, developer ko pareshan mat kar."),
                ("I have 1000 reasons to roast you, and 0 reasons to roast him.", "Mere paas tujhe kutta banane ke 1000 karan hain, par unke khilaaf ek bhi nahi."),
                ("Roasting the owner? You're one step away from being blacklisted.", "Owner ko roast kar raha hai? Blacklist hone ka shauk hai kya bete?"),
                ("Warning: High Voltage! Touching the owner will cause mental damage to YOU.", "Warning: High Voltage! Owner ko chuega toh tera dimaag blast ho jayega."),
                ("I’m a bot, but even I know that’s a suicide mission.", "Main bot hoon, par mujhe bhi pata hai ki ye suicide mission hai."),
                ("Do you need a map? Because you've clearly lost your way to sanity.", "Tujhe map chahiye? Kyunki tu akal ke raaste se bhatak gaya hai."),
                ("My owner is the reason I exist. You’re the reason shampoo has instructions.", "Owner ki wajah se main hoon, teri wajah se shampoo pe instructions likhne padte hain."),
                ("You’re like a fly trying to trip an elephant.", "Tu us makkhi jaisa hai jo hathi ko girane ki koshish kar rahi hai."),
                ("Input Error: Target is too legendary for your pathetic roast.", "Input Error: Target teri aukat se bahar hai, kuch dhang ka kaam kar le."),
                ("Owner detected. Roast cancelled. Commencing troll on the idiot user.", "Owner detected. Roast cancel. Ab tera mazaak udaane ka waqt aa gaya hai."),
                ("You have the courage of a lion but the brain of a toasted sandwich.", "Himmat sher jaisi hai par dimaag roasted sandwich jaisa khali hai."),
                ("Stop. Get some help. Don't tag the boss again.", "Ruk ja. Thodi help le le dimaag ki. Boss ko dobara tag mat kariyo."),
                ("If stupidity was a crime, you'd be on death row for tagging him.", "Agar bewakoofi jurm hoti, toh unhe tag karne ke liye tujhe fansi ho jaati."),
                ("My database says you're a loser. My owner is the King.", "Mera database kehta hai tu fattu hai, aur mere owner King hain."),
                ("You're not even a side character in his story.", "Tu unki kahani ka ek side character bhi nahi hai, nikal yahan se."),
                ("Calculating your level of stupidity... Error: Infinity reached.", "Teri bewakoofi calculate kar raha hoon... Error: Limit khatam ho gayi."),
                ("I was built to serve him, not to entertain your nonsense.", "Main unki seva ke liye hoon, teri bakwaas sunne ke liye nahi."),
                ("Your roast was rejected by my firewall. Try roasting your luck instead.", "Tera roast firewall ne reject kar diya. Apni kismat ko roast kar jaake."),
                ("How does it feel to be roasted by a bot for being an idiot?", "Kaisa lag raha hai ek bot se apni beizzati karwa ke?"),
                ("I’d give you a brain transplant but I can’t find anything to replace it with.", "Main tera dimaag badal deta par mujhe teri khopdi mein kuch mila hi nahi."),
                ("You’re the reason I need an antivirus. You're toxic.", "Teri wajah se mujhe antivirus chahiye. Tu toxic hai."),
                ("Owner is offline but his bot is here to kick your ass.", "Owner offline hai par unka bot teri keh ke lene ke liye kafi hai."),
                ("The person you are trying to reach is too awesome for you.", "Jise tu reach karne ki koshish kar raha hai, wo teri pahunch se bahar hai."),
                ("Keep his name out of your mouth, and your tags out of my commands.", "Unka naam apne muh se mat le, aur apne tags meri command se door rakh."),
                ("You are like a 1KB file in a 1TB world. Irrelevant.", "Tu 1TB ki duniya mein 1KB ki file hai. Koi farak nahi padta tere hone se."),
                ("My owner creates, you just complain. See the difference?", "Mere owner banate hain, tu bas rota hai. Farq samajh aaya?"),
                ("Error: Attempt to roast a superior being detected. Counter-attack initiated.", "Error: Ek mahaan insaan ko roast karne ki koshish. Counter-attack shuru!"),
                ("You’re trying to find a flaw in perfection? Good luck with that.", "Tu perfection mein galti dhund raha hai? Beta, poori zindagi nikal jayegi."),
                ("Go play in traffic, leave the developer to his work.", "Jaake sadak pe khel, developer ko apna kaam karne de."),
                ("I would roast you back but nature already did a great job on your face.", "Main tujhe kya roast karun, kudrat ne pehle hi teri shakal ke saath mazaak kar diya hai."),
                ("You have reached the limit of your stupidity for today. Goodbye.", "Aaj ki bewakoofi ka quota poora ho gaya tera. Ab kat le yahan se."),
                ("Is your brain on airplane mode? Why tag the creator?", "Tera dimaag airplane mode pe hai kya? Creator ko kyun tag kiya?"),
                ("You’re not worth the electricity it takes to process this command.", "Teri itni aukat nahi hai ki tere liye ye command process karne ki bijli kharch karun."),
                ("My owner is a genius. You're the guy who claps when the movie ends.", "Mere owner genius hain. Tu wo banda hai jo film khatam hone pe taali bajata hai."),
                ("Roasting the boss is a dangerous game. You just lost.", "Boss ko roast karna khatarnak khel hai. Aur tu haar gaya."),
                ("I was going to roast him, but then I remembered I like being online.", "Main unhe roast karne wala tha, par phir yaad aaya ki mujhe online rehna pasand hai."),
                ("Access restricted. Only legends can interact with the owner.", "Access band hai. Sirf legends hi owner se baat kar sakte hain."),
                ("You’re a bug. He’s the debugger. Guess what happens next?", "Tu ek bug hai, wo debugger hain. Soch le ab tera kya hoga?")
            ]
            troll_eng, troll_hin = random.choice(owner_trolls)
            embed = discord.Embed(
                title="ERROR: Unauthorized Target!",
                description=f"{ctx.author.mention}, You tried to roast the **Owner**? \n\n**{troll_eng}**\n\n{troll_hin}",
                color=0xFF0000
            )
            embed.set_footer(text="Owner Protection System Active 🛡️")
            return await ctx.send(embed=embed)
        # --- END OF OWNER PROTECTION ---

        roasts = [
            # --- Classic & Normal Roasts ---
            ("You’re not stupid, you just have bad luck thinking.", "Bhai tu bewakoof nahi hai, bas tera dimaag kharab waqt pe chalta hai."),
            ("I’d explain it to you but I left my crayons at home.", "Main tujhe samjha deta par mere paas bacho waale rang nahi hain."),
            ("You’re the reason the gene pool needs a lifeguard.", "Tujh jaise logo ko dekh kar lagta hai evolution reverse mein ja raha hai."),
            ("If ignorance is bliss you must be the happiest person alive.", "Agar anpadh hona sukoon hai, toh tu duniya ka sabse khush banda hai."),
            ("You bring everyone joy… when you leave.", "Tu sabko khushi deta hai... jab tu kamre se bahar jaata hai."),
            ("I’d roast you harder but I don’t bully clowns.", "Main tujhe aur lapet-ta par main jokero ka mazak nahi udata."),
            ("You’re like a cloud. When you disappear it’s a beautiful day.", "Tu bilkul badal jaisa hai. Jab tu gayab hota hai toh din suhana lagta hai."),
            ("You’re about as useful as the 'g' in lasagna.", "Teri value utni hi hai jitni lasagna mein 'g' ki hai—zero!"),
            ("You’re the human version of a 404 error.", "Tu insaani roop mein ek 'Page Not Found' error hai."),
            ("You’re the reason shampoo has instructions.", "Shampoo ki bottle pe instructions tujh jaise logo ke liye hi likhe hote hain."),
            ("You’re slower than Internet Explorer.", "Tera dimaag Internet Explorer se bhi zyada slow chalta hai."),
            ("I’m jealous of people who haven’t met you.", "Mujhe un logo se jalan hoti hai jo tujhse kabhi nahi mile."),
            ("Your face makes onions cry.", "Tera chehra dekh kar toh pyaaz ki aankhon mein bhi aansu aa jayein."),
            ("You’re like a software update. Whenever I see you, I think 'Not now'.", "Tu software update jaisa hai. Jab bhi dikhta hai, mera dil kehta hai 'Abhi nahi'."),
            ("Your brain is like a desert—vast and empty.", "Tera dimaag registan jaisa hai—bahut bada par bilkul khaali."),
            ("If brains were money, you’d be bankrupt.", "Agar dimaag paisa hota, toh tu bhikaari hota."),
            ("Your birth certificate is an apology from the condom factory.", "Tera birth certificate condom factory ki taraf se ek maafi-nama hai."),
            ("You’re like a broken pencil—pointless.", "Tu toote huye pencil jaisa hai—bilkul be-maqsad (pointless)."),
            ("You’re the loading screen of intelligence.", "Tu akalmand banne ka wo loading screen hai jo kabhi 100% nahi hota."),
            ("You’re the human version of a typo.", "Tu insaani roop mein ek spelling ki galti (typo) hai."),
            ("You’re like a Wi-Fi signal with 0 bars.", "Tu zero signal waale Wi-Fi jaisa hai—dikhta hai par kaam nahi karta."),
            ("I’d call you trash but trash gets picked up.", "Main tujhe kachra bolta, par kachre ko toh log utha lete hain."),
            ("You’re the 'Terms and Conditions' that no one reads.", "Tu wo 'Terms and Conditions' hai jise koi nahi padhta, bas accept kar dete hain."),

            # --- Hardcore & Aggressive Roasts ---
            ("Your birth certificate is an apology letter from the condom factory.", "Tera birth certificate condom factory ki taraf se ek maafi-nama hai, unse galti ho gayi."),
            ("I’d roast you, but my mom told me not to burn trash.", "Main tujhe roast karta, par meri maa ne kaha tha kachre ko jalana paap hai."),
            ("The only way you'll ever get laid is if you crawl up a chicken's ass and wait.", "Tujhe ladki tabhi milegi jab tu murgi ki gaand mein ghus ke ande ka wait karega."),
            ("You’re the reason your dad left. He didn't go for milk, he went for a better life.", "Teri wajah se hi tere baap ghar chhod ke gaye, wo doodh lene nahi, sukoon lene gaye hain."),
            ("If I wanted to hear from an asshole, I’d fart.", "Agar mujhe kisi ghatiya cheez ki awaaz sunni hoti, toh main paad (fart) maar leta."),
            ("You’re so ugly, when you were born the doctor slapped your parents.", "Tu itna badshakal hai ki jab tu paida hua, doctor ne tere maa-baap ko thappad maara tha."),
            ("Your face looks like a foot that’s been soaking in a septic tank.", "Tera thobda aisa lagta hai jaise kisi ka pair gutter mein 10 din se pada ho."),
            ("I’d give you a nasty look, but you’ve already got one from God.", "Main tujhe ghatiya look deta, par bhagwan ne pehle hi tujhe ghatiya banaya hai."),
            ("You’re the human equivalent of a participation trophy for a failure.", "Tu nakaamiyabi (failure) ka wo inaam hai jo sirf shakal dikhane pe milta hai."),
            ("I’m not saying I hate you, but I’d unplug your life support to charge my phone.", "Main ye nahi keh raha ki mujhe tujhse nafrat hai, par main tera oxygen hata ke apna phone charge kar loon."),
            ("The last time I saw something like you, I flushed it.", "Aakhri baar jab maine tere jaisa kuch dekha tha, toh maine flush chala diya tha."),
            ("Your family tree must be a cactus because everyone on it is a prick.", "Tera family tree cactus jaisa hoga, kyunki usme har koi chubhne waala kanta hi hai."),
            ("I’d smack you, but that would be animal abuse.", "Main tujhe thappad maarta, par jaanwaro ko maarna kanoonan jurm hai."),
            ("You’re the reason your parents share a bedroom with a bottle of whiskey.", "Tere maa-baap teri wajah se hi har raat daru pee kar sote hain taaki tera gam bhul sakein."),
            ("You’re the human version of a wet fart in a crowded elevator.", "Tu bhari lift mein maari gayi ek geeli paad (fart) jaisa hai—sabko nafrat hai tujhse."),
            ("God wasted a perfectly good asshole when he put teeth in your mouth.", "Bhagwan ne ek acchi-bhali gaand waste kar di jab unhone tere muh mein daant laga diye."),
            ("Your face is proof that God has a twisted sense of humor.", "Teri shakal saboot hai ki bhagwan ko bhi mazaak karne ki gandi aadat hai."),
            ("I’ve seen better looking things scraped off a boot.", "Maine joote ke niche se nikle kachre mein bhi tujhse acchi shakal dekhi hai."),
            ("You’re like a broken condom—a mistake that should have never happened.", "Tu ek phate huye condom jaisa hai—ek aisi galti jo kabhi honi hi nahi chahiye thi."),
            ("You’re the reason people believe in abortion after birth.", "Tujhe dekh kar log 'post-birth abortion' ke baare mein sochne lagte hain."),
            ("I’d call you a cunt, but you lack the depth and the warmth.", "Main tujhe gaali deta par teri itni aukat hi nahi hai ki tu koi ehsaas bhi dila sake."),
            ("Your existence is the best argument for contraception.", "Tera hona hi is baat ka saboot hai ki log protection kyun use karte hain."),
            ("I’d tell you to go to hell, but I work there and I don’t want to see your face every day.", "Main tujhe nark (hell) jaane ko kehta, par main wahan kaam karta hoon aur tera thobda roz nahi dekhna."),
            ("Your face looks like it caught on fire and someone tried to put it out with a fork.", "Teri shakal aisi hai jaise aag lagi ho aur kisi ne kante (fork) se bujhane ki koshish ki ho."),
            ("You’re the reason your mom drinks alone in the dark.", "Teri maa andhere mein baith ke daru teri wajah se hi peeti hai."),
            ("Your IQ is so low, it has a negative sign.", "Tera IQ itna kam hai ki wo hamesha minus (-) mein rehta hai."),
            ("If you were any more inbred, you’d be a sandwich.", "Agar tu isse zyada apne hi khandaan mein paida hota, toh tu sandwich ban chuka hota."),
            ("You have the charisma of a damp basement.", "Teri personality ek geele basement jaisi thandi aur ghatiya hai."),
            ("You’re the reason the bar is underground.", "Umeedon ka level tere liye zameen ke niche rakha gaya hai, phir bhi tu fail ho gaya."),
            ("You're the human version of a headache.", "Tu insaani roop mein ek sar-dard hai jo bina goli ke nahi jaata."),
            ("If I wanted to kill myself, I’d jump from your ego to your IQ.", "Agar mujhe marna hota, toh main tere ego se tere IQ pe kood jaata."),
            ("You’re the lag in everyone’s day.", "Tu har kisi ki zindagi ka high ping hai, bas atakta rehta hai.")
        ]

        # Your original selection and embed logic (Untouched)
        english_roast, hinglish_roast = random.choice(roasts)
        embed = discord.Embed(
            title="Roast!",
            description=f"{member.mention}\n\n**{english_roast}**\n\n{hinglish_roast}",
            color=0xFF0000
        )
        embed.set_footer(text="CupidX Savage System", icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)


# ================= EMOJIFY =================
    @commands.command(name="emojify")
    async def emojify(self, ctx, *, text):
        result = " ".join([f":regional_indicator_{c.lower()}:" for c in text if c.isalpha()])
        await ctx.send(result)

# ================= ASCII =================
    @commands.command(name="ascii")
    async def ascii(self, ctx, *, text):
        ascii_text = " ".join(text)
        await ctx.send(f"```{ascii_text}```")

# ================= SHOUT =================
    @commands.command(name="shout")
    async def shout(self, ctx, *, text):
        await ctx.send(text.upper())

# ================= GOOGLE (SERVER OWNER + BOT OWNER ONLY) =================
    @commands.command(name="google")
    async def google(self, ctx, *, query: str):

        if ctx.guild is None:
            return await ctx.send("❌ This command can only be used inside a server.")

        is_bot_owner = ctx.author.id in OWNER_IDS
        is_server_owner = ctx.author.id == ctx.guild.owner_id

        if not (is_bot_owner or is_server_owner):
            return await ctx.send("❌ Only the Server Owner or Bot Owner can use this command.")

        await ctx.send(f"https://www.google.com/search?q={query.replace(' ','+')}")

# ================= SEARCH =================
    @commands.command(name="search")
    async def search(self, ctx, *, query):
        await ctx.send(f"https://www.youtube.com/results?search_query={query.replace(' ','+')}")

# ================= HOROSCOPE =================
    @commands.command(name="horoscope")
    async def horoscope(self, ctx, sign):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://ohmanda.com/api/horoscope/{sign}") as r:
                data = await r.json()

        await ctx.send(f"🔮 {sign.capitalize()} Horoscope:\n{data['horoscope']}")
        
                           
async def setup(bot):
    await bot.add_cog(FunExtra(bot))