import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# URL สำหรับดาวน์โหลดไฟล์ Top 5,000 คำศัพท์ภาษาอังกฤษที่ใช้บ่อยที่สุด
WORDLIST_URL = "https://raw.githubusercontent.com/david47k/top-english-wordlists/master/top_english_words_lower_10000.txt"

FETCHED_5000_WORDS = []
WORD_CACHE = {"A0": [], "A1": [], "A2": [], "B1": [], "B2": []}
USED_WORDS = set()

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("🌐 กำลังดาวน์โหลดไฟล์ Top 5,000 คำศัพท์จากอินเทอร์เน็ต...")
    
    async with aiohttp.ClientSession() as session:
        await fetch_top_words_from_internet(session)

    print("🧠 สมองเบื้องหลังเริ่มทำงาน: เตรียมคำศัพท์ Top 5,000 ไว้ใน Cache...")
    asyncio.create_task(infinite_word_brain())

# ฟังก์ชันดาวน์โหลดคำศัพท์ Top 5,000 จากอินเทอร์เน็ต
async def fetch_top_words_from_internet(session):
    global FETCHED_5000_WORDS
    try:
        async with session.get(WORDLIST_URL, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
            if resp.status == 200:
                text = await resp.text()
                lines = [line.strip() for line in text.splitlines() if line.strip().isalpha()]
                FETCHED_5000_WORDS = [w.upper() for w in lines if len(w) >= 2][:5000]
                print(f"✅ โหลดไฟล์ Top 5,000 คำสำเร็จ! ({len(FETCHED_5000_WORDS)} คำ)")
            else:
                print(f"⚠️ HTTP Status: {resp.status}")
    except Exception as e:
        print(f"⚠️ Load Error: {e}")

# แบ่งระดับความยากตามลำดับความถี่ใน Top 5,000
def get_level_by_rank(index):
    if index < 300:
        return "A0"
    elif index < 1000:
        return "A1"
    elif index < 2000:
        return "A2"
    elif index < 3500:
        return "B1"
    else:
        return "B2"

# แปลความหมายตามบริบทไทยจริง
async def translate_in_context(session, word: str):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                if translated.lower() != word.lower() and len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

# สร้างข้อทายจากคลัง Top 5,000 ที่โหลดมาจากอินเทอร์เน็ต
async def generate_simple_quiz(session, level: str):
    if not FETCHED_5000_WORDS:
        return None

    # คัดเอาเฉพาะคำศัพท์ Top 5,000 ที่ตรงตามระดับความยากนั้นๆ
    candidates = [
        (idx, word) for idx, word in enumerate(FETCHED_5000_WORDS) 
        if get_level_by_rank(idx) == level and word not in USED_WORDS
    ]
    
    # ถ้าเล่นจนหมดคลังระดับนั้นแล้ว ให้รีเซ็ตประวัติของระดับนั้นมาสุ่มใหม่ได้วนลูป
    if not candidates:
        for idx, word in enumerate(FETCHED_5000_WORDS):
            if get_level_by_rank(idx) == level:
                USED_WORDS.discard(word)
        candidates = [
            (idx, word) for idx, word in enumerate(FETCHED_5000_WORDS) 
            if get_level_by_rank(idx) == level
        ]

    if not candidates:
        return None

    _, target_word = random.choice(candidates)
    thai_meaning = await translate_in_context(session, target_word.lower())
    
    if thai_meaning:
        fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
        selected_fakes = random.sample(fakes, min(len(fakes), 3))
        choices = [thai_meaning] + selected_fakes
        random.shuffle(choices)
        
        return {
            "word": target_word,
            "correct": thai_meaning,
            "choices": choices
        }
    return None

# สมองคัดกรองเบื้องหลัง วนลูปเตรียมคำจาก Top 5,000 ไว้ใน Cache
async def infinite_word_brain():
    async with aiohttp.ClientSession() as session:
        while True:
            if not FETCHED_5000_WORDS:
                await asyncio.sleep(1.0)
                continue

            for level in ["A0", "A1", "A2", "B1", "B2"]:
                if len(WORD_CACHE[level]) < 5:
                    quiz = await generate_simple_quiz(session, level)
                    if quiz:
                        WORD_CACHE[level].append(quiz)
                        USED_WORDS.add(quiz["word"])
            await asyncio.sleep(0.5)

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
            quiz_data = {
                "word": "HAPPY",
                "correct": "มีความสุข",
                "choices": ["มีความสุข", "ครอบครัว", "การเดินทาง", "ประสบการณ์"]
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
    
