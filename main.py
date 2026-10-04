import os
import random
import aiohttp
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["t!", "!t"], intents=intents)

# ตัวอย่างรายการคำศัพท์เรียงตามความถี่จากอันดับ 1 เป็นต้นไป (Top Most Frequent Words)
# เมื่อรันจริง Background Task จะทยอยสุ่มและดึงคำตามช่วงความถี่เพื่อความหลากหลาย
TOP_5000_VOCAB = {
    "A0": [
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with",
        "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
        "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up", "out", "if",
        "about", "who", "get", "which", "go", "me", "when", "make", "can", "like", "time", "no", "just", "him",
        "know", "take", "people", "into", "year", "your", "good", "some", "could", "them", "see", "other", "than",
        "then", "now", "look", "only", "come", "its", "over", "think", "also", "back", "after", "use", "two", "how"
    ],
    "A1": [
        "work", "first", "well", "way", "even", "new", "want", "because", "any", "these", "give", "day", "most",
        "us", "great", "between", "need", "large", "home", "big", "give", "air", "small", "number", "always",
        "place", "world", "life", "hand", "part", "child", "eye", "woman", "place", "work", "week", "case", "point",
        "company", "water", "room", "mother", "area", "money", "story", "fact", "month", "lot", "right", "study",
        "book", "eye", "job", "word", "business", "issue", "side", "kind", "head", "house", "service", "friend"
    ],
    "A2": [
        "market", "guide", "health", "school", "system", "program", "question", "during", "government", "important",
        "family", "power", "problem", "court", "office", "social", "national", "student", "country", "member",
        "police", "project", "person", "history", "party", "result", "change", "reason", "research", "girl",
        "moment", "teacher", "force", "education", "foreign", "nature", "decision", "society", "season", "camera"
    ],
    "B1": [
        "strategy", "analysis", "economy", "investment", "technology", "resource", "solution", "benefit", "challenge",
        "culture", "security", "impact", "evidence", "authority", "evidence", "factor", "concept", "structure",
        "performance", "management", "financial", "production", "behavior", "consumer", "environmental", "opportunity"
    ],
    "B2": [
        "perspective", "hypothesis", "infrastructure", "subsequent", "implementation", "methodology", "phenomenon",
        "legislation", "framework", "sustainable", "fundamental", "interpretation", "comprehensive", "significance"
    ]
}

UNCATEGORIZED_CACHE = []
USED_WORDS = set()

BACKUP_FAKES = [
    "ความรู้สึก", "การเดินทาง", "ครอบครัว", "ความคิดเห็น", "ความสำเร็จ", 
    "สภาพแวดล้อม", "การพัฒนา", "โอกาส", "ประสบการณ์", "เป้าหมาย", "ความรู้", "เทคโนโลยี"
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("🚀 เริ่มระบบดึงคำศัพท์เรียงตามความถี่ Top 5,000 Most Frequent Words...")
    asyncio.create_task(background_word_fetcher())

async def translate_in_context(session, word: str):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={word}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                translated = data[0][0][0].strip()
                if translated.lower() != word.lower() and len(translated) <= 25:
                    return translated
    except Exception:
        pass
    return None

async def build_quiz_item(session, word: str, level: str):
    thai_meaning = await translate_in_context(session, word.lower())
    if thai_meaning:
        fakes = [f for f in BACKUP_FAKES if f != thai_meaning]
        selected_fakes = random.sample(fakes, min(len(fakes), 3))
        choices = [thai_meaning] + selected_fakes
        random.shuffle(choices)
        return {
            "word": word.upper(), 
            "correct": thai_meaning, 
            "choices": choices,
            "level": level
        }
    return None

async def background_word_fetcher():
    async with aiohttp.ClientSession() as session:
        while True:
            if len(UNCATEGORIZED_CACHE) < 200:
                target_level = random.choice(["A0", "A1", "A2", "B1", "B2"])
                word_candidates = TOP_5000_VOCAB[target_level]
                
                # สุ่มเลือกคำศัพท์เรียงจากลำดับความถี่
                random.shuffle(word_candidates)
                for w in word_candidates:
                    w_upper = w.upper()
                    if w_upper.isalpha() and w_upper not in USED_WORDS and len(w_upper) >= 2:
                        quiz = await build_quiz_item(session, w_upper, target_level)
                        if quiz:
                            UNCATEGORIZED_CACHE.append(quiz)
                            USED_WORDS.add(w_upper)
                            print(f"✅ [TOP 5000 LOADED] {w_upper} ({target_level}) | คลังรวม: {len(UNCATEGORIZED_CACHE)} คำ")
                            await asyncio.sleep(0.1)
                            break

            await asyncio.sleep(0.2)

def match_word_for_level(level: str):
    if not UNCATEGORIZED_CACHE:
        return None

    for idx, item in enumerate(UNCATEGORIZED_CACHE):
        if item.get("level") == level:
            return UNCATEGORIZED_CACHE.pop(idx)
            
    return UNCATEGORIZED_CACHE.pop(0)

async def reset_to_main_menu(channel, old_message=None):
    if old_message:
        try:
            await old_message.delete()
        except Exception:
            pass
    try:
        embed = discord.Embed(
            title="🎯 เกมทายคำศัพท์ภาษาอังกฤษ (Top 5,000 Words)", 
            description="เลือกระดับความยากด้านล่างเพื่อเริ่มสุ่มคำถามได้เลยครับ:", 
            color=0xF1C40F
        )
        new_view = LevelSelectView()
        new_msg = await channel.send(embed=embed, view=new_view)
        new_view.message = new_msg
    except Exception:
        pass

class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer, choices):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer
        self.message = None

        for choice in choices:
            button = discord.ui.Button(label=choice[:80], style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(choice)
            self.add_item(button)

    async def on_timeout(self):
        if self.message:
            await reset_to_main_menu(self.message.channel, self.message)

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()

                if choice == self.correct_answer:
                    embed = discord.Embed(title="🎉 ถูกต้องครับ!", description=f"คำตอบคือ:\n**{choice}**", color=0x2ECC71)
                else:
                    embed = discord.Embed(title="❌ ยังไม่ถูกต้องครับ", description=f"คำตอบที่ถูกต้องคือ:\n**{self.correct_answer}**", color=0xE74C3C)

                for item in self.children:
                    item.disabled = True

                await interaction.edit_original_response(view=self)
                next_embed = discord.Embed(title="🎮 เล่นคำต่อไป", description="เลือกระดับความยากด้านล่างเพื่อเล่นต่อได้เลยครับ:", color=0xF1C40F)
                next_view = LevelSelectView()
                sent_msg = await interaction.followup.send(embeds=[embed, next_embed], view=next_view)
                next_view.message = sent_msg

            except Exception:
                await reset_to_main_menu(interaction.channel, self.message)

        return callback

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None

    async def on_timeout(self):
        if self.message:
            await reset_to_main_menu(self.message.channel, self.message)

    async def handle_level_click(self, interaction: discord.Interaction, level: str):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()

            quiz_data = match_word_for_level(level)

            if quiz_data:
                embed = discord.Embed(
                    title=f"🎯 ทายคำศัพท์ระดับ {level}",
                    description=f"คำศัพท์: **{quiz_data['word']}**\n\nคำแปลภาษาไทยคือข้อใด?:",
                    color=0x3498DB
                )
                quiz_view = QuizChoiceView(quiz_data["correct"], quiz_data["choices"])
                sent_msg = await interaction.followup.send(embed=embed, view=quiz_view)
                quiz_view.message = sent_msg
            else:
                embed = discord.Embed(
                    title="⏳ กำลังเตรียมคำศัพท์ใหม่...",
                    description=f"กำลังโหลดคำศัพท์ Top 5,000 จากอินเทอร์เน็ต\n\n**กรุณากดปุ่มอีกครั้งใน 1-2 วินาทีครับ**",
                    color=0xE67E22
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            await reset_to_main_menu(interaction.channel, self.message)

    @discord.ui.button(label="A0 (บ่อยสุด 1-300 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A0")

    @discord.ui.button(label="A1 (301-1,000 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A1")

    @discord.ui.button(label="A2 (1,001-2,000 คำแรก)", style=discord.ButtonStyle.primary)
    async def btn_a2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "A2")

    @discord.ui.button(label="B1 (2,001-3,500 คำแรก)", style=discord.ButtonStyle.success)
    async def btn_b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B1")

    @discord.ui.button(label="B2 (3,501-5,000 คำแรก)", style=discord.ButtonStyle.success)
    async def btn_b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_level_click(interaction, "B2")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.strip().lower()
    if msg_content in ["t!", "!t"]:
        try:
            await message.delete()
        except Exception:
            pass

        await reset_to_main_menu(message.channel)
        return

    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
    
