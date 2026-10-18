import json
import re
import random
import asyncio
import discord
from discord.ext import commands
from huggingface_hub import InferenceClient
from difflib import SequenceMatcher

# ==========================================
# ⚙️ ตั้งค่าการเชื่อมต่อ
# ==========================================
TARGET_CHANNEL_ID = 1555905970050437206
BOT_TOKEN = "MTU1NTg5OTk0MzE4MzQ1MDE4Mw.Gy0qEO.6JBccig9EbpgO3NCePLWSxs3cZsseyo8CQ1qgo"
HF_API_KEY = "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"

hf_client = InferenceClient(
    model="Qwen/Qwen2.5-72B-Instruct",
    token=HF_API_KEY
)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

channel_active_quizzes = {}
used_sentences_history = []

# ==========================================
# 🧠 1. ฟังก์ชันเจนประโยคใหม่ (ปรับปรุงใหม่ให้หลากหลายและแม่นยำขึ้น)
# ==========================================
async def generate_sentence_with_hf(level_name: str):
    global used_sentences_history
    random_seed = random.randint(10000, 99999)
    topics = [
        "animals and pets", "favorite foods and cooking", "daily routines and habits", 
        "weather and seasons", "hobbies and free time", "travel and places", 
        "family and friends", "school and studying", "sports and exercise", 
        "shopping and money", "feelings and emotions", "jobs and work life",
        "technology and gadgets", "health and lifestyle", "weekend plans"
    ]
    selected_topic = random.choice(topics)
    
    history_str = ", ".join(used_sentences_history[-20:]) if used_sentences_history else "None"
    
    prompt = f"""
    You are an expert English teacher. Generate ONE natural, everyday English sentence along with its accurate Thai translation.
    Difficulty Level: {level_name}
    Topic: {selected_topic}
    Random Seed: {random_seed}
    
    Previously used sentences (DO NOT use these or similar ones): [{history_str}]
    
    Guidelines based on levels:
    - A0: Very short, simple sentences (2-4 words) like "I like cats.", "This is red."
    - A1: Simple sentences (4-6 words) with basic grammar like "She drinks milk.", "Where is my bag?"
    - A2: Everyday spoken sentences (5-8 words) like "I went to the market.", "Can you help me?"
    - B1/B2: Natural intermediate/upper-intermediate sentences with common phrases.
    
    Strict Rules:
    - Use ONLY English and Thai. No other languages.
    - Output MUST BE strictly a valid JSON object with keys "en" and "th". Format: {{"en": "English sentence", "th": "Thai translation"}}
    """

    loop = asyncio.get_event_loop()
    
    def call_api():
        response = hf_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful English teacher API. You must respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.95
        )
        return response.choices[0].message.content.strip()

    try:
        raw_text = await loop.run_in_executor(None, call_api)
        
        # ค้นหาโครงสร้าง JSON จากข้อความที่โมเดลตอบกลับมา
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)

        data = json.loads(raw_text)
        en_res = data["en"].strip()
        th_res = data["th"].strip()
        
    except Exception as e:
        print(f"API Error / Fallback triggered: {e}")
        # ขยายรายการ Fallback ให้หลากหลายขึ้นป้องกันประโยคซ้ำซาก
        fallback_list = [
            ("I love eating fresh apples in the morning.", "ฉันชอบกินแอปเปิ้ลสดๆ ในตอนเช้า"),
            ("He plays football with his friends every weekend.", "เขาเล่นฟุตบอลกับเพื่อนๆ ทุกวันหยุดสุดสัปดาห์"),
            ("Excuse me, could you tell me where the nearest library is?", "ขอโทษนะครับ ช่วยบอกหน่อยได้ไหมว่าห้องสมุดที่ใกล้ที่สุดอยู่ที่ไหน"),
            ("The weather is absolutely nice and sunny today.", "วันนี้อากาศดีและมีแดดจัดมากๆ"),
            ("She is quietly reading an interesting book in her room.", "เธอกำลังนั่งอ่านหนังสือที่น่าสนใจอย่างเงียบๆ อยู่ในห้องของเธอ"),
            ("I usually drink a cup of hot coffee before starting work.", "ฉันมักจะดื่มกาแฟร้อนๆ หนึ่งแก้วก่อนเริ่มทำงาน"),
            ("Do you have any plans for the upcoming holiday?", "คุณมีแผนสำหรับวันหยุดที่จะถึงนี้หรือยัง"),
            ("Learning a new language requires patience and consistent practice.", "การเรียนรู้ภาษาใหม่ต้องอาศัยความอดทนและการฝึกฝนอย่างสม่ำเสมอ")
        ]
        en_res, th_res = random.choice(fallback_list)
    
    used_sentences_history.append(en_res)
    if len(used_sentences_history) > 40:
        used_sentences_history.pop(0)
        
    return en_res, th_res

# ==========================================
# 🧠 2. ฟังก์ชัน AI ตรวจคำตอบ
# ==========================================
async def check_answer_with_ai(target_th: str, target_en: str, user_ans: str) -> bool:
    u_clean = re.sub(r"[^\w\s]", "", user_ans.lower().strip())
    e_clean = re.sub(r"[^\w\s]", "", target_en.lower().strip())

    if u_clean == e_clean:
        return True

    prompt = f"""
    You are a strict English grammar teacher evaluating a student's answer.
    
    Thai sentence: "{target_th}"
    Expected English: "{target_en}"
    Student's Answer: "{user_ans}"
    
    Rules:
    - Does the student's answer accurately translate the Thai sentence with correct grammar and vocabulary?
    - If key words are wrong or meaning changes, answer INCORRECT.
    - Answer EXACTLY one word: "CORRECT" or "INCORRECT".
    """

    loop = asyncio.get_event_loop()
    
    def call_api():
        response = hf_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a strict English evaluator. Respond with ONLY 'CORRECT' or 'INCORRECT'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.0
        )
        return response.choices[0].message.content.strip()

    try:
        result = await loop.run_in_executor(None, call_api)
        return "CORRECT" in result.upper() and "INCORRECT" not in result.upper()
    except Exception as e:
        print(f"Check AI Error: {e}")
        similarity = SequenceMatcher(None, u_clean, e_clean).ratio()
        return similarity >= 0.85

# ==========================================
# 🔘 ปุ่มกดเฉลย / ข้ามโจทย์
# ==========================================
class SkipQuizView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="💡 ดูเฉลย / ข้ามข้อนี้", style=discord.ButtonStyle.danger)
    async def button_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel_id in channel_active_quizzes:
            quiz_data = channel_active_quizzes[self.channel_id]
            answer = quiz_data["en"]
            del channel_active_quizzes[self.channel_id]

            embed = discord.Embed(
                title="💡 เฉลยคำตอบ",
                description=f"โจทย์: **\"{quiz_data['th']}\"**\nคำตอบที่ถูกต้องคือ: `{answer}`\n\n*(กดเลือกความยากด้านล่างเพื่อเริ่มข้อใหม่ได้เลยครับ)*",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            await interaction.channel.send(embed=discord.Embed(title="🎯 เลือกระดับความยากข้อต่อไป:", color=discord.Color.gold()), view=QuizLevelView())
        else:
            await interaction.response.send_message("⚠️ ไม่พบข้อสอบที่กำลังเล่นอยู่ครับ", ephemeral=True)

# ==========================================
# 🔘 ปุ่มกดเลือกระดับความยาก (5 ปุ่ม)
# ==========================================
class QuizLevelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚪ Level A0 (เริ่มต้นมาก)", style=discord.ButtonStyle.secondary, row=0)
    async def button_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_quiz(interaction, "A0 - Starter")

    @discord.ui.button(label="🟢 Level A1 (เริ่มต้น)", style=discord.ButtonStyle.success, row=0)
    async def button_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_quiz(interaction, "A1 - Elementary")

    @discord.ui.button(label="🔵 Level A2 (พื้นฐาน)", style=discord.ButtonStyle.primary, row=0)
    async def button_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_quiz(interaction, "A2 - Pre-Intermediate")

    @discord.ui.button(label="🟡 Level B1 (ปานกลาง)", style=discord.ButtonStyle.primary, row=1)
    async def button_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_quiz(interaction, "B1 - Intermediate")

    @discord.ui.button(label="🔴 Level B2 (ท้าทาย)", style=discord.ButtonStyle.danger, row=1)
    async def button_b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_quiz(interaction, "B2 - Upper-Intermediate")

    async def process_quiz(self, interaction: discord.Interaction, level_name: str):
        await interaction.response.defer()

        try:
            channel_id = interaction.channel.id
            en_sentence, th_sentence = await generate_sentence_with_hf(level_name)

            channel_active_quizzes[channel_id] = {
                "en": en_sentence,
                "th": th_sentence,
                "level": level_name,
                "started_by": interaction.user.mention,
                "wrong_count": 0
            }

            embed = discord.Embed(
                title=f"📝 โจทย์ฝึกแปล ({level_name})",
                description=f"ผู้กดเริ่ม: {interaction.user.mention}\n\nแปลประโยคนี้เป็นภาษาอังกฤษ:\n> **\"{th_sentence}\"**\n\n*(พิมพ์คำตอบในช่องได้เลย หรือกดปุ่มเฉลยด้านล่างหากยอมแพ้)*",
                color=discord.Color.purple()
            )
            await interaction.followup.send(embed=embed, view=SkipQuizView(channel_id))

        except Exception as e:
            print(f"Error generating sentence: {e}")
            await interaction.followup.send("⚠️ เกิดข้อผิดพลาด กรุณากดปุ่มเพื่อลองใหม่อีกครั้งครับ", ephemeral=True)

# ==========================================
# 💬 คำสั่ง !quiz
# ==========================================
@bot.command(name="quiz")
async def start_quiz(ctx):
    embed = discord.Embed(
        title="🎯 เมนูฝึกแปลภาษาอังกฤษ",
        description="กดเลือกความยากเพื่อเริ่มสุ่มโจทย์ใหม่ได้เลยครับ (เล่นร่วมกันได้ทุกคน)",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=QuizLevelView())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Command Error: {error}")

# ==========================================
# 💬 ระบบตรวจคำตอบ
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if not message.content.startswith("!"):
        channel_id = message.channel.id

        if message.channel.id == TARGET_CHANNEL_ID and channel_id in channel_active_quizzes:
            quiz_data = channel_active_quizzes[channel_id]
            user_ans = message.content.strip()

            is_correct = await check_answer_with_ai(quiz_data["th"], quiz_data["en"], user_ans)

            if is_correct:
                msg = f"🎉 **ถูกต้องครับ!** ยอดเยี่ยมมาก {message.author.mention}\nตัวอย่างประโยค: `{quiz_data['en']}`"
                del channel_active_quizzes[channel_id]

                embed = discord.Embed(
                    title="🎯 เลือกเลเวลเพื่อเริ่มเล่นข้อต่อไปได้เลยครับ:",
                    color=discord.Color.gold()
                )
                await message.channel.send(content=msg, embed=embed, view=QuizLevelView())
            else:
                quiz_data["wrong_count"] += 1
                
                if quiz_data["wrong_count"] >= 3:
                    hint = f"\n💡 **เฉลย:** ตัวอย่างประโยคคือ `{quiz_data['en']}`"
                    await message.channel.send(f"❌ **ผิดครับ!** {message.author.mention}{hint}\n*(ลองพิมพ์ให้ตรงตามตัวอย่าง หรือกดปุ่มข้ามโจทย์เพื่อเปลี่ยนข้อได้เลยครับ)*")
                else:
                    await message.channel.send(f"❌ **ผิดครับ!** {message.author.mention} ลองใหม่อีกครั้งนะครับ (ตอบผิดครั้งที่ {quiz_data['wrong_count']}/3)")

# ==========================================
# 🚀 บอทออนไลน์
# ==========================================
@bot.event
async def on_ready():
    print(f"✅ บอทระบบพร้อมใช้งานแล้ว: {bot.user.name}")

bot.run(BOT_TOKEN)
    
