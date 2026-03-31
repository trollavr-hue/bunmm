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
# message_id: {
#   "title": str,
#   "host_id": int,
#   "winner_count": int,
#   "entries": set[int],
#   "channel_id": int,
#   "end_time": float,
#   "ended": bool
# }
giveaways = {}

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True
intents.guilds = True

# Disable voice to avoid audioop issues
discord.VoiceClient = None

bot = commands.Bot(command_prefix="s!", intents=intents)

# Nicer purple
EMBED_COLOR = discord.Color.from_rgb(155, 89, 182)


# ---------- UTILITIES ----------

def parse_duration(duration: str) -> int:
    """
    Parse duration like '10s', '5m', '2h', '3d', '1w' into seconds.
    """
    duration = duration.strip().lower()
    if not duration:
        raise ValueError("Empty duration")

    unit = duration[-1]
    try:
        amount = int(duration[:-1])
    except ValueError:
        raise ValueError("Invalid duration number")

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
        "w": 60 * 60 * 24 * 7,
    }

    if unit not in multipliers:
        raise ValueError("Invalid duration unit (use s/m/h/d/w)")

    return amount * multipliers[unit]


def format_timestamp(seconds_from_now: int) -> int:
    """
    Return a Unix timestamp for Discord <t:...> formatting.
    """
    return int(discord.utils.utcnow().timestamp()) + seconds_from_now


# ---------- REACTION TRACKER (10 REACTIONS) ----------

@bot.event
async def on_reaction_add(reaction, user):
    # Ignore bot reactions
    if user.bot:
        return

    message = reaction.message

    # Only track messages from allowed users
    if message.author.id not in ALLOWED_USERS:
        return

    # Count total reactions on the message
    total_reacts = sum(r.count for r in message.reactions)

    # Trigger at exactly 10 reactions
    if total_reacts == 10:
        channel = bot.get_channel(REACTION_NOTIFY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(REACTION_NOTIFY_CHANNEL_ID)
            except:
                print("[ERROR] Could not fetch reaction notify channel.")
                return

        try:
            await channel.send(
                "Hey king Ftdduck, your message has reached 10 reactions. <@1385468564231815239>"
            )
            print("[SUCCESS] Reaction notification sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send reaction notification: {e}")


# ---------- GIVEAWAY VIEW ----------

class GiveawayView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw = giveaways.get(self.message_id)
        if gw is None or gw.get("ended"):
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in gw["entries"]:
            await interaction.response.send_message("You are already entered.", ephemeral=True)
            return

        gw["entries"].add(user_id)

        # Update embed with new entries count
        try:
            channel = interaction.channel or await bot.fetch_channel(gw["channel_id"])
            message = await channel.fetch_message(self.message_id)
        except Exception as e:
            print(f"[ERROR] Failed to fetch giveaway message for update: {e}")
            await interaction.response.send_message("Entry registered, but failed to update message.", ephemeral=True)
            return

        if not message.embeds:
            await interaction.response.send_message("Entry registered.", ephemeral=True)
            return

        embed = message.embeds[0]
        new_embed = discord.Embed(
            title=embed.title,
            description=embed.description,
            color=EMBED_COLOR
        )

        # Rebuild fields, updating Entries only
        for field in embed.fields:
            if field.name.lower().startswith("entries"):
                new_embed.add_field(name="Entries", value=str(len(gw["entries"])), inline=False)
            else:
                new_embed.add_field(name=field.name, value=field.value, inline=field.inline)

        await message.edit(embed=new_embed, view=self)
        await interaction.response.send_message("You have joined the giveaway!", ephemeral=True)


# ---------- GIVEAWAY TASK ----------

async def run_giveaway(message_id: int, duration_seconds: int):
    await asyncio.sleep(duration_seconds)

    gw = giveaways.get(message_id)
    if gw is None or gw.get("ended"):
        return

    gw["ended"] = True

    channel = bot.get_channel(gw["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(gw["channel_id"])
        except:
            print("[ERROR] Could not fetch giveaway channel at end.")
            return

    try:
        message = await channel.fetch_message(message_id)
    except Exception as e:
        print(f"[ERROR] Could not fetch giveaway message at end: {e}")
        return

    entries = list(gw["entries"])
    winners = []
    if entries and gw["winner_count"] > 0:
        k = min(gw["winner_count"], len(entries))
        winners = random.sample(entries, k)

    # Build final embed
    if not message.embeds:
        return

    original_embed = message.embeds[0]
    new_embed = discord.Embed(
        title=original_embed.title,
        color=EMBED_COLOR
    )

    # Ended timestamp
    ended_ts = int(discord.utils.utcnow().timestamp())
    new_embed.add_field(name="Ended", value=f"<t:{ended_ts}:F>", inline=False)
    new_embed.add_field(name="Hosted by", value=f"<@{gw['host_id']}>", inline=False)
    new_embed.add_field(name="Entries", value=str(len(entries)), inline=False)

    if winners:
        winner_mentions = ", ".join(f"<@{w}>" for w in winners)
        new_embed.add_field(name="Winners", value=winner_mentions, inline=False)
    else:
        winner_mentions = "No valid entries."
        new_embed.add_field(name="Winners", value=winner_mentions, inline=False)

    # Remove join button
    await message.edit(embed=new_embed, view=None)
    print(f"[SUCCESS] Giveaway {message_id} ended. Winners: {winner_mentions}")

    # Congratulation message in the giveaway channel
    if winners:
        await channel.send(
            f"🎊 Congratulations {', '.join(f'<@{w}>' for w in winners)}, you won the **{gw['title']}**!"
        )


# ---------- SLASH COMMANDS ----------

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("[READY] Slash commands synced.")
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")
    print(f"[READY] Logged in as {bot.user}")


@bot.tree.command(name="gcreate", description="Create a giveaway.")
async def gcreate(
    interaction: discord.Interaction,
    title: str,
    timer: str,
    winnercount: int
):
    # Permission check
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return

    # Parse duration
    try:
        duration_seconds = parse_duration(timer)
    except ValueError as e:
        await interaction.response.send_message(
            f"Invalid timer: {e}. Use formats like 10s, 5m, 2h, 3d, 1w.",
            ephemeral=True
        )
        return

    if winnercount < 1:
        await interaction.response.send_message("Winner count must be at least 1.", ephemeral=True)
        return

    end_ts = format_timestamp(duration_seconds)

    embed = discord.Embed(
        title=title,
        color=EMBED_COLOR
    )
    embed.add_field(name="Ends", value=f"<t:{end_ts}:F>", inline=False)
    embed.add_field(name="Hosted by", value=f"<@{interaction.user.id}>", inline=False)
    embed.add_field(name="Entries", value="0", inline=False)
    # No "Winners" field yet – only added when giveaway ends

    await interaction.response.send_message("Giveaway created.", ephemeral=True)

    channel = interaction.channel
    if channel is None:
        try:
            channel = await bot.fetch_channel(interaction.channel_id)
        except:
            print("[ERROR] Could not fetch interaction channel for giveaway.")
            return

    message = await channel.send(embed=embed, view=GiveawayView(0))  # temp id

    # Store giveaway
    giveaways[message.id] = {
        "title": title,
        "host_id": interaction.user.id,
        "winner_count": winnercount,
        "entries": set(),
        "channel_id": channel.id,
        "end_time": discord.utils.utcnow().timestamp() + duration_seconds,
        "ended": False,
    }

    # Update view with real message id
    view = GiveawayView(message.id)
    await message.edit(view=view)

    # Start background task
    asyncio.create_task(run_giveaway(message.id, duration_seconds))


@bot.tree.command(name="reroll", description="Reroll winners for an existing giveaway.")
async def reroll(
    interaction: discord.Interaction,
    message_id: str
):
    # Permission check
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return

    try:
        msg_id_int = int(message_id)
    except ValueError:
        await interaction.response.send_message("Invalid message ID.", ephemeral=True)
        return

    gw = giveaways.get(msg_id_int)
    if gw is None:
        await interaction.response.send_message("Giveaway not found in memory.", ephemeral=True)
        return

    if not gw.get("ended"):
        await interaction.response.send_message("Giveaway has not ended yet.", ephemeral=True)
        return

    channel = bot.get_channel(gw["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(gw["channel_id"])
        except:
            await interaction.response.send_message("Could not fetch giveaway channel.", ephemeral=True)
            return

    try:
        message = await channel.fetch_message(msg_id_int)
    except Exception:
        await interaction.response.send_message("Could not fetch giveaway message.", ephemeral=True)
        return

    entries = list(gw["entries"])
    if not entries:
        await interaction.response.send_message("No entries to reroll.", ephemeral=True)
        return

    k = min(gw["winner_count"], len(entries))
    winners = random.sample(entries, k)
    winner_mentions = ", ".join(f"<@{w}>" for w in winners)

    if not message.embeds:
        await interaction.response.send_message("Original giveaway embed missing.", ephemeral=True)
        return

    original_embed = message.embeds[0]
    new_embed = discord.Embed(
        title=original_embed.title,
        color=EMBED_COLOR
    )

    # Preserve fields but replace Winners
    has_winners_field = False
    for field in original_embed.fields:
        if field.name.lower().startswith("winners"):
            new_embed.add_field(name="Winners", value=winner_mentions, inline=False)
            has_winners_field = True
        else:
            new_embed.add_field(name=field.name, value=field.value, inline=field.inline)

    if not has_winners_field:
        new_embed.add_field(name="Winners", value=winner_mentions, inline=False)

    await message.edit(embed=new_embed)
    await interaction.response.send_message(f"Rerolled winners: {winner_mentions}", ephemeral=True)

    # Congratulation message in the giveaway channel for reroll
    await channel.send(
        f"🎊 Congratulations {winner_mentions}, you won the **{gw['title']}**!"
    )


bot.run(TOKEN)
