import os
import random
import aiohttp
import discord
from discord.ext import commands

# ตั้งค่า Prefix เป็น t!
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="t!", intents=intents)

# ซ่อน Error CommandNotFound ไม่ให้รก Termux
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

class QuizView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60) # ตั้งเวลาปุ่มหมดอายุ (60 วินาที)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        # 1. แจ้ง Discord ทันทีว่ากำลังประมวลผล (แก้ปัญหา "แอปไม่ตอบสนอง")
        await interaction.response.defer()
        
        # 2. ดึงข้อมูลคำศัพท์จาก API (หรือสุ่มคำศัพท์)
        # ตัวอย่างการส่งข้อความตอบกลับหลังจาก defer
        await interaction.followup.send(f"คุณเลือกความยากระดับ: **{level}**\nกำลังสุ่มคำศัพท์...", ephemeral=True)

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
        title="🎯 ทายคำศัพท์ภาษาอังกฤษ (Auto-Generated)",
        description="คลิกเลือกความยากด้านล่าง บอทจะสุ่มคำศัพท์ใหม่จาก API ให้ทันที:",
        color=0xF1C40F
    )
    await ctx.send(embed=embed, view=QuizView())

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)

