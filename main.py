import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# เมล็ดคำศัพท์พื้นฐานสุดๆ สำหรับเป็นต้นทางสุ่มคำทั่วไป
SEED_WORDS = [
    "time", "person", "year", "way", "day", "thing", "man", "world", "life", "hand",
    "part", "child", "eye", "woman", "place", "work", "week", "case", "point", "company",
    "number", "group", "problem", "fact", "home", "water", "room", "mother", "area", "money"
]

# คลังคำศัพท์กลางที่ผ่านการกรองความถี่แล้ว
UNCATEGORIZED_CACHE = []
USED_WORDS = set()

BACKUP_FAKES = [
    "ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", 
    "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("🚀 เริ่มระบบดึงคำศัพท์ง่ายใช้งานจริง (Frequency-Filtered Stream)...")
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

async def build_quiz_item(session, word: str, score: float):
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
            "length": len(word),
            "freq": score
        }
    return None

# ระบบดึงข้อมูลแบบกรองความถี่ (Frequency-Based Fetching)
async def background_word_fetcher():
    async with aiohttp.ClientSession() as session:
        while True:
            if len(UNCATEGORIZED_CACHE) < 200:
                seed = random.choice(SEED_WORDS)
                # ดึงข้อมูลพร้อมสถิติความถี่คำ (md=f)
                url = f"https://api.datamuse.com/words?ml={seed}&md=f&max=50"
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            candidates = []
                            for item in data:
                                w = item.get("word", "").strip()
                                tags = item.get("tags", [])
                                
                                # ดึงค่าความถี่ (f: frequency count)
                                freq_score = 0.0
                                for tag in tags:
                                    if tag.startswith("f:"):
                                        try:
                                            freq_score = float(tag.split(":")[1])
                                        except ValueError:
                                            pass
                                
                                # กรองเอาเฉพาะคำที่เป็นตัวอักษรบริสุทธิ์ และมีความถี่ในการใช้งานสูง (> 10.0)
                                # เพื่อตัดศัพท์ยาก ศัพท์โบราณ หรือศัพท์เฉพาะทางทิ้งทั้งหมด
                                if w.isalpha() and freq_score > 10.0 and len(w) >= 3:
                                    candidates.append((w, freq_score))

                            random.shuffle(candidates)
                            
                            for w, freq_score in candidates:
                                w_upper = w.upper()
                                if w_upper not in USED_WORDS:
                                    quiz = await build_quiz_item(session, w_upper, freq_score)
                                    if quiz:
                                        UNCATEGORIZED_CACHE.append(quiz)
                                        USED_WORDS.add(w_upper)
                                        print(f"✅ [FETCHED EASY WORD] {w_upper} (ยาว:{len(w_upper)}, ความถี่:{freq_score}) | ในคลัง: {len(UNCATEGORIZED_CACHE)} คำ")
                                        await asyncio.sleep(0.1)
                                        break
                except Exception as e:
                    print(f"⚠️ Fetch Note: {e}")

            await asyncio.sleep(0.2)

# ฟังก์ชั่นคัดเลือกคำศัพท์ตามระดับความง่ายจริง (ความถี่สูง + ความยาวเหมาะสม)
def match_word_for_level(level: str):
    if not UNCATEGORIZED_CACHE:
        return None

    # จัดระดับโดยใช้ทั้ง "ความถี่การใช้จริง (freq)" และ "ความยาวคำ (length)"
    level_filters = {
        # A0: คำสั้นมากๆ และใช้บ่อยมากที่สุดในชีวิตประจำวัน
        "A0": lambda item: item["length"] <= 4 and item["freq"] >= 50.0,
        # A1: คำสั้น และใช้บ่อยมาก
        "A1": lambda item: item["length"] <= 5 and item["freq"] >= 30.0,
        # A2: คำทั่วไปในชีวิตประจำวัน
        "A2": lambda item: 4 <= item["length"] <= 6 and item["freq"] >= 20.0,
        # B1: คำยาวปานกลาง พบเห็นทั่วไป
        "B1": lambda item: 5 <= item["length"] <= 7 and item["freq"] >= 10.0,
        # B2: คำยาวหรือซับซ้อนขึ้น
        "B2": lambda item: item["length"] >= 7
    }

    filter_func = level_filters.get(level, lambda item: True)
    
    # ค้นหาคำที่ตรงตามเกณฑ์ความง่ายของระดับนั้น
    for idx, item in enumerate(UNCATEGORIZED_CACHE):
        if filter_func(item):
            return UNCATEGORIZED_CACHE.pop(idx)
            
    # หากไม่มีคำตรงเงื่อนไขเป๊ะๆ ให้ดึงคำที่มีค่าความถี่สูงสุด (ง่ายที่สุด) ออกมาตอบแทน
    UNCATEGORIZED_CACHE.sort(key=lambda x: x["freq"], reverse=True)
    return UNCATEGORIZED_CACHE.pop(0)

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
                await interaction.followup.send(embeds=[embed, next_embed], view=LevelSelectView())
            except Exception:
                pass
        return callback

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

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
                await interaction.followup.send(embed=embed, view=QuizChoiceView(quiz_data["correct"], quiz_data["choices"]))
            except Exception:
                pass
        else:
            embed = discord.Embed(
                title="⏳ กำลังเตรียมคำศัพท์ใหม่...",
                description=f"กำลังโหลดคำศัพท์ที่ใช้บ่อยในชีวิตประจำวันจากอินเทอร์เน็ต\n\n**กรุณากดปุ่มอีกครั้งใน 1-2 วินาทีครับ**",
                color=0xE67E22
            )
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="A0 (ง่ายมากๆ)", style=discord.ButtonStyle.primary)
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

    @discord.ui.button(label="🔄 เริ่มใหม่ / เรียกเมนู (!t)", style=discord.ButtonStyle.danger)
    async def btn_reboot(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
            await interaction.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (คำศัพท์ใช้งานจริง)", 
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มทายคำศัพท์ได้เลยครับ:", 
            color=0xF1C40F
        )
        try:
            await interaction.channel.send(embed=embed, view=LevelSelectView())
        except Exception:
            pass

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
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
