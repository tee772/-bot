import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# แหล่งที่มาไฟล์ Top 5,000 คำศัพท์ภาษาอังกฤษใช้บ่อยที่สุด
WORDLIST_URL = "https://raw.githubusercontent.com/david47k/top-english-wordlists/master/top_english_words_lower_10000.txt"

FETCHED_5000_WORDS = []
UNCATEGORIZED_CACHE = []
USED_WORDS = set()

BACKUP_FAKES = [
    "ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", 
    "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("🌐 กำลังเริ่มดาวน์โหลดไฟล์ 5,000 คำศัพท์ใช้บ่อยที่สุดจากอินเทอร์เน็ต...")
    
    async with aiohttp.ClientSession() as session:
        await fetch_top_words_from_internet(session)
        
    print("🚀 เริ่มระบบคัดแยกคำศัพท์และสร้างคลังคำถามล่วงหน้า...")
    asyncio.create_task(background_word_fetcher())

async def fetch_top_words_from_internet(session):
    global FETCHED_5000_WORDS
    try:
        async with session.get(WORDLIST_URL, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
            if resp.status == 200:
                text = await resp.text()
                lines = [line.strip() for line in text.splitlines() if line.strip().isalpha()]
                FETCHED_5000_WORDS = [w for w in lines if len(w) >= 2][:5000]
                print(f"✅ โหลดคำศัพท์ Top 5,000 สำเร็จ! ({len(FETCHED_5000_WORDS)} คำ)")
            else:
                print(f"⚠️ HTTP Status: {resp.status}")
    except Exception as e:
        print(f"⚠️ Load Error: {e}")

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

async def build_quiz_item(session, word: str, level: str):
    thai_meaning = await translate_in_context(session, word.lower())
    if thai_meaning:
        fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
        selected_fakes = random.sample(fakes, min(len(fakes), 3))
        choices = [thai_meaning] + selected_fakes
        random.shuffle(choices)
        return {
            "word": word.upper(), 
            "correct": thai_meaning, 
            "choices": choices,
            "level": level
        }
    return None

async def background_word_fetcher():
    async with aiohttp.ClientSession() as session:
        while True:
            if not FETCHED_5000_WORDS:
                await asyncio.sleep(1.0)
                continue

            if len(UNCATEGORIZED_CACHE) < 200:
                target_level = random.choice(["A0", "A1", "A2", "B1", "B2"])
                candidates = [
                    (idx, word) for idx, word in enumerate(FETCHED_5000_WORDS) 
                    if get_level_by_rank(idx) == target_level and word.upper() not in USED_WORDS
                ]
                
                if not candidates:
                    print(f"🔄 รีเซ็ตคลังระดับ {target_level} เพื่อเริ่มสุ่มใหม่...")
                    for idx, word in enumerate(FETCHED_5000_WORDS):
                        if get_level_by_rank(idx) == target_level:
                            USED_WORDS.discard(word.upper())
                    candidates = [
                        (idx, word) for idx, word in enumerate(FETCHED_5000_WORDS) 
                        if get_level_by_rank(idx) == target_level
                    ]

                random.shuffle(candidates)
                for idx, word in candidates:
                    w_upper = word.upper()
                    quiz = await build_quiz_item(session, w_upper, target_level)
                    if quiz:
                        UNCATEGORIZED_CACHE.append(quiz)
                        USED_WORDS.add(w_upper)
                        print(f"✅ [LOADED] {w_upper} (#{idx+1} | {target_level}) | คลังรวม: {len(UNCATEGORIZED_CACHE)}")
                        await asyncio.sleep(0.1)
                        break

            await asyncio.sleep(0.2)

def match_word_for_level(level: str):
    if not UNCATEGORIZED_CACHE:
        return None

    for idx, item in enumerate(UNCATEGORIZED_CACHE):
        if item.get("level") == level:
            return UNCATEGORIZED_CACHE.pop(idx)
            
    return UNCATEGORIZED_CACHE.pop(0)

async def auto_clean_message(message):
    """ลบข้อความทันทีเมื่อหมดเวลาหรือเกิดข้อผิดพลาด"""
    if message:
        try:
            await message.delete()
        except Exception:
            pass

class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer, choices):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer
        self.message = None

        for choice in choices:
            button = discord.ui.Button(label=choice[:80], style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(choice)
            self.add_item(button)

    async def on_timeout(self):
        # เมื่อหมดเวลา ลบข้อความนี้ทิ้งทันที
        await auto_clean_message(self.message)

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()

                if choice == self.correct_answer:
                    embed = discord.Embed(title="🎉 ถูกต้องครับ!", description=f"คำตอบคือ:\n**{choice}**", color=0x2ECC71)
                else:
                    embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**", color=0xE74C3C)

                # ปิดใช้งานปุ่มทั้งหมดในคำถามเดิม
                for item in self.children:
                    item.disabled = True

                await interaction.edit_original_response(embed=embed, view=self)

            except Exception:
                await auto_clean_message(self.message)

        return callback

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None

    async def on_timeout(self):
        # เมื่อหมดเวลา ลบข้อความเลือกเมนูนี้ทิ้งทันที
        await auto_clean_message(self.message)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()

            quiz_data = match_word_for_level(level)

            if quiz_data:
                embed = discord.Embed(
                    title=f"🎯 ทายคำศัพท์ระดับ {level}",
                    description=f"คำศัพท์: **{quiz_data['word']}**\n\nคำแปลภาษาไทยคือข้อใด?:",
                    color=0x3498DB
                )
                quiz_view = QuizChoiceView(quiz_data["correct"], quiz_data["choices"])
                sent_msg = await interaction.followup.send(embed=embed, view=quiz_view)
                quiz_view.message = sent_msg
                
                # เมื่อกดเลือกคำถามเสร็จแล้ว ให้ลบเมนูเลือกระดับเดิมทิ้งทันที ไม่ให้ค้างในแชท
                await auto_clean_message(self.message)
            else:
                embed = discord.Embed(
                    title="⏳ กำลังเตรียมคำศัพท์...",
                    description="กำลังเตรียมคำศัพท์จากอินเทอร์เน็ต กรุณากดปุ่มใหม่อีกครั้งใน 1-2 วินาทีครับ",
                    color=0xE67E22
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            await auto_clean_message(self.message)

    @discord.ui.button(label="A0 (1-300 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A0")

    @discord.ui.button(label="A1 (301-1,000 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A1")

    @discord.ui.button(label="A2 (1,001-2,000 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A2")

    @discord.ui.button(label="B1 (2,001-3,500 คำแรก)", style=discord.ButtonStyle.success)
    async def btn_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B1")

    @discord.ui.button(label="B2 (3,501-5,000 คำแรก)", style=discord.ButtonStyle.success)
    async def btn_b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B2")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        try:
            await message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="🎯 เลือกความยากคำศัพท์ (Top 5,000 Words)", 
            description="กดเลือกระดับความยากด้านล่างเพื่อเริ่มคำถามได้เลยครับ:", 
            color=0xF1C40F
        )
        view = LevelSelectView()
        sent_msg = await message.channel.send(embed=embed, view=view)
        view.message = sent_msg
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
