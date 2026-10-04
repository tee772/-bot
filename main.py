import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# คลังคำแปลหลอกภาษาไทยที่เนียนตามระดับ
THAI_DISTRACTORS = {
    "A0": ["สุนัข", "แมว", "หนังสือ", "ปากกา", "โรงเรียน", "บ้าน", "น้ำ", "อาหาร", "รถยนต์", "เพื่อน"],
    "A1": ["ครอบครัว", "การเดินทาง", "สภาพอากาศ", "ห้องครัว", "สะพาน", "หน้าต่าง", "เสื้อผ้า", "กระเป๋า", "ความสุข", "เวลา"],
    "A2": ["โอกาส", "ประสบการณ์", "ความสำเร็จ", "การตัดสินใจ", "ข้อเสนอ", "ความรู้สึก", "เป้าหมาย", "ความสัมพันธ์", "ความช่วยเหลือ", "ความคิด"],
    "B1": ["ความกล้าหาญ", "ประสิทธิภาพ", "ข้อตกลง", "การอธิบาย", "สถานการณ์", "ผลกระทบ", "ความรับผิดชอบ", "การพัฒนา", "ความพยายาม", "ข้อสรุป"],
    "B2": ["ความกำกวม", "การวิเคราะห์", "การประเมิน", "ข้อจำกัด", "ความขัดแย้ง", "ทัศนคติ", "การคาดการณ์", "นวัตกรรม", "ความยั่งยืน", "มุมมอง"]
}

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

async def fetch_random_word():
    url = "https://random-word-api.herokuapp.com/word"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0]
    except Exception:
        pass
    return None

async def translate_to_thai(word):
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
    return "คำแปล"

# View สำหรับเลือกความยาก (A0 - B2)
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        target_word = await fetch_random_word()
        if not target_word:
            await interaction.followup.send("❌ เกิดข้อผิดพลาดในการดึงข้อมูลจาก API กรุณาลองใหม่อีกครั้ง")
            return

        correct_th = await translate_to_thai(target_word)

        # สุ่มช้อยส์หลอกเนียนๆ จาก Pool ภาษาไทยตามระดับ
        pool = THAI_DISTRACTORS.get(level, THAI_DISTRACTORS["A1"])
        fake_choices = [item for item in pool if item != correct_th]
        selected_fakes = random.sample(fake_choices, min(3, len(fake_choices)))

        choices = [correct_th] + selected_fakes
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

            # ล็อคปุ่มตอบของข้อนี้
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

            # แสดงผลการตอบ พร้อมแนบปุ่มเลือกระดับให้เล่นคำต่อไปทันที!
            next_embed = discord.Embed(
                title="🎮 เล่นคำต่อไป",
                description="เลือกระดับความยากด้านล่างเพื่อเริ่มทายคำต่อไปได้เลยครับ:",
                color=0xF1C40F
            )
            await interaction.followup.send(embeds=[embed, next_embed], view=LevelSelectView())
        return callback

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
