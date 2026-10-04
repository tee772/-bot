import os
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="t!", intents=intents)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ฟังก์ชันดึงคำศัพท์จาก API ภายนอกเท่านั้น
async def fetch_random_word():
    url = "https://random-word-api.herokuapp.com/word"
    # ตั้งค่า Timeout ไว้ที่ 3 วินาทีเพื่อป้องกันบอทค้าง
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0]
                return "Error: API Response Status Failure"
    except asyncio.TimeoutError:
        return "Error: API Request Timeout (เซิร์ฟเวอร์ตอบสนองช้า)"
    except Exception as e:
        return f"Error: {str(e)}"

class QuizView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        # 1. แจ้ง Discord ทันทีเพื่อป้องกันปุ่มขึ้น "ไม่ตอบสนอง"
        await interaction.response.defer()

        # 2. ดึงคำศัพท์จาก API ภายนอกเพียวๆ
        word = await fetch_random_word()

        if word.startswith("Error:"):
            embed = discord.Embed(
                title="❌ การเชื่อมต่อ API ขัดข้อง",
                description=f"ไม่สามารถดึงข้อมูลจาก API ได้ในขณะนี้\n`{word}`",
                color=0xE74C3C
            )
        else:
            embed = discord.Embed(
                title=f"🎯 คำถามระดับ {level} (จาก API)",
                description=f"คำศัพท์ที่สุ่มได้: **{word}**",
                color=0x3498DB
            )
            embed.set_footer(text="ข้อมูลดึงตรงจาก API แบบ Real-time")

        # 3. ส่งข้อความตอบกลับ
        await interaction.followup.send(embed=embed)

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

@bot.command(name="quiz")
async def quiz(ctx):
    embed = discord.Embed(
        title="🎯 ทายคำศัพท์ภาษาอังกฤษ (API Direct)",
        description="คลิกเลือกระดับความยากด้านล่างเพื่อดึงคำศัพท์จาก API:",
        color=0xF1C40F
    )
    await ctx.send(embed=embed, view=QuizView())

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
