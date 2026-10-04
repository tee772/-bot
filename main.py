import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# กำหนดช่วงความถี่คำศัพท์ (Frequency Score) ตามระดับความยาก A0 - B2
# ค่า f ยิ่งสูง = คำศัพท์ยิ่งพื้นฐาน/ง่าย
LEVEL_FREQ_MAP = {
    "A0": (100.0, 500.0), # คำพื้นฐานที่สุดในชีวิตประจำวัน
    "A1": (30.0, 99.9),
    "A2": (10.0, 29.9),
    "B1": (3.0, 9.9),
    "B2": (1.0, 2.9)      # คำศัพท์เฉพาะหรือซับซ้อนขึ้น
}

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# 1. Generate สุ่มคำศัพท์ภาษาอังกฤษที่ตรงตามระดับความยากจาก Datamuse API
async def fetch_word_by_level(level: str):
    min_f, max_f = LEVEL_FREQ_MAP.get(level, (10.0, 30.0))
    # สุ่มอักษรตัวแรกเพื่อให้ได้คำศัพท์ที่หลากหลาย
    random_letter = random.choice("abcdefghijklmnopqrstuvwxyz")
    url = f"https://api.datamuse.com/words?sp={random_letter}*&md=f&max=100"
    
    timeout = aiohttp.ClientTimeout(total=4)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    valid_words = []
                    for item in data:
                        word = item.get("word", "")
                        # คัดเฉพาะคำศัพท์เดี่ยวที่เป็นตัวอักษรบริสุทธิ์
                        if word.isalpha() and 2 < len(word) < 12:
                            tags = item.get("tags", [])
                            for tag in tags:
                                if tag.startswith("f:"):
                                    try:
                                        score = float(tag.split(":")[1])
                                        if min_f <= score <= max_f:
                                            valid_words.append(word)
                                    except ValueError:
                                        pass
                    if valid_words:
                        return random.choice(valid_words)
    except Exception:
        pass
    
    # หากสุ่มสัญลักษณ์ตัวอักษรแล้วไม่พบ ให้ใช้ API สุ่มคำทั่วไปแทน
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://random-word-api.herokuapp.com/word") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0]
    except Exception:
        pass
    return "example"

# 2. Generate คำแปลภาษาไทยสดๆ ผ่าน Translation API
async def translate_to_thai(word: str):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translation = data['responseData']['translatedText']
                    if translation.lower() != word.lower():
                        return translation
    except Exception:
        pass
    return f"คำแปลของ {word}"

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

# View สำหรับเลือกระดับความยาก (A0 - B2)
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        # 1. Generate สุ่มคำศัพท์หลัก และคำศัพท์หลอก 3 คำตรงตามระดับที่กดทันที
        target_word = await fetch_word_by_level(level)
        fake_word1 = await fetch_word_by_level(level)
        fake_word2 = await fetch_word_by_level(level)
        fake_word3 = await fetch_word_by_level(level)

        # 2. Generate แปลคำศัพท์ทั้งหมดเป็นภาษาไทยสดๆ จาก API
        correct_th = await translate_to_thai(target_word)
        fake_th1 = await translate_to_thai(fake_word1)
        fake_th2 = await translate_to_thai(fake_word2)
        fake_th3 = await translate_to_thai(fake_word3)

        # 3. รวบรวมตัวเลือกและป้องกันตัวเลือกซ้ำกัน
        choices_set = {correct_th, fake_th1, fake_th2, fake_th3}
        
        # หากได้คำแปลซ้ำกัน ให้ดึงคำศัพท์ใหม่มาแปลเติมจนครบ 4 ช้อยส์
        while len(choices_set) < 4:
            extra_word = await fetch_word_by_level(level)
            extra_th = await translate_to_thai(extra_word)
            choices_set.add(extra_th)

        choices = list(choices_set)
        random.shuffle(choices)

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{target_word.upper()}**\n\nคำแปลภาษาไทยของคำนี้คือข้อใด?:",
            color=0x3498DB
        )
        embed.set_footer(text="คำศัพท์และคำแปลถูก Generate สดๆ จาก API ตรงตามระดับความยาก")

        await interaction.followup.send(embed=embed, view=QuizChoiceView(correct_th, choices))

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
    
