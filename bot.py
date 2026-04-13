import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import json
import os
from datetime import timedelta

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "handled.json"

# ------------------------
# Load / Save handled data
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
# On ready (sync commands)
# ------------------------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# ------------------------
# Create reports channel
# ------------------------
@bot.event
async def on_guild_join(guild):
    existing = discord.utils.get(guild.text_channels, name="nsfw-reports")
    if existing:
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }

    # Allow admins to see it
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

    await guild.create_text_channel("nsfw-reports", overwrites=overwrites)

# ------------------------
# Moderation buttons
# ------------------------
class ReportView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Accept (Kick)", style=discord.ButtonStyle.danger)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("No permission.", ephemeral=True)

        try:
            await self.user.kick(reason="Approved report")
            await interaction.response.send_message("User kicked.")
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Deny (Unmute)", style=discord.ButtonStyle.success)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("No permission.", ephemeral=True)

        try:
            await self.user.timeout(None)
            await interaction.response.send_message("Timeout removed.")
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# ------------------------
# Detect suspicious links
# ------------------------
def is_suspicious(content: str):
    suspicious_keywords = [
        "discord.gg/",
        "discord.com/invite",
        "onlyfans",
        "leak",
        "nudes",
        "nsfw"
    ]
    content = content.lower()
    return any(word in content for word in suspicious_keywords)

# ------------------------
# Slash command: change nickname
# ------------------------
@bot.tree.command(name="name", description="Change the bot's nickname in this server")
@app_commands.describe(new_name="New nickname for the bot")
async def change_name(interaction: discord.Interaction, new_name: str):
    if not interaction.user.guild_permissions.manage_nicknames:
        return await interaction.response.send_message(
            "You need Manage Nicknames permission.", ephemeral=True
        )

    try:
        await interaction.guild.me.edit(nick=new_name)
        await interaction.response.send_message(f"Bot nickname changed to **{new_name}**")
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# ------------------------
# Message handler
# ------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.id in data["handled_messages"]:
        return

    if is_suspicious(message.content):
        data["handled_messages"].append(message.id)
        save_data(data)

        # Delete message
        try:
            await message.delete()
        except:
            pass

        # Timeout user
        try:
            await message.author.timeout(timedelta(hours=1), reason="Suspicious link")
        except:
            pass

        # Find reports channel
        report_channel = discord.utils.get(message.guild.text_channels, name="nsfw-reports")

        if report_channel:
            embed = discord.Embed(
                title="🚨 Suspicious Message Detected",
                description=message.content,
                color=discord.Color.red()
            )
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Channel", value=message.channel.mention)

            view = ReportView(message.author)

            await report_channel.send(embed=embed, view=view)

    await bot.process_commands(message)

# ------------------------
# Run bot
# ------------------------
bot.run(TOKEN)
