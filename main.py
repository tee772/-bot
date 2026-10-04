import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# 1. สมองคลังข้อมูลเบื้องหลัง (Infinite Cache & History Tracking)
WORD_CACHE = {"A0": [], "A1": [], "A2": [], "B1": [], "B2": []}
USED_WORDS = set()

# หมวดหมู่บริบทในการดึงคำศัพท์
CONTEXT_CATEGORIES = {
    "A0": ["family", "animals", "daily_life", "food", "objects"],
    "A1": ["work", "shopping", "feelings", "places", "activities"],
    "A2": ["travel", "health", "technology", "society", "nature"],
    "B1": ["business", "education", "relationships", "culture", "environment"],
    "B2": ["philosophy", "economy", "politics", "science", "psychology"]
}

# ช้อยส์บริบทหลอกตามประเภท เพื่อให้ช้อยส์เนียนสมจริง
CONTEXT_FAKES = {
    "A0": ["สัตว์เลี้ยง", "อาหารเช้า", "ของใช้ในบ้าน", "สมาชิกในครอบครัว", "สีสัน"],
    "A1": ["กิจกรรมยามว่าง", "การเดินทาง", "สถานที่ทำงาน", "อารมณ์ความรู้สึก", "การซื้อของ"],
    "A2": ["การดูแลสุขภาพ", "สภาพอากาศ", "การท่องเที่ยว", "อุปกรณ์เทคโนโลยี", "ธรรมชาติ"],
    "B1": ["การบริหารจัดการ", "ความสัมพันธ์", "การวางแผนอนาคต", "การแก้ไขปัญหา", "วัฒนธรรม"],
    "B2": ["ทัศนคติเชิงบวก", "การวิเคราะห์ข้อมูล", "ความขัดแย้งทางความคิด", "นโยบายสาธารณะ", "ทฤษฎีทางวิทยาศาสตร์"]
}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # เปิดสมองวนลูปเบื้องหลังทันที
    asyncio.create_task(infinite_word_finder())

# 2. ระบบแปลตามบริบทภาษาไทย (Context-Aware Translator)
async def translate_in_context(session, word: str):
    # ดึงข้อมูลจาก Google Translation Engine สำหรับบริบทการใช้งานจริง
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                
                # กรองไม่ให้แปลทับศัพท์ หรือแปลยาวเป็นประโยค
                if translated.lower() != word.lower() and 2 <= len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

# 3. ค้นหาคำศัพท์วนลูปจาก Datamuse & คัดกรองบริบท
async def fetch_contextual_quiz(session, level: str):
    category = random.choice(CONTEXT_CATEGORIES.get(level, CONTEXT_CATEGORIES["A1"]))
    char = random.choice("abcdefghijklmnopqrstuvwxyz")
    url = f"https://api.datamuse.com/words?ml={category}&sp={char}*&max=40"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                # กรองเอาเฉพาะศัพท์ที่เป็นคำเดี่ยว ไร้ตัวเลข และไม่เคยเล่นมาก่อน
                candidates = [
                    item["word"].upper() for item in data 
                    if item["word"].isalpha() 
                    and 3 <= len(item["word"]) <= 10 
                    and item["word"].upper() not in USED_WORDS
                ]
                
                if candidates:
                    target_word = random.choice(candidates)
                    thai_context_meaning = await translate_in_context(session, target_word.lower())
                    
                    if thai_context_meaning:
                        # สร้างช้อยส์หลอกตามบริบทที่สมเหตุสมผล
                        fake_pool = [f for f in CONTEXT_FAKES.get(level, CONTEXT_FAKES["A1"]) if f != thai_context_meaning]
                        fakes = random.sample(fake_pool, min(3, len(fake_pool)))
                        
                        choices = [thai_context_meaning] + fakes
                        random.shuffle(choices)
                        
                        return {
                            "word": target_word,
                            "correct": thai_context_meaning,
                            "choices": choices
                        }
    except Exception:
        pass
    return None

# 4. สมองวนลูปค้นหาคำศัพท์เบื้องหลังตลอดเวลา (Infinite Background Loop)
async def infinite_word_finder():
    print("🧠 สมองเบื้องหลังกำลังทำงานวนลูปค้นหาคำศัพท์ตามบริบทไร้ขีดจำกัด...")
    async with aiohttp.ClientSession() as session:
        while True:
            for level in ["A0", "A1", "A2", "B1", "B2"]:
                # เติมคำศัพท์ใส่ Cache ถ้ามีน้อยกว่า 5 ข้อ
                if len(WORD_CACHE[level]) < 5:
                    quiz_item = await fetch_contextual_quiz(session, level)
                    if quiz_item:
                        WORD_CACHE[level].append(quiz_item)
                        USED_WORDS.add(quiz_item["word"]) # ลงบันทึกห้ามใช้ซ้ำ
            
            # พัก 0.8 วินาทีต่อรอบ เพื่อไม่ให้โดนบล็อก IP
            await asyncio.sleep(0.8)

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
                embed = discord.Embed(title="🎉 ถูกต้องตามบริบท!", description=f"ความหมายที่ถูกต้องคือ:\n**{choice}**", color=0x2ECC71)
            else:
                embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คุณเลือก: {choice}\n\nความหมายตามบริบทคือ:\n**{self.correct_answer}**", color=0xE74C3C)

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

        # ดึงคำศัพท์ที่สมองคัดกรองบริบทมาเตรียมไว้แล้ว (< 0.1 วินาที)
        if WORD_CACHE[level]:
            quiz_data = WORD_CACHE[level].pop(0)
        else:
            # สำรองกรณีสมองกำลังประมวลผลคำแรก
            quiz_data = {
                "word": "PERSPECTIVE",
                "correct": "มุมมอง / ทัศนคติ",
                "choices": ["มุมมอง / ทัศนคติ", "สภาพแวดล้อม", "การวางแผนอนาคต", "การบริหารจัดการ"]
            }

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{quiz_data['word']}**\n\nความหมายตามบริบทการใช้งานจริงคือข้อใด?:",
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
    
