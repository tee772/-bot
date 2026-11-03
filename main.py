import os
import random
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=["!q ", "!q", "!"], intents=intents)

QUIZ_DATA = {
    "cat.jpg": "cat",
    "apple.jpg": "apple",
    "car.jpg": "car",
}

active_games = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready to play quiz!")

@bot.command(name="quiz", aliases=["q"], help="เริ่มเกมทายภาพจากรูปภาพ")
async def start_quiz(ctx):
    channel_id = ctx.channel.id
    if not QUIZ_DATA:
        await ctx.send("ยังไม่มีรูปภาพในระบบ กรุณาเพิ่มรูปภาพก่อน!")
        return

    image_filename = random.choice(list(QUIZ_DATA.keys()))
    answer = QUIZ_DATA[image_filename]
    image_path = os.path.join("images", image_filename)

    if not os.path.exists(image_path):
        await ctx.send(f"⚠️ ไม่พบไฟล์รูปภาพ `{image_filename}` ในโฟลเดอร์ `images/`")
        return

    active_games[channel_id] = {"answer": answer.lower()}

    file = discord.File(image_path, filename=image_filename)
    await ctx.send(
        "🎮 **เกมทายคำศัพท์มาแล้ว!** ทายซิว่ารูปนี้คืออะไร? (พิมพ์ตอบได้เลย)"
        f" (ความยาว: {len(answer)} ตัวอักษร)",
        file=file,
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    if channel_id in active_games:
        user_answer = message.content.strip().lower()
        correct_answer = active_games[channel_id]["answer"]

        if user_answer == correct_answer:
            await message.channel.send(
                f"🎉 ยินดีด้วยครับคุณ {message.author.mention}! ตอบถูกต้อง คำตอบคือ **{correct_answer.upper()}**"
            )
            del active_games[channel_id]

    await bot.process_commands(message)

# ดึง Token จากระบบตั้งค่าของโฮสต์ (ปลอดภัย ไม่ถูกแฮกผ่าน GitHub)
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("Error: ไม่พบ TOKEN กรุณาตั้งค่า Environment Variable ชื่อ TOKEN ในโฮสต์")
else:
    bot.run(TOKEN)
    
