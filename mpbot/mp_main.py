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

# Load environment variables
env_path = Path(__file__).parent / ".env.mtplf"
load_dotenv(dotenv_path=env_path)

TOKEN = os.environ['DISCORD_BOT_TOKEN']

intents = discord.Intents.default()
client = discord.Client(intents=intents)

update_count = 0  # Count how many update cycles have occurred

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

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 📈 Price fetched: ${last:.2f}, Change: {change:+.2f}%, ¥{jpy_price:.0f}" if jpy_price else "JPY price not available.")
        return last, change, jpy_price

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Not enough data to calculate price change.")
    return 0.0, 0.0, None


# Check Discord API rate limits
async def check_rate_limit():
    url = 'https://discord.com/api/v10/users/@me'
    headers = {'Authorization': f'Bot {TOKEN}'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print("?? Discord API Rate Limit Headers:")
            print(f"  X-RateLimit-Limit:        {response.headers.get('X-RateLimit-Limit')}")
            
# When bot is ready
@client.event
async def on_ready():
    print(f"✅ Metaplanet Bot Logged in as {client.user}")
    last_status = None
    global update_count

    while True:
        try:
            update_count += 1
            print(f"\n🔄 Update Cycle #{update_count} Starting...")

            # Fetch USD price, % change, and JPY equivalent
            price, change, jpy_price = get_mtplf_price_and_change()
            if price > 0:
                price_str = f"${price:.2f}"
                jpy_str = f"¥{jpy_price:.0f}" if jpy_price else ""
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
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🟢 Status updated to: '{combined_status}'")

                # Optional: Check rate limit info
                await check_rate_limit()
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Status unchanged, skipping update.")

            await asyncio.sleep(15)

        except Exception as e:
            print(f"❌ Error during update cycle: {e}")
            await asyncio.sleep(15)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip().lower()

    # Respond to DMs
    if isinstance(message.channel, discord.DMChannel):
        if content in {"wen", "when", "schedule", "next"}:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DM command received from {message.author}: '{message.content}'")

            upcoming = get_nyse_market_times()
            if upcoming:
                label, minutes = upcoming[0]
                hours = minutes // 60
                mins = minutes % 60
                parts = []
                if hours > 0:
                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if mins > 0 or not parts:
                    parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
                time_str = " ".join(parts)
                reply = f"Next up: **{label}** in **{time_str}**."
                await message.channel.send(reply)
            else:
                await message.channel.send("The NYSE market is closed for the day.")
        return

    # Respond to mentions like "@bot wen"
    if client.user in message.mentions:
        if any(word in content for word in {"wen", "when", "schedule", "next"}):
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Mention detected from {message.author}: '{message.content}'")

            upcoming = get_nyse_market_times()
            if upcoming:
                label, minutes = upcoming[0]
                hours = minutes // 60
                mins = minutes % 60
                parts = []
                if hours > 0:
                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if mins > 0 or not parts:
                    parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
                time_str = " ".join(parts)
                reply = f"Next up: **{label}** in **{time_str}**."
                await message.channel.send(reply)
            else:
                await message.channel.send("The NYSE market is closed for the day.")


# Run the bot
client.run(TOKEN)
