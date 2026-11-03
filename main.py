import os
import re
import discord
from discord.ext import commands
import requests

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=["!q ", "!q", "!"], intents=intents)

active_games = {}


def get_random_word_and_image():
  """ฟังก์ชันสุ่มดึงคำศัพท์และรูปภาพสดๆ จากอินเทอร์เน็ต (ไม่ต้องเตรียมคำศัพท์ล่วงหน้า)"""
  headers = {"User-Agent": "DiscordQuizBot/1.0 (https://discord.gg)"}

  # ลองสุ่มค้นหาคำศัพท์และรูปภาพสูงสุด 5 ครั้ง (เผื่อบางคำไม่มีรูปใน Wikimedia)
  for _ in range(5):
    try:
      # 1. ดึงคำศัพท์สุ่มภาษาอังกฤษจาก Random Word API
      word_res = requests.get(
          "https://random-word-api.herokuapp.com/word?length=5", timeout=5
      )
      if word_res.status_code != 200:
        continue

      word = word_res.json()[0].lower()

      # ตรวจสอบให้แน่ใจว่าเป็นตัวอักษรภาษาอังกฤษเท่านั้น
      if not re.match("^[a-z]+$", word):
        continue

      # 2. นำคำศัพท์ไปค้นหารูปภาพจาก Wikimedia Commons API
      wiki_url = (
          "https://commons.wikimedia.org/w/api.php?"
          f"action=query&generator=search&gsrsearch={word}&gsrnamespace=6&gsrlimit=1"
          "&prop=imageinfo&iiprop=url&format=json"
      )

      wiki_res = requests.get(wiki_url, headers=headers, timeout=5)
      if wiki_res.status_code == 200:
        data = wiki_res.json()
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_info in pages.items():
          image_info = page_info.get("imageinfo", [])
          if image_info:
            image_url = image_info[0].get("url")
            # ตรวจสอบว่าเป็นไฟล์รูปภาพทั่วไป (JPG, PNG)
            if image_url and image_url.lower().endswith(
                (".jpg", ".jpeg", ".png")
            ):
              return word, image_url
    except Exception as e:
      print(f"Fetch error: {e}")
      continue

  return None, None


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("100% Dynamic Online Quiz Bot is ready!")


@bot.command(name="quiz", aliases=["q"], help="สุ่มคำและรูปจากเน็ตแบบสดๆ")
async def start_quiz(ctx):
  channel_id = ctx.channel.id

  await ctx.send("🌐 กำลังสุ่มดึงคำศัพท์และรูปภาพตรงจากอินเทอร์เน็ต...")

  word, image_url = get_random_word_and_image()

  if not word or not image_url:
    await ctx.send(
        "⚠️ ไม่สามารถดึงรูปภาพจากอินเทอร์เน็ตได้ในขณะนี้ กรุณาลองใช้อีกครั้ง!"
    )
    return

  active_games[channel_id] = {"answer": word}

  embed = discord.Embed(
      title="🎮 **เกมทายคำศัพท์ภาษาอังกฤษ!**",
      description=(
          "ทายซิว่ารูปนี้คืออะไร? (พิมพ์ตอบได้เลย)\n"
          f"💡 **ใบ้:** ความยาว {len(word)} ตัวอักษร | ขึ้นต้นด้วย **'{word[0].upper()}'**"
      ),
      color=discord.Color.green(),
  )
  embed.set_image(url=image_url)

  await ctx.send(embed=embed)


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
          f"🎉 ยินดีด้วยครับคุณ {message.author.mention}! ตอบถูกต้อง คำตอบคือ"
          f" **{correct_answer.upper()}**"
      )
      del active_games[channel_id]

  await bot.process_commands(message)


TOKEN = os.getenv("TOKEN")
if not TOKEN:
  print("Error: ไม่พบ TOKEN")
else:
  bot.run(TOKEN)
    
