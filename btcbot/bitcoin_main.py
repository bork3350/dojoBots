import discord
import asyncio
import aiohttp
import os
import yfinance as yf
from dotenv import load_dotenv
import time
from datetime import datetime
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / ".env.btc"
load_dotenv(dotenv_path=env_path)

TOKEN = os.environ['DISCORD_BOT_TOKEN']
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# === Price Functions ===

def get_btc_usd_price_and_change():
    print(f"[{datetime.now()}] ðŸ›  Fetching BTC-USD data from Yahoo Finance...")
    ticker = yf.Ticker("BTC-USD")
    data = ticker.history(period="3d", interval="1d")
    print(f"[{datetime.now()}] ðŸ“Š Data fetched, len(data): {len(data)}")

    if len(data) >= 2:
        latest = data['Close'].iloc[-1]
        previous = data['Close'].iloc[-2]
        change = ((latest - previous) / previous) * 100
        print(f"[{datetime.now()}] ðŸ’µ USD fetched: ${latest:.2f}, Previous: ${previous:.2f}, Change: {change:+.2f}%")
        return latest, change
    else:
        print(f"[{datetime.now()}] âš ï¸ Not enough data for price and change.")
        return 0.0, 0.0

async def get_btc_price_jpy():
    print(f"[{datetime.now()}] ðŸ›  Fetching BTC-JPY price from CoinGecko...")
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=jpy'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            jpy_price = float(data['bitcoin']['jpy'])
            print(f"[{datetime.now()}] ðŸ’´ JPY fetched: Â¥{jpy_price}")
            return jpy_price

# === Bot Behavior ===

@client.event
async def on_ready():
    print(f"[{datetime.now()}] âœ… Bitcoin Bot Logged in as {client.user}")
    last_status = None
    cycle_count = 0

    while True:
        try:
            cycle_count += 1
            print(f"\nâ³ Update Cycle #{cycle_count} Starting...")

            usd_price, change = get_btc_usd_price_and_change()
            jpy_price = await get_btc_price_jpy()

            # Format USD
            usd_str = f"${usd_price / 1000:.1f}k" if usd_price >= 1000 else f"${usd_price:.2f}"

            # Format JPY
            jpy_str = (
                f"Â¥{jpy_price / 100_000_000:.2f}å„„" if jpy_price >= 100_000_000 else
                f"Â¥{jpy_price / 10_000:.2f}ä¸‡" if jpy_price >= 10_000 else
                f"Â¥{jpy_price:.2f}"
            )

            # Format change
            change_str = f"{change:+.2f}%"

            # Combine into one status string
            combined_status = f"{usd_str}  {jpy_str}   {change_str}"

            # Update status only if changed
            if combined_status != last_status:
                await client.change_presence(
                    activity=discord.CustomActivity(name=combined_status)
                )
                last_status = combined_status
                print(f"[{datetime.now()}] ðŸŸ¢ Status updated to: '{combined_status}'")
            else:
                print(f"[{datetime.now()}] âš ï¸ Status unchanged, skipping update.")

            await asyncio.sleep(15)

        except Exception as e:
            print(f"[{datetime.now()}] âŒ Error: {e}")
            await asyncio.sleep(15)

client.run(TOKEN)
