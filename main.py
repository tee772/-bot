import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# ชุดคำศัพท์พื้นฐานระดับเด็กและผู้เริ่มต้น
KIDS_BASE_WORDS = {
    "A0": ["cat", "dog", "sun", "red", "boy", "car", "pen", "hat", "cup", "run", "fan", "box", "sky", "sea", "bus", "day", "hot", "man", "map", "bed", "pig", "cow", "toy", "zoo", "egg", "leg", "arm", "top", "big"],
    "A1": ["book", "milk", "fish", "home", "love", "tree", "bird", "food", "city", "park", "game", "time", "work", "rain", "cake", "door", "face", "girl", "help", "life", "star", "ball", "duck", "ship", "frog", "hand", "foot", "baby", "moon", "fire"],
    "A2": ["apple", "water", "house", "bread", "train", "clock", "chair", "table", "paper", "shirt", "shoes", "teeth", "music", "smile", "clean", "green", "white", "black", "happy", "sweet"],
    "B1": ["doctor", "family", "school", "friend", "animal", "window", "garden", "market", "dinner", "person", "summer", "winter", "travel", "yellow", "orange", "monkey", "rabbit", "pencil"],
    "B2": ["student", "teacher", "morning", "evening", "country", "picture", "station", "weather", "brother", "sister", "kitchen", "chicken", "holiday", "saturday", "sunday"]
}

UNCATEGORIZED_CACHE = []
USED_WORDS = set()

BACKUP_FAKES = [
    "ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", 
    "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("🚀 เริ่มระบบดึงคำศัพท์พื้นฐานสำหรับเด็กและผู้เริ่มต้น...")
    asyncio.create_task(background_word_fetcher())

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
            if len(UNCATEGORIZED_CACHE) < 200:
                target_level = random.choice(["A0", "A1", "A2", "B1", "B2"])
                word_candidates = KIDS_BASE_WORDS[target_level]
                
                seed = random.choice(word_candidates)
                url = f"https://api.datamuse.com/words?sp={seed}*&max=10"
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            fetched_words = [item.get("word", "") for item in data if len(item.get("word", "")) <= 8]
                            all_choices = list(set([seed] + fetched_words))
                            random.shuffle(all_choices)
                            
                            for w in all_choices:
                                w_upper = w.upper()
                                if w_upper.isalpha() and w_upper not in USED_WORDS and len(w_upper) >= 3:
                                    quiz = await build_quiz_item(session, w_upper, target_level)
                                    if quiz:
                                        UNCATEGORIZED_CACHE.append(quiz)
                                        USED_WORDS.add(w_upper)
                                        print(f"✅ [LOADED EASY] {w_upper} (ระดับ {target_level}) | คลังรวม: {len(UNCATEGORIZED_CACHE)} คำ")
                                        await asyncio.sleep(0.1)
                                        break
                except Exception as e:
                    print(f"⚠️ Fetch Note: {e}")

            await asyncio.sleep(0.2)

def match_word_for_level(level: str):
    if not UNCATEGORIZED_CACHE:
        return None

    for idx, item in enumerate(UNCATEGORIZED_CACHE):
        if item.get("level") == level:
            return UNCATEGORIZED_CACHE.pop(idx)
            
    return UNCATEGORIZED_CACHE.pop(0)

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
        # เมื่อหมดเวลา ให้ลบข้อความเดิมทิ้งและสร้างข้อความใหม่ขึ้นมาเองอัตโนมัติ
        if self.message:
            try:
                channel = self.message.channel
                await self.message.delete()
                embed = discord.Embed(
                    title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
                    description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามได้เลยครับ:", 
                    color=0xF1C40F
                )
                new_view = LevelSelectView()
                new_msg = await channel.send(embed=embed, view=new_view)
                new_view.message = new_msg
            except Exception:
                pass

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass

            if choice == self.correct_answer:
                embed = discord.Embed(title="🎉 ถูกต้องครับ!", description=f"คำตอบคือ:\n**{choice}**", color=0x2ECC71)
            else:
                embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**", color=0xE74C3C)

            for item in self.children:
                item.disabled = True

            try:
                await interaction.edit_original_response(view=self)
                next_embed = discord.Embed(title="🎮 เล่นคำต่อไป", description="เลือกระดับความยากด้านล่างเพื่อเล่นต่อได้เลยครับ:", color=0xF1C40F)
                next_view = LevelSelectView()
                sent_msg = await interaction.followup.send(embeds=[embed, next_embed], view=next_view)
                next_view.message = sent_msg
            except Exception:
                pass
        return callback

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None

    async def on_timeout(self):
        # เมื่อเกินเวลาที่กำหนด ลบข้อความตัวเองแล้วเริ่มเมนูใหม่ขึ้นมาแทน
        if self.message:
            try:
                channel = self.message.channel
                await self.message.delete()
                embed = discord.Embed(
                    title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
                    description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามได้เลยครับ:", 
                    color=0xF1C40F
                )
                new_view = LevelSelectView()
                new_msg = await channel.send(embed=embed, view=new_view)
                new_view.message = new_msg
            except Exception:
                pass

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

        quiz_data = match_word_for_level(level)

        if quiz_data:
            embed = discord.Embed(
                title=f"🎯 ทายคำศัพท์ระดับ {level}",
                description=f"คำศัพท์: **{quiz_data['word']}**\n\nคำแปลภาษาไทยคือข้อใด?:",
                color=0x3498DB
            )
            
            try:
                quiz_view = QuizChoiceView(quiz_data["correct"], quiz_data["choices"])
                sent_msg = await interaction.followup.send(embed=embed, view=quiz_view)
                quiz_view.message = sent_msg
            except Exception:
                pass
        else:
            embed = discord.Embed(
                title="⏳ กำลังเตรียมคำศัพท์ใหม่...",
                description=f"กำลังโหลดคำศัพท์พื้นฐานสำหรับเด็กจากอินเทอร์เน็ต\n\n**กรุณากดปุ่มอีกครั้งใน 1-2 วินาทีครับ**",
                color=0xE67E22
            )
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="A0 (เด็กอนุบาล/ง่ายสุดๆ)", style=discord.ButtonStyle.primary)
    async def btn_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A0")

    @discord.ui.button(label="A1 (ประถมต้น/ง่าย)", style=discord.ButtonStyle.primary)
    async def btn_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A1")

    @discord.ui.button(label="A2 (ประถมปลาย/ปานกลาง)", style=discord.ButtonStyle.primary)
    async def btn_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A2")

    @discord.ui.button(label="B1 (มัธยมต้น/ท้าทาย)", style=discord.ButtonStyle.success)
    async def btn_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B1")

    @discord.ui.button(label="B2 (มัธยมปลาย/ยากขึ้น)", style=discord.ButtonStyle.success)
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
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามได้เลยครับ:", 
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
    
