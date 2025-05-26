import discord
import asyncio
import os
import yfinance as yf
from dotenv import load_dotenv
import time
from pathlib import Path
import aiohttp
from datetime import datetime, timedelta
import pytz
import json

# Load environment variables
env_path = Path(__file__).parent / ".env.mtplf"
load_dotenv(dotenv_path=env_path)

TOKEN = os.environ['DISCORD_BOT_TOKEN']

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content for filtering
intents.members = True          # Needed to fetch member roles
client = discord.Client(intents=intents)

update_count = 0  # Count how many update cycles have occurred

# Setup path for banned_words.json in same folder as this script
script_folder = Path(__file__).parent
banned_words_path = script_folder / "banned_words.json"

# Load banned words from file or create empty dict
if banned_words_path.exists():
    with open(banned_words_path, "r", encoding="utf-8") as f:
        banned_words = json.load(f)
else:
    banned_words = {}
    with open(banned_words_path, "w", encoding="utf-8") as f:
        json.dump(banned_words, f, indent=2)

def save_banned_words():
    with open(banned_words_path, "w", encoding="utf-8") as f:
        json.dump(banned_words, f, indent=2)

def get_nyse_market_times():
    ny_tz = pytz.timezone("America/New_York")
    now = datetime.now(ny_tz)

    def is_weekday(dt):
        return dt.weekday() < 5  # Monday=0, Sunday=6

    while True:
        events = [
            ("Market Open", now.replace(hour=9, minute=30, second=0, microsecond=0)),
            ("Market Close", now.replace(hour=16, minute=0, second=0, microsecond=0))
        ]

        for label, dt in events:
            if dt > now:
                delta = dt - now
                total_minutes = int(delta.total_seconds() // 60)
                return [(label, total_minutes)]

        # If no events left today, move to next weekday
        now += timedelta(days=1)
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while not is_weekday(now):
            now += timedelta(days=1)

def get_mtplf_price_and_change():
    ticker = yf.Ticker("MTPLF")
    data = ticker.history(period="2d")

    if len(data) >= 2:
        prev_close = data['Close'].iloc[-2]
        last = data['Close'].iloc[-1]
        change = ((last - prev_close) / prev_close) * 100

        # Fetch USD/JPY exchange rate
        fx = yf.Ticker("JPY=X")
        fx_data = fx.history(period="1d")
        if not fx_data.empty:
            usd_to_jpy = fx_data['Close'].iloc[-1]
            jpy_price = last * usd_to_jpy
        else:
            jpy_price = None

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ðŸ“ˆ Price fetched: ${last:.2f}, Change: {change:+.2f}%, Â¥{jpy_price:.0f}" if jpy_price else "JPY price not available.")
        return last, change, jpy_price

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âš ï¸ Not enough data to calculate price change.")
    return 0.0, 0.0, None


# Check Discord API rate limits
async def check_rate_limit():
    url = 'https://discord.com/api/v10/users/@me'
    headers = {'Authorization': f'Bot {TOKEN}'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print("ðŸ•’ Discord API Rate Limit Headers:")
            print(f"  X-RateLimit-Limit:        {response.headers.get('X-RateLimit-Limit')}")
            
# When bot is ready
@client.event
async def on_ready():
    print(f"âœ”ï¸ Metaplanet Bot Logged in as {client.user}")
    last_status = None
    global update_count

    while True:
        try:
            update_count += 1
            print(f"\nðŸ”„ Update Cycle #{update_count} Starting...")

            # Fetch USD price, % change, and JPY equivalent
            price, change, jpy_price = get_mtplf_price_and_change()
            if price > 0:
                price_str = f"${price:.2f}"
                jpy_str = f"Â¥{jpy_price:.0f}" if jpy_price else ""
                change_str = f"{change:+.2f}%"
                combined_status = f"{price_str}  {jpy_str}  {change_str}"
            else:
                combined_status = "Price not found"

            # Only update if status changed
            if combined_status != last_status:
                await client.change_presence(
                    activity=discord.CustomActivity(name=combined_status)
                )
                last_status = combined_status
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ðŸ“° Status updated to: '{combined_status}'")

                # Optional: Check rate limit info
                await check_rate_limit()
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âš ï¸ Status unchanged, skipping update.")

            await asyncio.sleep(15)

        except Exception as e:
            print(f"âŒ Error during update cycle: {e}")
            await asyncio.sleep(15)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()
    content_lower = content.lower()

    # Command handling only for roles 'moderator' and 'admin'
    def is_mod_or_admin(member):
        roles = [role.name.lower() for role in member.roles]
        return 'moderator' in roles or 'admin' in roles

    if content_lower.startswith("!add-bad") or content_lower.startswith("!remove-bad") or content_lower.startswith("!list-bad"):
        if not is_mod_or_admin(message.author):
            await message.channel.send("âŒ You don't have permission to use this command.")
            return

        parts = content.split(maxsplit=2)
        if len(parts) < 2:
            await message.channel.send("âŒ Invalid command format.")
            return

        cmd = parts[0].lower()

        if cmd == "!list-bad":
            if len(parts) != 2:
                await message.channel.send("âŒ Usage: !list-bad <channel_name>")
                return
            channel_name = parts[1].lower()
            # Get channel by name in guild
            target_channel = discord.utils.get(message.guild.channels, name=channel_name)
            if not target_channel:
                await message.channel.send(f"âŒ Channel '{channel_name}' not found.")
                return

            banned_list = banned_words.get(channel_name, [])
            if banned_list:
                banned_formatted = ", ".join(banned_list)
                await message.channel.send(f"ðŸ›‘ Banned words/phrases in #{channel_name}: {banned_formatted}")
            else:
                await message.channel.send(f"â„¹ï¸ No banned words/phrases set for #{channel_name}.")

        elif cmd == "!add-bad":
            if len(parts) != 3:
                await message.channel.send("âŒ Usage: !add-bad <channel_name> <phrase>")
                return
            channel_name = parts[1].lower()
            phrase = parts[2].lower()

            target_channel = discord.utils.get(message.guild.channels, name=channel_name)
            if not target_channel:
                await message.channel.send(f"âŒ Channel '{channel_name}' not found.")
                return

            banned_list = banned_words.get(channel_name, [])
            if phrase in banned_list:
                await message.channel.send(f"âš ï¸ '{phrase}' is already banned in #{channel_name}.")
                return

            banned_list.append(phrase)
            banned_words[channel_name] = banned_list
            save_banned_words()
            await message.channel.send(f"âœ… Added banned phrase '{phrase}' to #{channel_name}.")

        elif cmd == "!remove-bad":
            if len(parts) != 3:
                await message.channel.send("âŒ Usage: !remove-bad <channel_name> <phrase>")
                return
            channel_name = parts[1].lower()
            phrase = parts[2].lower()

            target_channel = discord.utils.get(message.guild.channels, name=channel_name)
            if not target_channel:
                await message.channel.send(f"âŒ Channel '{channel_name}' not found.")
                return

            banned_list = banned_words.get(channel_name, [])
            if phrase not in banned_list:
                await message.channel.send(f"âš ï¸ '{phrase}' is not in the banned list for #{channel_name}.")
                return

            banned_list.remove(phrase)
            banned_words[channel_name] = banned_list
            save_banned_words()
            await message.channel.send(f"âœ… Removed banned phrase '{phrase}' from #{channel_name}.")

        return

    # Check for banned words/phrases on all other messages in the guild (non-DM)
    if message.guild:
        channel_name = message.channel.name.lower()
        banned_list = banned_words.get(channel_name, [])

        # Check if any banned phrase is in the message content (case insensitive)
        triggered_phrase = None
        for phrase in banned_list:
            if phrase in content_lower:
                triggered_phrase = phrase
                break

        if triggered_phrase:
            try:
                # Delete offending message
                await message.delete()

                # DM user explaining the deletion
                dm_msg = f"Your message was deleted because it contained a banned phrase: '{triggered_phrase}' in #{channel_name}. Try moving this topic to #off-topic or #btc-derivatives."
                await message.author.send(dm_msg)

                # Notify moderators channel
                mod_channel = discord.utils.get(message.guild.channels, name="bot-logs")
                if mod_channel:
                    notify_msg = (f"ðŸš¨ Message deleted in #{channel_name}.\n"
                                  f"User: {message.author.mention} ({message.author})\n"
                                  f"Phrase: '{triggered_phrase}'\n"
                                  f"Original message: {content}")
                    await mod_channel.send(notify_msg)

            except Exception as e:
                print(f"Error handling banned phrase: {e}")

# Run the bot
client.run(TOKEN)
