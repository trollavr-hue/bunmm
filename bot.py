import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import json
import os
import re
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
# On ready
# ------------------------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

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

        try:
            await self.user.kick(reason="NSFW link detected")
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
# NSFW detection (STRICT)
# ------------------------
NSFW_KEYWORDS = [
    "porn", "xxx", "hentai", "rule34", "nsfw",
    "onlyfans", "xvideos", "xnxx", "redtube", "pornhub"
]

NSFW_DOMAINS = [
    "onlyfans.com",
    "pornhub.com",
    "xvideos.com",
    "xnxx.com",
    "redtube.com"
]

NSFW_TLDS = [".xxx"]

def is_nsfw_link(content: str):
    content_lower = content.lower()

    urls = re.findall(r'(https?://[^\s]+)', content_lower)

    for url in urls:
        # Check explicit domains
        if any(domain in url for domain in NSFW_DOMAINS):
            return True

        # Check keywords inside URL
        if any(keyword in url for keyword in NSFW_KEYWORDS):
            return True

        # Check adult TLDs
        if any(tld in url for tld in NSFW_TLDS):
            return True

    return False

# ------------------------
# Slash command: nickname
# ------------------------
@bot.tree.command(name="name", description="Change the bot's nickname in this server")
@app_commands.describe(new_name="New nickname")
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

    if is_nsfw_link(message.content):
        data["handled_messages"].append(message.id)
        save_data(data)

        # Delete message
        try:
            await message.delete()
        except:
            pass

        # Timeout user
        try:
            await message.author.timeout(timedelta(hours=1), reason="NSFW link")
        except:
            pass

        report_channel = discord.utils.get(message.guild.text_channels, name="link-report")

        if report_channel:
            embed = discord.Embed(
                title="🚨 NSFW Link Detected",
                description=message.content,
                color=discord.Color.red()
            )
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Channel", value=message.channel.mention)

            view = ReportView(message.author)

            await report_channel.send(embed=embed, view=view)

    await bot.process_commands(message)

# ------------------------
# Run
# ------------------------
bot.run(TOKEN)
