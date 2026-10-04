import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# กำหนดหมวดหมู่คำศัพท์เพื่อบีบ scope ให้อยู่ในระดับ CEFR A0 - B2
TOPIC_MAP = {
    "A0": ["color", "animal", "number", "food", "family"],
    "A1": ["home", "school", "clothes", "time", "body", "city"],
    "A2": ["travel", "weather", "work", "hobby", "health", "nature"],
    "B1": ["business", "feeling", "society", "media", "science", "art"],
    "B2": ["opinion", "process", "system", "culture", "law", "economy"]
}

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# 1. Generate สุ่มคำศัพท์ภาษาอังกฤษสดๆ จาก Datamuse API ตามระดับความยาก
async def generate_english_word(session, level: str):
    topic = random.choice(TOPICS_MAP.get(level, TOPIC_MAP["A1"]))
    # สุ่มอักษรตัวแรกเพื่อไม่ให้ได้คำซ้ำเดิม
    random_char = random.choice("abcdefghijklmnopqrstuvwxyz")
    url = f"https://api.datamuse.com/words?ml={topic}&sp={random_char}*&max=20"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
            if resp.status == 200:
                data = await resp.json()
                words = [
                    item["word"] for item in data 
                    if item["word"].isalpha() and 3 <= len(item["word"]) <= 8
                ]
                if words:
                    return random.choice(words)
    except Exception:
        pass
    return "example"

# 2. Generate แปลคำศัพท์หลักเป็นภาษาไทยผ่าน API
async def generate_thai_translation(session, word: str):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                raw_text = data['responseData']['translatedText'].strip()
                clean_text = raw_text.split(',')[0].split(';')[0].strip()
                if clean_text.lower() != word.lower() and len(clean_text) < 30:
                    return clean_text
    except Exception:
        pass
    return f"ความหมายของ {word}"

# 3. Generate ช้อยส์หลอกภาษาไทยสดๆ ที่อ้างอิงจากคำแปลใกล้เคียง
async def generate_fake_choices(session, level: str):
    # ดึงคำศัพท์หลอก 3 คำ
    tasks = [generate_english_word(session, level) for _ in range(3)]
    fake_words = await asyncio.gather(*tasks)
    
    # แปลคำศัพท์หลอกเป็นภาษาไทยพร้อมกัน
    trans_tasks = [generate_thai_translation(session, w) for w in fake_words]
    fake_translations = await asyncio.gather(*trans_tasks)
    
    return fake_translations

# View ปุ่มตอบคำถาม 4 ช้อยส์
class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer, choices):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer

        for choice in choices:
            button = discord.ui.Button(
                label=choice[:80],
                style=discord.ButtonStyle.secondary
            )
            button.callback = self.make_callback(choice)
            self.add_item(button)

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            if choice == self.correct_answer:
                embed = discord.Embed(
                    title="🎉 ถูกต้องครับ!",
                    description=f"คำตอบที่ถูกต้องคือ:\n**{choice}**",
                    color=0x2ECC71
                )
            else:
                embed = discord.Embed(
                    title="❌ ยังไม่ถูกต้องครับ",
                    description=f"คุณเลือก: {choice}\n\nคำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**",
                    color=0xE74C3C
                )

            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

            next_embed = discord.Embed(
                title="🎮 เล่นคำต่อไป",
                description="เลือกระดับความยากด้านล่างเพื่อเริ่มทายคำต่อไปได้เลยครับ:",
                color=0xF1C40F
            )
            await interaction.followup.send(embeds=[embed, next_embed], view=LevelSelectView())
        return callback

# View เลือกระดับความยาก (A0 - B2)
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        # 1. แจ้งสถานะการประมวลผลทันที
        loading_embed = discord.Embed(
            title="⚡ กำลัง Generate คำศัพท์สด...",
            description="คาดว่าจะใช้เวลาประมาณ **1 - 2 วินาที**",
            color=0xE67E22
        )
        await interaction.response.send_message(embed=loading_embed)

        # 2. รันระบบ Generate แบบ Parallel
        async with aiohttp.ClientSession() as session:
            # Generate คำศัพท์หลัก
            target_word = await generate_english_word(session, level)
            
            # Generate คำแปลหลัก + ช้อยส์หลอกพร้อมกัน
            correct_th_task = generate_thai_translation(session, target_word)
            fake_choices_task = generate_fake_choices(session, level)
            
            correct_th, fake_choices = await asyncio.gather(correct_th_task, fake_choices_task)

            # รวมช้อยส์และตัดตัวเลือกที่ซ้ำกัน
            choices_set = {correct_th}
            for fake in fake_choices:
                if fake != correct_th:
                    choices_set.add(fake)
            
            # หากตัวเลือกไม่ครบ 4 ให้เติมช้อยส์ทั่วไป
            backup_fakes = ["สถานที่", "การกระทำ", "ความรู้สึก", "วัตถุสิ่งของ", "สถานการณ์"]
            while len(choices_set) < 4:
                choices_set.add(backup_fakes.pop())

            choices = list(choices_set)
            random.shuffle(choices)

        quiz_embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{target_word.upper()}**\n\nคำแปลภาษาไทยของคำนี้คือข้อใด?:",
            color=0x3498DB
        )

        # 3. ส่งคำถามทันที
        await interaction.edit_original_response(embed=quiz_embed, view=QuizChoiceView(correct_th, choices))

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
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ",
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถาม:",
            color=0xF1C40F
        )
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
