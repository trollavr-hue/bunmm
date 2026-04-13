import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import json
import os
import re
from datetime import timedelta

from transformers import pipeline

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "handled.json"

# ------------------------
# AI MODEL (zero-shot NSFW classifier)
# ------------------------
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

CANDIDATE_LABELS = [
    "nsfw adult content",
    "pornographic link",
    "safe normal link"
]

# ------------------------
# Data storage
# ------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"handled_messages": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

# ------------------------
# Create report channel
# ------------------------
@bot.event
async def on_guild_join(guild):
    existing = discord.utils.get(guild.text_channels, name="link-report")
    if existing:
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }

    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

    await guild.create_text_channel("link-report", overwrites=overwrites)

# ------------------------
# Buttons
# ------------------------
class ReportView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Accept (Kick)", style=discord.ButtonStyle.danger)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("No permission.", ephemeral=True)

        await self.user.kick(reason="AI NSFW detection")
        await interaction.response.send_message("User kicked.")

    @discord.ui.button(label="Deny (Unmute)", style=discord.ButtonStyle.success)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("No permission.", ephemeral=True)

        await self.user.timeout(None)
        await interaction.response.send_message("Timeout removed.")

# ------------------------
# AI detection
# ------------------------
def is_nsfw_ai(content: str) -> bool:
    # extract urls if present
    urls = re.findall(r'(https?://[^\s]+)', content)
    text_to_check = content

    # if link exists, include it strongly in detection
    if urls:
        text_to_check = content + " " + " ".join(urls)

    result = classifier(text_to_check, CANDIDATE_LABELS)

    label = result["labels"][0]
    score = result["scores"][0]

    # Only trigger if model is confident
    if label != "safe normal link" and score > 0.75:
        return True

    return False

# ------------------------
# Slash command: rename bot
# ------------------------
@bot.tree.command(name="name", description="Change bot nickname")
@app_commands.describe(new_name="New name")
async def change_name(interaction: discord.Interaction, new_name: str):
    if not interaction.user.guild_permissions.manage_nicknames:
        return await interaction.response.send_message("No permission.", ephemeral=True)

    await interaction.guild.me.edit(nick=new_name)
    await interaction.response.send_message(f"Changed to {new_name}")

# ------------------------
# Message handler
# ------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.id in data["handled_messages"]:
        return

    if is_nsfw_ai(message.content):
        data["handled_messages"].append(message.id)
        save_data(data)

        try:
            await message.delete()
        except:
            pass

        try:
            await message.author.timeout(timedelta(hours=1), reason="AI NSFW detection")
        except:
            pass

        channel = discord.utils.get(message.guild.text_channels, name="link-report")

        if channel:
            embed = discord.Embed(
                title="🚨 AI NSFW Detection Triggered",
                description=message.content,
                color=discord.Color.red()
            )
            embed.add_field(name="User", value=message.author.mention)

            await channel.send(embed=embed, view=ReportView(message.author))

    await bot.process_commands(message)

# ------------------------
# Run bot
# ------------------------
bot.run(TOKEN)
