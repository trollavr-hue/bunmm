import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")
OWNER_ID = 1429110753683832985  # Only you can use the bot

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

# Disable voice entirely so discord.py never imports audioop
discord.VoiceClient = None

bot = commands.Bot(command_prefix="s!", intents=intents)

@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def send(ctx, channel_id: int, *, message: str):
    # Only allow DM usage
    if not isinstance(ctx.channel, discord.DMChannel):
        return

    # Only allow YOU
    if ctx.author.id != OWNER_ID:
        return

    # Fetch channel
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except:
            await ctx.reply("Invalid channel ID.")
            return

    # Send message
    try:
        await channel.send(message)
        await ctx.reply("Message sent successfully.")
        print(f"[SUCCESS] Sent to {channel_id}")
    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.reply("Failed to send message.")

bot.run(TOKEN)
