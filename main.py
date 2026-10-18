import json
import re
import random
import asyncio
import os
import discord
from discord.ext import commands
from huggingface_hub import InferenceClient
from difflib import SequenceMatcher

# ==========================================
# ⚙️ 1. ตั้งค่าการเชื่อมต่อ (ดึงค่าจาก Environment Variables)
# ==========================================
TARGET_CHANNEL_ID = 1555905970050437206
BOT_TOKEN = os.getenv("")
HF_API_KEY = os.getenv("HF_API_KEY")

# เรียกใช้งาน Hugging Face Inference Client
hf_client = InferenceClient(
    model="Qwen/Qwen2.5-72B-Instruct",
    token=HF_API_KEY
)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ตัวแปรเก็บสถานะโจทย์ที่กำลังเล่น และประวัติประโยคที่เคยใช้
channel_active_quizzes = {}
used_sentences_history = []

# ==========================================
# 🧠 2. ฟังก์ชัน AI เจนโจทย์ฝึกแปลภาษาไทย -> อังกฤษ
# ==========================================
async def generate_sentence_with_hf(level_name: str):
    global used_sentences_history
    random_seed = random.randint(10000, 99999)
    topics = [
        "daily life and routines", "food, cooking, and dining", 
        "weather and seasonal activities", "hobbies, sports, and entertainment", 
        "travel, places, and transportation", "family, friends, and relationships", 
        "work, studies, and career", "shopping and technology", "feelings and health"
    ]
    selected_topic = random.choice(topics)
    history_str = ", ".join(used_sentences_history[-20:]) if used_sentences_history else "None"
    
    prompt = f"""
    You are an expert English teacher creating a translation quiz for Thai students learning English.
    Task: Create ONE natural Thai sentence with its accurate English translation.
    
    Difficulty Level: {level_name}
    Topic: {selected_topic}
    Random Seed: {random_seed}
    Previously used English sentences (DO NOT REPEAT): [{history_str}]
    
    Level Criteria:
    - A0: Very simple, 2-4 words in English (e.g., "ฉันชอบแมว" -> "I like cats.")
    - A1: Basic everyday, 4-6 words in English (e.g., "เธอดื่มนมทุกวัน" -> "She drinks milk every day.")
    - A2: Conversational, 5-8 words in English (e.g., "เมื่อวานฉันไปตลาดมา" -> "I went to the market yesterday.")
    - B1/B2: Natural, intermediate English expressions and idioms.
    
    Output Requirement:
    - MUST return strictly valid JSON format: {{"th": "ประโยคภาษาไทย", "en": "English translation"}}
    - Use ONLY Thai and English text.
    """

    loop = asyncio.get_event_loop()
    
    def call_api():
        response = hf_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful English teacher API. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.95
        )
        return response.choices[0].message.content.strip()

    try:
        raw_text = await loop.run_in_executor(None, call_api)
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)

        data = json.loads(raw_text)
        th_res = data["th"].strip()
        en_res = data["en"].strip()
        
    except Exception as e:
        print(f"API Error / Fallback triggered: {e}")
        fallback_list = [
            ("ฉันชอบกินแอปเปิ้ลสดๆ ในตอนเช้า", "I love eating fresh apples in the morning."),
            ("เขาเล่นฟุตบอลกับเพื่อนๆ ทุกวันหยุด", "He plays football with his friends every weekend."),
            ("ขอโทษนะครับ ห้องสมุดที่ใกล้ที่สุดอยู่ที่ไหน", "Excuse me, where is the nearest library?"),
            ("วันนี้อากาศดีและมีแดดจัดมาก", "The weather is very nice and sunny today."),
            ("เธอกำลังอ่านหนังสืออย่างเงียบๆ ในห้อง", "She is quietly reading a book in her room."),
            ("ฉันมักจะดื่มกาแฟร้อนก่อนเริ่มทำงาน", "I usually drink hot coffee before starting work.")
        ]
        th_res, en_res = random.choice(fallback_list)
    
    used_sentences_history.append(en_res)
    if len(used_sentences_history) > 40:
        used_sentences_history.pop(0)
        
    return th_res, en_res

# ==========================================
# 🧠 3. ฟังก์ชัน AI ตรวจคำตอบการแปล
# ==========================================
async def check_answer_with_ai(target_th: str, target_en: str, user_ans: str) -> bool:
    u_clean = re.sub(r"[^\w\s]", "", user_ans.lower().strip())
    e_clean = re.sub(r"[^\w\s]", "", target_en.lower().strip())

    # 1. ถ้าพิมพ์ตรงเป๊ะถือว่าผ่านทันที
    if u_clean == e_clean:
        return True

    # 2. ให้ AI ตรวจสอบว่าความหมายภาษาอังกฤษถูกต้องตามโจทย์ภาษาไทยหรือไม่
    prompt = f"""
    You are an English teacher evaluating a student's translation.
    
    Thai Source: "{target_th}"
    Expected English: "{target_en}"
    Student's Answer: "{user_ans}"
    
    Question: Is the student's answer an accurate and grammatically correct English translation of the Thai sentence?
    Respond with ONLY one word: "CORRECT" or "INCORRECT".
    """

    loop = asyncio.get_event_loop()
    
    def call_api():
        response = hf_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a strict English evaluator. Respond ONLY with 'CORRECT' or 'INCORRECT'."},
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
# 🔘 4. UI components (ปุ่มกดเลือกเลเวล / ปุ่มข้าม)
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
                description=f"โจทย์ภาษาไทย: **\"{quiz_data['th']}\"**\n\nแปลเป็นภาษาอังกฤษที่ถูกต้องคือ:\n`{answer}`\n\n*(เลือกความยากด้านล่างเพื่อเริ่มข้อต่อไปได้เลย)*",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            await interaction.channel.send(
                embed=discord.Embed(title="🎯 เลือกระดับความยากข้อต่อไป:", color=discord.Color.gold()), 
                view=QuizLevelView()
            )
        else:
            await interaction.response.send_message("⚠️ ไม่พบข้อสอบที่กำลังเล่นอยู่ครับ", ephemeral=True)

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
            th_sentence, en_sentence = await generate_sentence_with_hf(level_name)

            channel_active_quizzes[channel_id] = {
                "th": th_sentence,
                "en": en_sentence,
                "level": level_name,
                "started_by": interaction.user.mention,
                "wrong_count": 0
            }

            embed = discord.Embed(
                title=f"📝 โจทย์ฝึกแปลภาษาอังกฤษ ({level_name})",
                description=f"ผู้กดเริ่ม: {interaction.user.mention}\n\nแปลประโยคภาษาไทยนี้เป็นภาษาอังกฤษ:\n> **\"{th_sentence}\"**\n\n*(พิมพ์คำตอบลงในช่องแชทได้เลย หรือกดปุ่มข้ามหากยอมแพ้)*",
                color=discord.Color.purple()
            )
            await interaction.followup.send(embed=embed, view=SkipQuizView(channel_id))

        except Exception as e:
            print(f"Error generating sentence: {e}")
            await interaction.followup.send("⚠️ เกิดข้อผิดพลาด กรุณากดปุ่มเพื่อลองใหม่อีกครั้งครับ", ephemeral=True)

# ==========================================
# 💬 5. คำสั่งและระบบรับข้อความ
# ==========================================
@bot.command(name="quiz")
async def start_quiz(ctx):
    embed = discord.Embed(
        title="🎯 เมนูฝึกแปลประโยคภาษาอังกฤษ",
        description="เลือกความยากที่ต้องการเพื่อสุ่มโจทย์ภาษาไทยสำหรับฝึกแปลได้เลยครับ!",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=QuizLevelView())

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
                    title="🎯 เลือกระดับความยากข้อต่อไปได้เลยครับ:",
                    color=discord.Color.gold()
                )
                await message.channel.send(content=msg, embed=embed, view=QuizLevelView())
            else:
                quiz_data["wrong_count"] += 1
                
                if quiz_data["wrong_count"] >= 3:
                    hint = f"\n💡 **เฉลยคำตอบ:** `{quiz_data['en']}`"
                    await message.channel.send(
                        f"❌ **ผิดครบ 3 ครั้งแล้วครับ!** {message.author.mention}{hint}\n*(กดเลือกความยากเพื่อเริ่มเล่นข้อต่อไปได้เลยครับ)*"
                    )
                    del channel_active_quizzes[channel_id]
                    await message.channel.send(
                        embed=discord.Embed(title="🎯 เลือกระดับความยากข้อต่อไป:", color=discord.Color.gold()), 
                        view=QuizLevelView()
                    )
                else:
                    await message.channel.send(
                        f"❌ **ยังไม่ถูกต้องครับ!** {message.author.mention} ลองแปลใหม่อีกครั้งนะครับ (ผิดครั้งที่ {quiz_data['wrong_count']}/3)"
                    )

# ==========================================
# 🚀 6. รันบอท
# ==========================================
@bot.event
async def on_ready():
    print(f"✅ บอทฝึกแปลภาษาพร้อมใช้งานแล้ว: {bot.user.name}")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
    
