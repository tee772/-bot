import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

WORD_CACHE = {"A0": [], "A1": [], "A2": [], "B1": [], "B2": []}
USED_WORDS = set()

# ตั้งค่าเกณฑ์ความยาก ความยาว และค่าความถี่การใช้คำ (Frequency) ให้ตรงตาม CEFR
LEVEL_CONFIG = {
    "A0": {
        "min_len": 2, "max_len": 4, 
        "min_freq": 20.0,  # บังคับเฉพาะคำที่ใช้บ่อยมากๆ ในภาษาอังกฤษ
        "topics": ["cat", "dog", "red", "boy", "sun", "car", "pen", "hat", "cup", "run"]
    },
    "A1": {
        "min_len": 4, "max_len": 5, 
        "min_freq": 10.0,  # คำพื้นฐานระดับต้น
        "topics": ["book", "milk", "fish", "home", "love", "tree", "bird", "food", "city", "park"]
    },
    "A2": {
        "min_len": 5, "max_len": 7, 
        "min_freq": 4.0, 
        "topics": ["travel", "weather", "garden", "market", "dinner", "family"]
    },
    "B1": {
        "min_len": 6, "max_len": 8, 
        "min_freq": 1.0, 
        "topics": ["health", "education", "business", "society", "solution"]
    },
    "B2": {
        "min_len": 7, "max_len": 10, 
        "min_freq": 0.1, 
        "topics": ["strategy", "analysis", "science", "global", "system"]
    }
}

# คลังคำง่ายการันตีความถูกต้อง (สำรองชั้นสุดท้าย)
BASE_VOCAB = {
    "A0": ["CAT", "DOG", "SUN", "BOY", "GIRL", "PEN", "CAR", "RED", "BLUE", "BIG", "RUN", "HOT", "BED", "BOX", "CUP"],
    "A1": ["BOOK", "FISH", "MILK", "TREE", "BIRD", "FOOD", "HAND", "HOME", "LOVE", "WALK", "PARK", "GAME", "TIME", "WORK"],
    "A2": ["TRAVEL", "WEATHER", "HOLIDAY", "SUNDAY", "FUTURE", "HEALTH", "PICTURE", "SUMMER", "WINTER", "GARDEN", "MARKET"],
    "B1": ["SUCCESS", "BUSINESS", "EXPERIENCE", "KNOWLEDGE", "EDUCATION", "OPINION", "DECISION", "PROGRESS", "PROBLEM"],
    "B2": ["STRATEGY", "RESOURCE", "ANALYSIS", "CAPACITY", "CHALLENGE", "CRITICAL", "EVIDENCE", "GLOBAL", "IDENTITY"]
}

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    asyncio.create_task(background_word_fetcher())

# แปลความหมายผ่าน Google Translate
async def translate_in_context(session, word: str):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                if translated.lower() != word.lower() and len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

async def build_quiz_item(session, word: str):
    thai_meaning = await translate_in_context(session, word.lower())
    if thai_meaning:
        fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
        selected_fakes = random.sample(fakes, 3)
        choices = [thai_meaning] + selected_fakes
        random.shuffle(choices)
        return {"word": word, "correct": thai_meaning, "choices": choices}
    return None

# สกัดค่า Word Frequency จาก API ของ Datamuse
def extract_frequency(tags):
    for tag in tags:
        if tag.startswith("f:"):
            try:
                return float(tag[2:])
            except ValueError:
                return 0.0
    return 0.0

# ระบบเบื้องหลัง: สั่ง API ให้กรองคำยากออกตามค่า Frequency และความยาวคำ
async def background_word_fetcher():
    print("🧠 สมองเบื้องหลังเริ่มทำงาน: กรองเฉพาะคำง่ายตรงตามระดับจาก API...")
    async with aiohttp.ClientSession() as session:
        while True:
            for level in ["A0", "A1", "A2", "B1", "B2"]:
                if len(WORD_CACHE[level]) < 8:
                    config = LEVEL_CONFIG[level]
                    topic = random.choice(config["topics"])
                    # md=f บอก API ให้ส่งค่า Frequency ความฮิตของคำกลับมาด้วย
                    url = f"https://api.datamuse.com/words?topics={topic}&md=f&max=60"
                    
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                random.shuffle(data)
                                for item in data:
                                    w = item.get("word", "").upper()
                                    tags = item.get("tags", [])
                                    freq = extract_frequency(tags)

                                    # กรองระดับ API: 1. เป็นตัวอักษรล้วน 2. ความยาวตรงระดับ 3. ค่าความฮิต (Frequency) ต้องสูงตามเกณฑ์
                                    if w.isalpha() and config["min_len"] <= len(w) <= config["max_len"] and freq >= config["min_freq"]:
                                        if w not in USED_WORDS:
                                            quiz = await build_quiz_item(session, w)
                                            if quiz:
                                                WORD_CACHE[level].append(quiz)
                                                USED_WORDS.add(w)
                                                if len(WORD_CACHE[level]) >= 8:
                                                    break
                    except Exception:
                        pass

                    # หาก API ดึงคำมาไม่ทัน ให้ดึงคลังคำพื้นฐานการันตีมาใช้งาน
                    if len(WORD_CACHE[level]) < 3:
                        pool = [w for w in BASE_VOCAB[level] if w not in USED_WORDS]
                        if not pool:
                            pool = BASE_VOCAB[level]
                        w = random.choice(pool)
                        quiz = await build_quiz_item(session, w)
                        if quiz:
                            WORD_CACHE[level].append(quiz)
                            USED_WORDS.add(w)

            await asyncio.sleep(1.0)

class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer, choices):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer

        for choice in choices:
            button = discord.ui.Button(label=choice[:80], style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(choice)
            self.add_item(button)

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            if choice == self.correct_answer:
                embed = discord.Embed(title="🎉 ถูกต้องครับ!", description=f"คำตอบคือ:\n**{choice}**", color=0x2ECC71)
            else:
                embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**", color=0xE74C3C)

            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

            next_embed = discord.Embed(title="🎮 เล่นคำต่อไป", description="เลือกระดับความยากด้านล่างเพื่อเล่นต่อได้เลยครับ:", color=0xF1C40F)
            await interaction.followup.send(embeds=[embed, next_embed], view=LevelSelectView())
        return callback

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        if WORD_CACHE[level]:
            quiz_data = WORD_CACHE[level].pop(0)
        else:
            word = random.choice(BASE_VOCAB[level])
            quiz_data = {
                "word": word,
                "correct": "คำศัพท์พื้นฐาน",
                "choices": ["คำศัพท์พื้นฐาน", "ครอบครัว", "การเดินทาง", "ประสบการณ์"]
            }

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{quiz_data['word']}**\n\nคำแปลภาษาไทยคือข้อใด?:",
            color=0x3498DB
        )

        await interaction.followup.send(embed=embed, view=QuizChoiceView(quiz_data["correct"], quiz_data["choices"]))

    @discord.ui.button(label="A0 (ง่ายมาก)", style=discord.ButtonStyle.primary)
    async def btn_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A0")

    @discord.ui.button(label="A1 (ง่าย)", style=discord.ButtonStyle.primary)
    async def btn_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A1")

    @discord.ui.button(label="A2 (ปานกลาง)", style=discord.ButtonStyle.primary)
    async def btn_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A2")

    @discord.ui.button(label="B1 (ท้าทาย)", style=discord.ButtonStyle.success)
    async def btn_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B1")

    @discord.ui.button(label="B2 (ยากขึ้น)", style=discord.ButtonStyle.success)
    async def btn_b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B2")

    @discord.ui.button(label="🔄 เริ่มเกมใหม่ / รีบอท", style=discord.ButtonStyle.danger)
    async def btn_reboot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มทายคำศัพท์ได้เลยครับ:", 
            color=0xF1C40F
        )
        await interaction.followup.send(embed=embed, view=LevelSelectView())

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        embed = discord.Embed(title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามง่ายๆ ได้เลยครับ:", color=0xF1C40F)
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
