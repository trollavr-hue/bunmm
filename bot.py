import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

OWNER_ID = 1429110753683832985  # Only track YOUR messages
NOTIFY_CHANNEL_ID = 1421305736121552985  # Where notifications are sent

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True

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

    # Only track YOUR messages
    if message.author.id != OWNER_ID:
        return

    # Count reactions
    total_reacts = sum(r.count for r in message.reactions)

    # Trigger at 1 reaction
    if total_reacts == 1:
        channel = bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(NOTIFY_CHANNEL_ID)
            except:
                print("[ERROR] Could not fetch notify channel.")
                return

        try:
            await channel.send(f"Hey <@{OWNER_ID}>, your message got 1 reaction.")
            print("[SUCCESS] Notification sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send notification: {e}")

bot.run(TOKEN)
