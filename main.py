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

# ดึงคำศัพท์ภาษาอังกฤษสุ่มจาก API
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

# แปลคำศัพท์ภาษาอังกฤษเป็นแปลภาษาไทยผ่าน Translation API
async def translate_to_thai(word):
    url = f"https://api.mymemory.translated.net/get?q={word}&langpair=en|th"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translation = data['responseData']['translatedText']
                    # ป้องกันกรณี API คืนค่าคำเดิม
                    if translation.lower() != word.lower():
                        return translation
    except Exception:
        pass
    return "คำแปลภาษาไทย"

# View สำหรับสร้างปุ่มช้อยส์คำแปลภาษาไทย 4 ปุ่ม
class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer, choices):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer

        for choice in choices:
            button = discord.ui.Button(
                label=choice[:80], # ข้อความปุ่มคำแปลไทย
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
            await interaction.followup.send(embed=embed)
        return callback

# View สำหรับเลือกระดับความยาก
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        # 1. ดึงคำศัพท์หลักและคำศัพท์หลอก 3 คำจาก API
        target_word = await fetch_random_word()
        fake_word1 = await fetch_random_word()
        fake_word2 = await fetch_random_word()
        fake_word3 = await fetch_random_word()

        if not target_word:
            await interaction.followup.send("❌ เกิดข้อผิดพลาดในการดึงข้อมูลจาก API กรุณาลองใหม่อีกครั้ง")
            return

        # 2. แปลคำศัพท์ทั้งหมดเป็นภาษาไทยผ่าน Translation API
        correct_th = await translate_to_thai(target_word)
        fake_th1 = await translate_to_thai(fake_word1) if fake_word1 else "การเปลี่ยนแปลง"
        fake_th2 = await translate_to_thai(fake_word2) if fake_word2 else "ความสัมพันธ์"
        fake_th3 = await translate_to_thai(fake_word3) if fake_word3 else "การดำเนินการ"

        # 3. รวมตัวเลือกภาษาไทย 4 ช้อยส์แล้วสุ่มลำดับปุ่ม
        choices = [correct_th, fake_th1, fake_th2, fake_th3]
        # ป้องกันตัวเลือกซ้ำกัน
        choices = list(set(choices))
        while len(choices) < 4:
            choices.append(f"ตัวเลือกสำรอง {len(choices)+1}")
        random.shuffle(choices)

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{target_word.upper()}**\n\nคำแปลภาษาไทยของคำนี้คือข้อใด? (เลือกตอบด้านล่าง):",
            color=0x3498DB
        )
        embed.set_footer(text="ข้อมูลดึงและแปลตรงจาก API แบบ Real-time")

        await interaction.followup.send(embed=embed, view=QuizChoiceView(correct_th, choices))

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

    @discord.ui.button(label="C1/C2", style=discord.ButtonStyle.danger)
    async def btn_c1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "C1/C2")

# พิมพ์ 't!' หรือ '!t' สั้นๆ เพื่อเริ่มเกม
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ",
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามและ 4 ตัวเลือกภาษาไทย:",
            color=0xF1C40F
        )
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
