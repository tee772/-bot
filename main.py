import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# 1. สมองคลังข้อมูลเบื้องหลัง (Cache Queue & Blacklist)
WORD_CACHE = {"A0": [], "A1": [], "A2": [], "B1": [], "B2": []}
USED_WORDS = set()  # บันทึกคำที่เคยเล่นไปแล้วเพื่อไม่ให้ทายซ้ำ

TOPIC_MAP = {
    "A0": ["color", "animal", "number", "food", "family"],
    "A1": ["home", "school", "clothes", "time", "body", "city"],
    "A2": ["travel", "weather", "work", "hobby", "health", "nature"],
    "B1": ["business", "feeling", "society", "media", "science", "art"],
    "B2": ["opinion", "process", "system", "culture", "law", "economy"]
}

# สำรองช้อยส์กรณีแปลภาษาไทยซ้ำกัน
BACKUP_FAKES = ["การเดินทาง", "ความสัมพันธ์", "สถานที่", "ความคิดเห็น", "การพัฒนา", "ความรู้สึก", "เป้าหมาย", "สภาพแวดล้อม"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # รันระบบสมองเบื้องหลังทันทีเมื่อเริ่มเปิดบอท
    asyncio.create_task(background_word_brain())

# 2. สมองคัดกรองความแปลและช้อยส์ภาษาไทย
async def fetch_clean_translation(session, word: str):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
            if resp.status == 200:
                data = await resp.json()
                raw_text = data['responseData']['translatedText'].strip()
                clean_text = raw_text.split(',')[0].split(';')[0].strip()
                # กรองคำแปลที่เพี้ยนหรือตรงกับคำภาษาอังกฤษออก
                if clean_text.lower() != word.lower() and len(clean_text) < 25:
                    return clean_text
    except Exception:
        pass
    return None

# 3. สมองสุ่มคำศัพท์จากอินเทอร์เน็ต + ตรวจสอบความถูกต้อง
async def generate_qualified_word(session, level: str):
    topic = random.choice(TOPIC_MAP.get(level, TOPIC_MAP["A1"]))
    random_char = random.choice("abcdefghijklmnopqrstuvwxyz")
    url = f"https://api.datamuse.com/words?ml={topic}&sp={random_char}*&max=30"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
            if resp.status == 200:
                data = await resp.json()
                # คัดกรองเอาเฉพาะตัวอักษรบริสุทธิ์ ไม่เคยเล่นมาก่อน และความยาวเหมาะสม
                valid_words = [
                    item["word"].upper() for item in data 
                    if item["word"].isalpha() 
                    and 3 <= len(item["word"]) <= 8 
                    and item["word"].upper() not in USED_WORDS
                ]
                
                if valid_words:
                    target = random.choice(valid_words)
                    translation = await fetch_clean_translation(session, target.lower())
                    
                    if translation:
                        # สร้างช้อยส์หลอก 3 ช้อยส์ที่ไม่ซ้ำกับคำตอบจริง
                        fakes = [f for f in BACKUP_FAKES if f != translation]
                        selected_fakes = random.sample(fakes, 3)
                        
                        choices = [translation] + selected_fakes
                        random.shuffle(choices)
                        
                        return {
                            "word": target,
                            "correct": translation,
                            "choices": choices
                        }
    except Exception:
        pass
    return None

# 4. สมองส่วนประมวลผลฉากหลัง (Background Brain Loop)
async def background_word_brain():
    print("🧠 สมองเบื้องหลังกำลังเริ่มค้นหาและจัดหมวดหมู่คำศัพท์จากอินเทอร์เน็ต...")
    async with aiohttp.ClientSession() as session:
        while True:
            for level in ["A0", "A1", "A2", "B1", "B2"]:
                # ถ้าคำศัพท์ใน Cache ของระดับนั้นๆ มีน้อยกว่า 5 คำ ให้เติมทันที
                if len(WORD_CACHE[level]) < 5:
                    data = await generate_qualified_word(session, level)
                    if data:
                        WORD_CACHE[level].append(data)
                        # บันทึกเข้า Blacklist ป้องกันนำคำเดิมมาใช้ซ้ำ
                        USED_WORDS.add(data["word"])
            # พักการทำงาน 1 วินาทีเพื่อไม่ให้บล็อกระบบ
            await asyncio.sleep(1)

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

        # ดึงข้อมูลที่สมองคัดกรองเตรียมไว้แล้วมาแสดงผลทันที (< 0.1 วินาที)
        if WORD_CACHE[level]:
            quiz_data = WORD_CACHE[level].pop(0)
        else:
            # สำรองฉุกเฉินกรณีสมองยังดึงข้อมูลเข้า Cache ไม่ทัน
            quiz_data = {
                "word": "OPPORTUNITY",
                "correct": "โอกาส",
                "choices": ["โอกาส", "ความสำเร็จ", "การเดินทาง", "ความคิดเห็น"]
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
    
