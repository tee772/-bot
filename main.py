import random
import urllib.parse
import urllib.request
import json
import os
import discord
from discord.ext import commands

def get_random_word_data(level: str):
    level_settings = {
        "A1": {"sp": "?????", "max_len": 5},
        "A2": {"sp": "??????", "max_len": 6},
        "B1": {"sp": "???????", "max_len": 7},
        "B2": {"sp": "????????", "max_len": 8},
        "C1/C2": {"sp": "*********", "max_len": 12}
    }
    
    setting = level_settings.get(level, level_settings["A1"])
    
    try:
        url = f"https://api.datamuse.com/words?sp={setting['sp']}&max=100"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            words_data = json.loads(response.read().decode())
            
        valid_words = [item['word'] for item in words_data if item['word'].isalpha()]
        target_word = random.choice(valid_words).capitalize()

        correct_th = translate_to_thai(target_word)
        
        wrong_options = []
        while len(wrong_options) < 3:
            random_wrong = random.choice(valid_words).capitalize()
            if random_wrong != target_word:
                wrong_th = translate_to_thai(random_wrong)
                if wrong_th != correct_th and wrong_th not in wrong_options:
                    wrong_options.append(wrong_th)

        options = [correct_th] + wrong_options
        random.shuffle(options)

        return {
            "word": target_word,
            "correct": correct_th,
            "options": options
        }
    except Exception as e:
        print(f"API Error: {e}")
        return {
            "word": "Challenge",
            "correct": "การท้าทาย",
            "options": ["การท้าทาย", "ความสะดวก", "การพักผ่อน", "ข้อตกลง"]
        }

def translate_to_thai(text: str) -> str:
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={encoded_text}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result[0][0][0]
    except Exception:
        return "ความหมาย"

class QuizChoiceView(discord.ui.View):
    def __init__(self, correct_answer: str):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer
        self.answered = False

    async def check_answer(self, interaction: discord.Interaction, selected_option: str):
        if self.answered:
            await interaction.response.send_message("คุณตอบคำถามนี้ไปแล้ว!", ephemeral=True)
            return

        self.answered = True
        for child in self.children:
            child.disabled = True

        if selected_option == self.correct_answer:
            embed = discord.Embed(
                title="✨ ถูกต้องครับ!",
                description=f"คำตอบที่ถูกต้องคือ: **{self.correct_answer}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ ยังไม่ถูกต้อง",
                description=f"คำตอบที่ถูกต้องคือ: **{self.correct_answer}**",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Choice 1", style=discord.ButtonStyle.secondary)
    async def choice1_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, button.label)

    @discord.ui.button(label="Choice 2", style=discord.ButtonStyle.secondary)
    async def choice2_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, button.label)

    @discord.ui.button(label="Choice 3", style=discord.ButtonStyle.secondary)
    async def choice3_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, button.label)

    @discord.ui.button(label="Choice 4", style=discord.ButtonStyle.secondary)
    async def choice4_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_answer(interaction, button.label)

class LevelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def generate_quiz(self, interaction: discord.Interaction, level: str):
        await interaction.response.defer(ephemeral=True)

        quiz_data = get_random_word_data(level)
        
        quiz_view = QuizChoiceView(correct_answer=quiz_data["correct"])
        for i, option_text in enumerate(quiz_data["options"]):
            quiz_view.children[i].label = option_text

        embed = discord.Embed(
            title=f"📝 คำศัพท์สุ่มใหม่ [{level}]",
            description=f"คำว่า: **\"{quiz_data['word']}\"** แปลว่าอะไร?",
            color=discord.Color.blue()
        )
        embed.set_footer(text="ระบบสุ่มคำศัพท์สดใหม่จาก API")

        await interaction.followup.send(embed=embed, view=quiz_view, ephemeral=True)

    @discord.ui.button(label="A1", style=discord.ButtonStyle.primary)
    async def a1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_quiz(interaction, "A1")

    @discord.ui.button(label="A2", style=discord.ButtonStyle.primary)
    async def a2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_quiz(interaction, "A2")

    @discord.ui.button(label="B1", style=discord.ButtonStyle.success)
    async def b1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_quiz(interaction, "B1")

    @discord.ui.button(label="B2", style=discord.ButtonStyle.success)
    async def b2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_quiz(interaction, "B2")

    @discord.ui.button(label="C1/C2", style=discord.ButtonStyle.danger)
    async def c1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_quiz(interaction, "C1/C2")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="t", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.command(name="quiz")
async def start_quiz_menu(ctx):
    embed = discord.Embed(
        title="🎯 ทายคำศัพท์ภาษาอังกฤษ (Auto-Generated)",
        description="คลิกเลือกความยากด้านล่าง บอทจะสุ่มคำศัพท์ใหม่จาก API ให้ทันที:",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=LevelSelectView())

# ดึง Token ปลอดภัยผ่าน Environment Variable
bot.run(os.environ.get("DISCORD_TOKEN"))
      
