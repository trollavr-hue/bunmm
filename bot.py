import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")  # Railway loads this from environment variables
OWNER_ID = 1429110753683832985  # Only you can use the bot

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="s!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
async def send(ctx, channel_id: int, *, message: str):
    # Only allow DM usage
    if not isinstance(ctx.channel, discord.DMChannel):
        return

    # Only allow YOU to use it
    if ctx.author.id != OWNER_ID:
        return

    # Try to fetch the channel
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except:
            await ctx.reply("Invalid channel ID.")
            return

    # Try to send the message
    try:
        await channel.send(message)
        await ctx.reply("Message sent successfully.")
    except Exception as e:
        print(e)
        await ctx.reply("Failed to send message.")

bot.run(TOKEN)
