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

# คลังคำศัพท์สำรองการันตีตามระดับ (ใช้ทันทีหาก Cache เบื้องหลังยังโหลดไม่ทัน)
FALLBACK_QUIZ = {
    "A0": {"word": "CAT", "correct": "แมว", "choices": ["แมว", "สุนัข", "ต้นไม้", "บ้าน"]},
    "A1": {"word": "HAPPY", "correct": "มีความสุข", "choices": ["มีความสุข", "ครอบครัว", "โรงเรียน", "เพื่อน"]},
    "A2": {"word": "TRAVEL", "correct": "ท่องเที่ยว", "choices": ["ท่องเที่ยว", "สภาพอากาศ", "อาหารเย็น", "อนาคต"]},
    "B1": {"word": "SUCCESS", "correct": "ความสำเร็จ", "choices": ["ความสำเร็จ", "ธุรกิจ", "การศึกษา", "ความคิดเห็น"]},
    "B2": {"word": "STRATEGY", "correct": "กลยุทธ์", "choices": ["กลยุทธ์", "ทรัพยากร", "การวิเคราะห์", "หลักฐาน"]}
}

LEVEL_CONFIG = {
    "A0": {"min_len": 3, "max_len": 4, "topics": ["cat", "dog", "sun", "red", "boy", "food"]},
    "A1": {"min_len": 4, "max_len": 5, "topics": ["family", "school", "house", "water", "music"]},
    "A2": {"min_len": 5, "max_len": 7, "topics": ["travel", "weather", "nature", "garden", "market"]},
    "B1": {"min_len": 6, "max_len": 8, "topics": ["business", "education", "health", "society", "habit"]},
    "B2": {"min_len": 7, "max_len": 10, "topics": ["strategy", "analysis", "science", "global", "system"]}
}

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    asyncio.create_task(infinite_word_brain())

async def translate_in_context(session, word: str):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=1.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                if translated.lower() != word.lower() and len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

async def fetch_random_net_words(session, level: str):
    config = LEVEL_CONFIG[level]
    topic = random.choice(config["topics"])
    url = f"https://api.datamuse.com/words?topics={topic}&max=30"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
            if resp.status == 200:
                data = await resp.json()
                fetched_words = []
                for item in data:
                    w = item.get("word", "").upper()
                    if w.isalpha() and config["min_len"] <= len(w) <= config["max_len"]:
                        if w not in USED_WORDS:
                            fetched_words.append(w)
                return fetched_words
    except Exception:
        pass
    return []

# สมองเบื้องหลังทำงานเงียบๆ ไม่กระทบความเร็วของปุ่ม
async def infinite_word_brain():
    print("🧠 สมองเบื้องหลังเริ่มทำงาน: กำลังดึงและสะสมคำศัพท์จากอินเทอร์เน็ต...")
    async with aiohttp.ClientSession() as session:
        while True:
            for level in ["A0", "A1", "A2", "B1", "B2"]:
                if len(WORD_CACHE[level]) < 10:
                    net_words = await fetch_random_net_words(session, level)
                    for target_word in net_words:
                        if target_word in USED_WORDS:
                            continue
                            
                        thai_meaning = await translate_in_context(session, target_word.lower())
                        if thai_meaning:
                            fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
                            selected_fakes = random.sample(fakes, 3)
                            choices = [thai_meaning] + selected_fakes
                            random.shuffle(choices)
                            
                            WORD_CACHE[level].append({
                                "word": target_word,
                                "correct": thai_meaning,
                                "choices": choices
                            })
                            USED_WORDS.add(target_word)
                            
                            if len(WORD_CACHE[level]) >= 10:
                                break
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
            # ตอบรับ Discord ทันทีป้องกัน Interaction Failed
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
        # 1. ตอบรับ Interaction ทันที
        await interaction.response.defer()

        # 2. ดึงจาก Cache ทันที หากว่างอยู่จะใช้ Fallback ประจำระดับทันที (ตอบสนองใน 0.01s)
        if WORD_CACHE[level]:
            quiz_data = WORD_CACHE[level].pop(0)
        else:
            quiz_data = FALLBACK_QUIZ[level]

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
        await interaction.response.defer()
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

