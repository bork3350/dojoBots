import discord
import asyncio
import os
from dotenv import load_dotenv
import time
from pathlib import Path
import aiohttp
import datetime
import pytz
import re
import yfinance as yf

# Load environment variables
env_path = Path(__file__).parent / ".env.dn3"
load_dotenv(dotenv_path=env_path)

TOKEN = os.environ['DISCORD_BOT_TOKEN']

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

update_count = 0

# Frankfurt market timezone
FRANKFURT_TZ = pytz.timezone("Europe/Berlin")

async def get_dn3_price_and_change_tradegate():
    url = "https://www.tradegate.de/refresh.php?isin=JP3481200008"
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ðŸ”„ Fetching JSON from Tradegate...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()

        print(f"[DEBUG] Raw JSON: {data}")

        # Handle European decimal format for 'last' and 'delta'
        last_raw = data.get("last")
        delta_raw = data.get("delta")

        if isinstance(last_raw, str):
            last_raw = last_raw.replace(",", ".")
        if isinstance(delta_raw, str):
            delta_raw = delta_raw.replace(",", ".").replace("+", "").strip()

        price = float(last_raw)
        change = float(delta_raw)

        # Get EUR to USD exchange rate
        fx = yf.Ticker("EURUSD=X")
        fx_data = fx.history(period="1d")
        eur_to_usd = None
        if not fx_data.empty:
            eur_to_usd = fx_data['Close'].iloc[-1]
            print(f"[DEBUG] EUR/USD from Yahoo: {eur_to_usd}")
        else:
            print("[DEBUG] Yahoo EUR/USD failed â€” trying ExchangeRate.host...")
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.exchangerate.host/latest?base=EUR&symbols=USD") as resp:
                    fx_json = await resp.json()
                    eur_to_usd = fx_json.get("rates", {}).get("USD")
                    print(f"[DEBUG] EUR/USD from exchangerate.host: {eur_to_usd}")

        usd_price = price * eur_to_usd if eur_to_usd else None

        if price:
            if usd_price:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âœ… â‚¬{price:.2f}, {change:+.2f}%, ${usd_price:.2f}")
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âœ… â‚¬{price:.2f}, {change:+.2f}% (no USD)")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âŒ Price not found")

        return price, change, usd_price

    except Exception as e:
        print(f"âŒ Error fetching or parsing Tradegate data: {e}")
        return 0.0, 0.0, None


def get_frankfurt_market_times():
    now = datetime.datetime.now(FRANKFURT_TZ)
    today = now.date()

    open_time = FRANKFURT_TZ.localize(datetime.datetime.combine(today, datetime.time(9, 0)))
    close_time = FRANKFURT_TZ.localize(datetime.datetime.combine(today, datetime.time(17, 30)))

    events = []

    if now < open_time:
        delta = int((open_time - now).total_seconds() // 60)
        events.append(("Market Open", delta))
    if open_time <= now < close_time:
        delta = int((close_time - now).total_seconds() // 60)
        events.append(("Market Close", delta))

    return events


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        content = message.content.strip().lower()

        if content in {"wen", "when", "schedule", "next"}:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DM command from {message.author}: '{message.content}'")

            upcoming = get_frankfurt_market_times()
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
                reply = f"ðŸ• Next up: **{label}** in **{time_str}**."
                await message.channel.send(reply)
            else:
                await message.channel.send("ðŸ“‰ The Frankfurt market is closed for the day.")


async def check_rate_limit():
    url = 'https://discord.com/api/v10/users/@me'
    headers = {'Authorization': f'Bot {TOKEN}'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print("ðŸ“Š Discord API Rate Limit Headers:")
            print(f"  X-RateLimit-Limit: {response.headers.get('X-RateLimit-Limit')}")


@client.event
async def on_ready():
    print(f"âœ… Metaplanet DN3 Bot Logged in as {client.user}")
    last_status = None
    global update_count

    while True:
        try:
            update_count += 1
            print(f"\nðŸ”„ Update Cycle #{update_count} Starting...")

            price, change, usd_price = await get_dn3_price_and_change_tradegate()
            if price > 0:
                price_str = f"â‚¬{price:.2f}"
                usd_str = f"${usd_price:.2f}" if usd_price else ""
                change_str = f"{change:+.2f}%"
                combined_status = f"{price_str}  {usd_str}  {change_str}".strip()
            else:
                combined_status = "Price not found"

            if combined_status != last_status:
                await client.change_presence(
                    activity=discord.CustomActivity(name=combined_status)
                )
                last_status = combined_status
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ðŸŸ¢ Status updated to: '{combined_status}'")
                await check_rate_limit()
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] âš ï¸ Status unchanged, skipping update.")

            await asyncio.sleep(15)

        except Exception as e:
            print(f"âŒ Error during update cycle: {e}")
            await asyncio.sleep(15)


# Run the bot
client.run(TOKEN)
