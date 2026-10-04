import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

USED_WORDS = set()

# คลังคำศัพท์จริงสำรองหลายระดับ (ป้องกันขึ้น WORD-xxx เมื่อเน็ตช้า)
REAL_BACKUP_WORDS = {
    "A0": ["CAT", "DOG", "SUN", "BOY", "GIRL", "BOOK", "PEN", "FISH", "MILK", "CAR", "TREE", "BIRD", "WATER", "FOOD", "HAND", "RED", "BLUE", "BIG", "RUN", "WALK"],
    "A1": ["HAPPY", "FAMILY", "SCHOOL", "FRIEND", "HOUSE", "ANIMAL", "APPLE", "DRINK", "MUSIC", "MONEY", "PHONE", "TIME", "DOCTOR", "MOTHER", "FATHER", "CLEAN", "EARLY", "TODAY"],
    "A2": ["TRAVEL", "WEATHER", "HOLIDAY", "SUNDAY", "FUTURE", "HEALTH", "PICTURE", "SUMMER", "WINTER", "LUNCH", "DINNER", "FARMER", "GARDEN", "KITCHEN", "MARKET", "BEAUTIFUL", "CAREFUL"],
    "B1": ["SUCCESS", "BUSINESS", "EXPERIENCE", "KNOWLEDGE", "EDUCATION", "OPINION", "DECISION", "PROGRESS", "PROBLEM", "SOLUTION", "COMMUNITY", "CREATIVE", "HABIT", "FEELING", "SOCIETY", "IMPROVE"],
    "B2": ["STRATEGY", "RESOURCE", "ANALYSIS", "CAPACITY", "CHALLENGE", "CRITICAL", "EVIDENCE", "GLOBAL", "IDENTITY", "OBJECTIVE", "STABILITY", "STRUCTURE", "PERSPECTIVE", "TRANSFORM"]
}

LEVEL_CONFIG = {
    "A0": {"min_len": 3, "max_len": 4, "seeds": ["cat", "dog", "sun", "red", "boy", "pen", "hat", "cup"]},
    "A1": {"min_len": 4, "max_len": 5, "seeds": ["love", "home", "city", "park", "food", "game", "time", "work"]},
    "A2": {"min_len": 5, "max_len": 7, "seeds": ["travel", "nature", "garden", "market", "dinner", "person", "system"]},
    "B1": {"min_len": 6, "max_len": 8, "seeds": ["nature", "health", "action", "detail", "effort", "market", "policy"]},
    "B2": {"min_len": 7, "max_len": 10, "seeds": ["theory", "method", "system", "factor", "growth", "energy", "future"]}
}

BACKUP_FAKES = ["ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# แปลความหมายผ่าน Google Translate
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

# สุ่มดึงคำใหม่สดๆ จาก Datamuse API (ปรับปรุง query ให้ดึงติดง่ายขึ้น)
async def fetch_live_word(level: str):
    config = LEVEL_CONFIG[level]
    seed = random.choice(config["seeds"])
    url = f"https://api.datamuse.com/words?ml={seed}&max=50"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4.0)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    random.shuffle(data)
                    for item in data:
                        w = item.get("word", "").upper()
                        if w.isalpha() and config["min_len"] <= len(w) <= config["max_len"]:
                            if w not in USED_WORDS:
                                thai_meaning = await translate_in_context(session, w.lower())
                                if thai_meaning:
                                    USED_WORDS.add(w)
                                    fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
                                    selected_fakes = random.sample(fakes, 3)
                                    choices = [thai_meaning] + selected_fakes
                                    random.shuffle(choices)
                                    return {"word": w, "correct": thai_meaning, "choices": choices}
        except Exception:
            pass

        # สำรองกรณีเน็ตช้ามากๆ จะใช้คำจริงตามระดับเสมอ (ไม่ใช้ WORD-xxx อีกต่อไป)
        backup_pool = [w for w in REAL_BACKUP_WORDS[level] if w not in USED_WORDS]
        if not backup_pool:
            backup_pool = REAL_BACKUP_WORDS[level]
            
        fallback_word = random.choice(backup_pool)
        USED_WORDS.add(fallback_word)
        thai_meaning = await translate_in_context(session, fallback_word.lower()) or "ความหมาย"
        fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
        choices = [thai_meaning] + random.sample(fakes, 3)
        random.shuffle(choices)
        return {"word": fallback_word, "correct": thai_meaning, "choices": choices}

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

        quiz_data = await fetch_live_word(level)

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
    
