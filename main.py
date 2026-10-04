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

# กำหนดเกณฑ์ความยาวของคำในแต่ละระดับ CEFR เพื่อดึงจาก API
LEVEL_SPECS = {
    "A0": {"min_len": 3, "max_len": 4, "topics": ["animal", "color", "food", "body"]},
    "A1": {"min_len": 4, "max_len": 5, "topics": ["family", "school", "house", "time"]},
    "A2": {"min_len": 5, "max_len": 7, "topics": ["travel", "weather", "nature", "work"]},
    "B1": {"min_len": 6, "max_len": 9, "topics": ["business", "education", "health", "society"]},
    "B2": {"min_len": 7, "max_len": 12, "topics": ["science", "technology", "politics", "economy"]}
}

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "การสื่อสาร", "ความรู้"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    asyncio.create_task(infinite_word_brain())

# ดึงคำแปลภาษาไทยจาก Google Translate
async def translate_in_context(session, word: str):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                # กรองไม่ให้เอาคำแปลที่เป็นภาษาอังกฤษ หรือแปลไม่ได้ความหมาย
                if translated.lower() != word.lower() and len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

# ดึงคำศัพท์ภาษาอังกฤษใหม่ๆ จาก Datamuse API บนอินเทอร์เน็ต
async def fetch_words_from_api(session, level: str):
    spec = LEVEL_SPECS[level]
    topic = random.choice(spec["topics"])
    url = f"https://api.datamuse.com/words?topics={topic}&max=50"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
            if resp.status == 200:
                data = await resp.json()
                valid_words = []
                for item in data:
                    word = item.get("word", "").upper()
                    # กรองเอาเฉพาะตัวอักษร A-Z และความยาวตรงตามระดับ
                    if word.isalpha() and spec["min_len"] <= len(word) <= spec["max_len"]:
                        if word not in USED_WORDS:
                            valid_words.append(word)
                return valid_words
    except Exception:
        pass
    return []

# สร้างโจทย์ทายคำศัพท์
async def generate_simple_quiz(session, level: str):
    words = await fetch_words_from_api(session, level)
    if not words:
        return None
        
    random.shuffle(words)
    for target_word in words:
        thai_meaning = await translate_in_context(session, target_word.lower())
        if thai_meaning:
            fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
            selected_fakes = random.sample(fakes, 3)
            choices = [thai_meaning] + selected_fakes
            random.shuffle(choices)
            
            return {
                "word": target_word,
                "correct": thai_meaning,
                "choices": choices
            }
    return None

# สมองคัดกรองเบื้องหลัง ดึงคำศัพท์จากอินเทอร์เน็ตเข้ามาเติมใน Cache เรื่อยๆ ไม่จำกัด
async def infinite_word_brain():
    print("🧠 สมองเบื้องหลังเริ่มทำงาน: กำลังเชื่อมต่ออินเทอร์เน็ตเพื่อดึงคำศัพท์ใหม่แบบไร้ขีดจำกัด...")
    async with aiohttp.ClientSession() as session:
        while True:
            for level in ["A0", "A1", "A2", "B1", "B2"]:
                if len(WORD_CACHE[level]) < 5:
                    quiz = await generate_simple_quiz(session, level)
                    if quiz:
                        WORD_CACHE[level].append(quiz)
                        USED_WORDS.add(quiz["word"])
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
            # สำรองข้อมูลฉุกเฉินกรณีเน็ตช้า
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

    @discord.ui.button(label="รีบอทใหม่", style=discord.ButtonStyle.secondary)
    async def btn_reboot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามง่ายๆ ได้เลยครับ:", 
            color=0xF1C40F
        )
        await interaction.channel.send(embed=embed, view=LevelSelectView())

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
    
