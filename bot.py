import os
import asyncio
import random
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

# Allowed users (you + Ftdduck)
ALLOWED_USERS = {1385468564231815239, 1429110753683832985}

# Reaction notification channel
REACTION_NOTIFY_CHANNEL_ID = 1421305736817934475

# Giveaway storage (in memory)
giveaways = {}

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True
intents.guilds = True

discord.VoiceClient = None  # Prevent audioop import

bot = commands.Bot(command_prefix="s!", intents=intents)

# Brighter purple
EMBED_COLOR = discord.Color.from_rgb(190, 120, 255)


# ---------- UTILITIES ----------

def parse_duration(duration: str) -> int:
    duration = duration.strip().lower()
    unit = duration[-1]
    amount = int(duration[:-1])

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }

    if unit not in multipliers:
        raise ValueError("Invalid duration unit")

    return amount * multipliers[unit]


def format_timestamp(seconds_from_now: int) -> int:
    return int(discord.utils.utcnow().timestamp()) + seconds_from_now


def build_giveaway_description(ends_ts, host_id, entries):
    return (
        f"Ends: **<t:{ends_ts}:F>**\n"
        f"Hosted by: **<@{host_id}>**\n"
        f"Entries: **{entries}**\n"
    )


def build_final_description(host_id, entries, winners):
    return (
        f"Ended: **<t:{int(discord.utils.utcnow().timestamp())}:F>**\n"
        f"Hosted by: **<@{host_id}>**\n"
        f"Entries: **{entries}**\n"
        f"Winners: **{winners}**\n"
    )


# ---------- REACTION TRACKER (10 REACTIONS) ----------

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    message = reaction.message

    if message.author.id not in ALLOWED_USERS:
        return

    total_reacts = sum(r.count for r in message.reactions)

    if total_reacts == 10:
        channel = bot.get_channel(REACTION_NOTIFY_CHANNEL_ID)
        if channel:
            await channel.send(
                "Hey king Ftdduck, your message has reached 10 reactions. <@1385468564231815239>"
            )


# ---------- GIVEAWAY VIEW ----------

class GiveawayView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw = giveaways.get(self.message_id)
        if not gw or gw["ended"]:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in gw["entries"]:
            await interaction.response.send_message("You already joined.", ephemeral=True)
            return

        gw["entries"].add(user_id)

        # Update embed
        channel = interaction.channel
        message = await channel.fetch_message(self.message_id)

        new_desc = build_giveaway_description(
            gw["end_ts"],
            gw["host_id"],
            len(gw["entries"])
        )

        new_embed = discord.Embed(
            title=gw["title"],
            description=new_desc,
            color=EMBED_COLOR
        )

        await message.edit(embed=new_embed, view=self)
        await interaction.response.send_message("You joined the giveaway!", ephemeral=True)


# ---------- GIVEAWAY END TASK ----------

async def run_giveaway(message_id: int, duration_seconds: int):
    await asyncio.sleep(duration_seconds)

    gw = giveaways.get(message_id)
    if not gw or gw["ended"]:
        return

    gw["ended"] = True

    channel = bot.get_channel(gw["channel_id"])
    message = await channel.fetch_message(message_id)

    entries = list(gw["entries"])
    if entries:
        winners = random.sample(entries, min(gw["winner_count"], len(entries)))
        winners_text = ", ".join(f"<@{w}>" for w in winners)
    else:
        winners = []
        winners_text = "No valid entries."

    # Build final embed
    final_desc = build_final_description(
        gw["host_id"],
        len(entries),
        winners_text
    )

    final_embed = discord.Embed(
        title=gw["title"],
        description=final_desc,
        color=EMBED_COLOR
    )

    await message.edit(embed=final_embed, view=None)

    # Congratulation message
    if winners:
        await channel.send(
            f"🎊 Congratulations {', '.join(f'<@{w}>' for w in winners)}, you won the **{gw['title']}**!"
        )


# ---------- SLASH COMMANDS ----------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("[READY] Slash commands synced.")


@bot.tree.command(name="gcreate", description="Create a giveaway.")
async def gcreate(interaction: discord.Interaction, title: str, timer: str, winnercount: int):
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("Not allowed.", ephemeral=True)
        return

    try:
        duration_seconds = parse_duration(timer)
    except:
        await interaction.response.send_message("Invalid timer format.", ephemeral=True)
        return

    end_ts = format_timestamp(duration_seconds)

    desc = build_giveaway_description(
        end_ts,
        interaction.user.id,
        entries=0
    )

    embed = discord.Embed(
        title=title,
        description=desc,
        color=EMBED_COLOR
    )

    await interaction.response.send_message("Giveaway created.", ephemeral=True)

    message = await interaction.channel.send(embed=embed, view=GiveawayView(0))

    giveaways[message.id] = {
        "title": title,
        "host_id": interaction.user.id,
        "winner_count": winnercount,
        "entries": set(),
        "channel_id": interaction.channel.id,
        "end_ts": end_ts,
        "ended": False,
    }

    await message.edit(view=GiveawayView(message.id))

    asyncio.create_task(run_giveaway(message.id, duration_seconds))


@bot.tree.command(name="reroll", description="Reroll winners for a giveaway.")
async def reroll(interaction: discord.Interaction, message_id: str):
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("Not allowed.", ephemeral=True)
        return

    try:
        msg_id = int(message_id)
    except:
        await interaction.response.send_message("Invalid message ID.", ephemeral=True)
        return

    gw = giveaways.get(msg_id)
    if not gw or not gw["ended"]:
        await interaction.response.send_message("Giveaway not found or not ended.", ephemeral=True)
        return

    channel = bot.get_channel(gw["channel_id"])
    message = await channel.fetch_message(msg_id)

    entries = list(gw["entries"])
    if not entries:
        await interaction.response.send_message("No entries to reroll.", ephemeral=True)
        return

    winners = random.sample(entries, min(gw["winner_count"], len(entries)))
    winners_text = ", ".join(f"<@{w}>" for w in winners)

    # Update embed
    final_desc = build_final_description(
        gw["host_id"],
        len(entries),
        winners_text
    )

    new_embed = discord.Embed(
        title=gw["title"],
        description=final_desc,
        color=EMBED_COLOR
    )

    await message.edit(embed=new_embed)
    await interaction.response.send_message("Rerolled!", ephemeral=True)

    await channel.send(
        f"🎊 Congratulations {winners_text}, you won the **{gw['title']}**!"
    )


bot.run(TOKEN)
