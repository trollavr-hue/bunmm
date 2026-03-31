import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

# Users allowed to trigger the reaction alert
ALLOWED_USERS = {1385468564231815239, 1429110753683832985}

# Channel where the bot sends the notification
NOTIFY_CHANNEL_ID = 1421305736817934475

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True

# Disable voice to avoid audioop import
discord.VoiceClient = None

bot = commands.Bot(command_prefix="s!", intents=intents)

@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user}")

@bot.event
async def on_reaction_add(reaction, user):
    # Ignore bot reactions
    if user.bot:
        return

    message = reaction.message

    # Only track messages from allowed users
    if message.author.id not in ALLOWED_USERS:
        return

    # Count total reactions
    total_reacts = sum(r.count for r in message.reactions)

    # Trigger at exactly 1 reaction
    if total_reacts == 1:
        channel = bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(NOTIFY_CHANNEL_ID)
            except:
                print("[ERROR] Could not fetch notify channel.")
                return

        try:
            await channel.send(
                f"Hey king Fttduck, your message got 1 reaction. <@1385468564231815239>"
            )
            print("[SUCCESS] Notification sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send notification: {e}")

bot.run(TOKEN)
