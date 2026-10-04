import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ดึงคำศัพท์ภาษาอังกฤษที่เน้นคำใช้จริงในชีวิตประจำวันผ่าน Datamuse Vocabulary API
async def fetch_common_word(level: str):
    # กำหนดหัวข้อ/หมวดหมู่คำศัพท์ที่พบบ่อยตามระดับ
    topics = {
        "A0": ["family", "color", "animal", "number", "food"],
        "A1": ["home", "school", "clothes", "time", "body"],
        "A2": ["travel", "weather", "work", "hobby", "health"],
        "B1": ["business", "feeling", "society", "nature", "media"],
        "B2": ["science", "culture", "opinion", "process", "system"]
    }
    
    topic = random.choice(topics.get(level, topics["A1"]))
    url = f"https://api.datamuse.com/words?topics={topic}&max=40"
    
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # คัดเฉพาะคำศัพท์ยาว 3-8 ตัวอักษรที่ไม่ซับซ้อนเกินไป
                    filtered = [
                        item["word"] for item in data 
                        if item["word"].isalpha() and 3 <= len(item["word"]) <= 8
                    ]
                    if filtered:
                        return random.choice(filtered)
    except Exception:
        pass
    return "water"

# แปลคำศัพท์เป็นภาษาไทย และขัดเกลาคำแปลให้อ่านง่าย
async def fetch_clean_thai_translation(word: str):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_text = data['responseData']['translatedText'].strip()
                    # คัดแยกเฉพาะคำแรกหากมีเครื่องหมายจุลภาค หรือตัดคำแปลกๆ ออก
                    clean_text = raw_text.split(',')[0].split(';')[0].strip()
                    if clean_text.lower() != word.lower() and len(clean_text) < 30:
                        return clean_text
    except Exception:
        pass
    return "น้ำ"

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
        await interaction.response.defer()

        # 1. สุ่มคำศัพท์หลักและคำศัพท์หลอก 3 คำจากหมวดหมู่ตามระดับ
        target_word = await fetch_common_word(level)
        fake_word1 = await fetch_common_word(level)
        fake_word2 = await fetch_common_word(level)
        fake_word3 = await fetch_common_word(level)

        # 2. แปลเป็นภาษาไทยพร้อมขัดเกลาคำแปล
        correct_th = await fetch_clean_thai_translation(target_word)
        fake_th1 = await fetch_clean_thai_translation(fake_word1)
        fake_th2 = await fetch_clean_thai_translation(fake_word2)
        fake_th3 = await fetch_clean_thai_translation(fake_word3)

        # 3. รวบรวมตัวเลือกและป้องกันตัวเลือกซ้ำกัน
        choices_set = {correct_th, fake_th1, fake_th2, fake_th3}
        while len(choices_set) < 4:
            extra_word = await fetch_common_word(level)
            extra_th = await fetch_clean_thai_translation(extra_word)
            choices_set.add(extra_th)

        choices = list(choices_set)
        random.shuffle(choices)

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{target_word.upper()}**\n\nคำแปลภาษาไทยของคำนี้คือข้อใด?:",
            color=0x3498DB
        )

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
    
