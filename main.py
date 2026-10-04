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

BASE_VOCAB = {
    "A0": ["CAT", "DOG", "SUN", "BOY", "GIRL", "BOOK", "PEN", "FISH", "MILK", "CAR", "TREE", "BIRD", "WATER", "FOOD", "HAND"],
    "A1": ["HAPPY", "FAMILY", "SCHOOL", "FRIEND", "HOUSE", "ANIMAL", "APPLE", "DRINK", "MUSIC", "MONEY", "PHONE", "TIME", "DOCTOR", "MOTHER", "FATHER"],
    "A2": ["TRAVEL", "WEATHER", "HOLIDAY", "SUNDAY", "FUTURE", "HEALTH", "PICTURE", "SUMMER", "WINTER", "LUNCH", "DINNER", "FARMER", "GARDEN", "KITCHEN", "MARKET"],
    "B1": ["SUCCESS", "BUSINESS", "EXPERIENCE", "KNOWLEDGE", "EDUCATION", "OPINION", "DECISION", "PROGRESS", "PROBLEM", "SOLUTION", "COMMUNITY", "CREATIVE", "HABIT", "FEELING", "SOCIETY"],
    "B2": ["STRATEGY", "RESOURCE", "ANALYSIS", "CAPACITY", "CHALLENGE", "CRITICAL", "EVIDENCE", "GLOBAL", "IDENTITY", "OBJECTIVE", "PRIMITIVE", "STABILITY", "STRUCTURE", "SUSPECT", "TREND"]
}

EXTRA_SEED_WORDS = {
    "A0": ["RED", "BLUE", "BIG", "SMALL", "RUN", "WALK", "HOT", "COLD", "EAT", "SEE"],
    "A1": ["CLEAN", "DIRTY", "EARLY", "LATE", "ALWAYS", "NEVER", "AGAIN", "TODAY", "BEFORE", "AFTER"],
    "A2": ["ALREADY", "BETWEEN", "BEAUTIFUL", "CAREFUL", "DANGEROUS", "IMPORTANT", "POSSIBLE", "TOGETHER", "WITHOUT", "EVERYWHERE"],
    "B1": ["ADVANTAGE", "BEHAVIOR", "CONFIDENT", "DIFFERENCE", "EFFECTIVE", "IMPROVE", "OPPORTUNITY", "RECOMMEND", "SITUATION", "VALUABLE"],
    "B2": ["ABSOLUTE", "COMPLEX", "EVALUATE", "GENERATE", "INDICATE", "MAINTAIN", "PERSPECTIVE", "SIGNIFICANT", "SUFFICIENT", "TRANSFORM"]
}

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    asyncio.create_task(infinite_word_brain())

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

async def generate_simple_quiz(session, level: str):
    pool = BASE_VOCAB.get(level, BASE_VOCAB["A1"]) + EXTRA_SEED_WORDS.get(level, EXTRA_SEED_WORDS["A1"])
    available_words = [w for w in pool if w not in USED_WORDS]
    
    if not available_words:
        available_words = pool
        
    target_word = random.choice(available_words)
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

async def infinite_word_brain():
    print("🧠 สมองเบื้องหลังเริ่มทำงาน: คัดสรรเฉพาะคำศัพท์ง่ายๆ ที่ใช้งานจริง...")
    async with aiohttp.ClientSession() as session:
        while True:
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

    # เพิ่มปุ่ม "รีบอทใหม่" ถัดจาก B2 สีเหลือง (ButtonStyle.warning)
    @discord.ui.button(label="รีบอทใหม่", style=discord.ButtonStyle.warning)
    async def btn_reboot(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ลบข้อความปัจจุบัน
        await interaction.message.delete()
        
        # ส่งข้อความคำสั่ง !t ใหม่ขึ้นมาทันที
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

