import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# คลังเก็บคำศัพท์ชั่วคราวใน Memory (Cache Queue)
WORD_CACHE = {"A0": [], "A1": [], "A2": [], "B1": [], "B2": []}

TOPIC_MAP = {
    "A0": ["color", "animal", "number", "food", "family"],
    "A1": ["home", "school", "clothes", "time", "body", "city"],
    "A2": ["travel", "weather", "work", "hobby", "health", "nature"],
    "B1": ["business", "feeling", "society", "media", "science", "art"],
    "B2": ["opinion", "process", "system", "culture", "law", "economy"]
}

# สำรองช้อยส์กรณี API แปลภาษาขัดข้อง
BACKUP_FAKES = ["การเดินทาง", "ความสัมพันธ์", "สถานที่", "ความคิดเห็น", "การพัฒนา", "ความรู้สึก", "เป้าหมาย"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # เมื่อบอทพร้อม ทำการดึงคำศัพท์ล่วงหน้ามาเติมใส่ Cache ทันที
    asyncio.create_task(preload_all_caches())

# แปลคำศัพท์เป็นภาษาไทย
async def fetch_translation(session, word: str):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
            if resp.status == 200:
                data = await resp.json()
                raw_text = data['responseData']['translatedText'].strip()
                clean_text = raw_text.split(',')[0].split(';')[0].strip()
                if clean_text.lower() != word.lower() and len(clean_text) < 30:
                    return clean_text
    except Exception:
        pass
    return None

# สุ่มคำศัพท์และแปลไทย 1 ข้อ
async def fetch_single_quiz(session, level: str):
    topic = random.choice(TOPIC_MAP.get(level, TOPIC_MAP["A1"]))
    char = random.choice("abcdefghijklmnopqrstuvwxyz")
    url = f"https://api.datamuse.com/words?ml={topic}&sp={char}*&max=30"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
            if resp.status == 200:
                data = await resp.json()
                words = [item["word"] for item in data if item["word"].isalpha() and 3 <= len(item["word"]) <= 8]
                if words:
                    target_word = random.choice(words)
                    translation = await fetch_translation(session, target_word)
                    if translation:
                        # สร้างช้อยส์หลอก
                        fake_samples = random.sample(BACKUP_FAKES, 3)
                        choices = [translation] + fake_samples
                        random.shuffle(choices)
                        return {
                            "word": target_word.upper(),
                            "correct": translation,
                            "choices": choices
                        }
    except Exception:
        pass
    return None

# ระบบเติมคำศัพท์ใส่ Cache ในฉากหลัง
async def refill_cache(level: str, count: int = 5):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_single_quiz(session, level) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res:
                WORD_CACHE[level].append(res)

async def preload_all_caches():
    print("⏳ กำลังเริ่มดึงคำศัพท์ล่วงหน้าเข้า Cache...")
    for lvl in ["A0", "A1", "A2", "B1", "B2"]:
        await refill_cache(lvl, count=5)
    print("✅ เตรียมคลังคำศัพท์ล่วงหน้าเรียบร้อยพร้อมเล่น!")

# View ปุ่มตอบคำถาม 4 ช้อยส์
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
                embed = discord.Embed(title="🎉 ถูกต้องครับ!", description=f"คำตอบที่ถูกต้องคือ:\n**{choice}**", color=0x2ECC71)
            else:
                embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**", color=0xE74C3C)

            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

            next_embed = discord.Embed(title="🎮 เล่นคำต่อไป", description="เลือกระดับความยากด้านล่างเพื่อเริ่มทายคำต่อไปได้เลยครับ:", color=0xF1C40F)
            await interaction.followup.send(embeds=[embed, next_embed], view=LevelSelectView())
        return callback

# View เลือกระดับความยาก (A0 - B2)
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        # 1. ตรวจสอบว่าใน Cache มีคำศัพท์เหลือไหม
        if not WORD_CACHE[level]:
            # ถ้า Cache หมด ให้ดึงสด 1 ข้อเป็น Fallback
            async with aiohttp.ClientSession() as session:
                quiz_data = await fetch_single_quiz(session, level)
        else:
            # ดึงคำศัพท์จาก Cache ทันที (Instant Speed < 0.1s)
            quiz_data = WORD_CACHE[level].pop(0)

        # 2. แอบสั่งเติมคำศัพท์ใหม่เข้า Cache ในฉากหลังทันที (ไม่บล็อกการเล่น)
        asyncio.create_task(refill_cache(level, count=2))

        if not quiz_data:
            # กรณีเกิดฉุกเฉิน API ล่มจริงๆ ให้ใช้ข้อความสำรอง
            quiz_data = {
                "word": "KNOWLEDGE",
                "correct": "ความรู้",
                "choices": ["ความรู้", "ความคิด", "ความรู้สึก", "ประสบการณ์"]
            }

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{quiz_data['word']}**\n\nคำแปลภาษาไทยของคำนี้คือข้อใด?:",
            color=0x3498DB
        )

        await interaction.followup.send(embed=embed, view=QuizChoiceView(quiz_data["correct"], quiz_data["choices"]))

    @discord.ui.button(label="A0", style=discord.ButtonStyle.primary)
    async def btn_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A0")

    @discord.ui.button(label="A1", style=discord.ButtonStyle.primary)
    async def btn_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A1")

    @discord.ui.button(label="A2", style=discord.ButtonStyle.primary)
    async def btn_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A2")

    @discord.ui.button(label="B1", style=discord.ButtonStyle.success)
    async def btn_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B1")

    @discord.ui.button(label="B2", style=discord.ButtonStyle.success)
    async def btn_b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B2")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        embed = discord.Embed(title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ", description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถาม:", color=0xF1C40F)
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
