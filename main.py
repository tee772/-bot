import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

# ตั้งให้รองรับ Prefix ทั้ง 't!' และ '!t'
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

# ดึงคำศัพท์สุ่มจาก API
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

# ดึงความหมายจาก Dictionary API
async def fetch_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    meanings = data[0]['meanings'][0]['definitions'][0]['definition']
                    return meanings
    except Exception:
        pass
    return "A specific type or concept in English"

# View ปุ่มตัวเลือกคำตอบ 4 ช้อยส์
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
                    title="🎉 ถูกต้องครับ! (Correct)",
                    description=f"คำตอบที่ถูกต้องคือ:\n**{choice}**",
                    color=0x2ECC71
                )
            else:
                embed = discord.Embed(
                    title="❌ ยังไม่ถูกต้องครับ (Incorrect)",
                    description=f"คุณเลือก: {choice}\n\nคำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**",
                    color=0xE74C3C
                )
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(embed=embed)
        return callback

# View เลือกระดับความยาก
class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer()

        target_word = await fetch_random_word()
        fake_word1 = await fetch_random_word()
        fake_word2 = await fetch_random_word()
        fake_word3 = await fetch_random_word()

        if not target_word:
            await interaction.followup.send("❌ เกิดข้อผิดพลาดในการดึงข้อมูลจาก API กรุณาลองใหม่อีกครั้ง")
            return

        correct_def = await fetch_definition(target_word)
        fake_def1 = f"Definition related to {fake_word1}" if fake_word1 else "To process or transform data"
        fake_def2 = f"Definition related to {fake_word2}" if fake_word2 else "An event or state of occurrence"
        fake_def3 = f"Definition related to {fake_word3}" if fake_word3 else "Quality or condition of being free"

        choices = [correct_def, fake_def1, fake_def2, fake_def3]
        random.shuffle(choices)

        embed = discord.Embed(
            title=f"🎯 ทายคำศัพท์ระดับ {level}",
            description=f"คำศัพท์: **{target_word.upper()}**\n\nคำความหมายของคำนี้คือข้อใด? (เลือกตอบด้านล่าง):",
            color=0x3498DB
        )
        embed.set_footer(text="ข้อมูลดึงตรงจาก API แบบ Real-time")

        await interaction.followup.send(embed=embed, view=QuizChoiceView(correct_def, choices))

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

# ดักจับข้อความเมื่อพิมพ์เพียง 't!' หรือ '!t' สั้นๆ โดยไม่ต้องพิมพ์ชื่อคำสั่ง
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ",
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามและ 4 ตัวเลือกจาก API:",
            color=0xF1C40F
        )
        await message.channel.send(embed=embed, view=LevelSelectView())
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
                                      
