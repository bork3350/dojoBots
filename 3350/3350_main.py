import discord
from discord.ext import tasks
import asyncio
import os
import yfinance as yf
from dotenv import load_dotenv
import time
from pathlib import Path
import csv
import io
from datetime import datetime, timedelta
import pytz
import requests  # NEW
from bs4 import BeautifulSoup  # NEW
import re

# Load .env file
env_path = Path(__file__).parent / ".env.3350"
load_dotenv(dotenv_path=env_path)

TOKEN = os.environ['DISCORD_BOT_TOKEN']

intents = discord.Intents.default()
intents.message_content = True  # Needed for DM handling
intents.members = True          # Needed to access member join info

bot = discord.Bot(intents=intents)

last_status = None  # Track last status to avoid redundant updates
latest_usd_to_jpy = None  # Cache the latest exchange rate

# Tokyo timezone
TOKYO_TZ = pytz.timezone("Asia/Tokyo")

def get_tse_market_times():
    now = datetime.now(TOKYO_TZ)
    today = now.date()

    events = {
        "Market Open": datetime.combine(today, datetime.strptime("09:00", "%H:%M").time(), tzinfo=TOKYO_TZ),
        "Lunch Break": datetime.combine(today, datetime.strptime("11:30", "%H:%M").time(), tzinfo=TOKYO_TZ),
        "Market Reopen": datetime.combine(today, datetime.strptime("12:30", "%H:%M").time(), tzinfo=TOKYO_TZ),
        "Market Close": datetime.combine(today, datetime.strptime("15:00", "%H:%M").time(), tzinfo=TOKYO_TZ),
    }

    upcoming = []
    for label, event_time in events.items():
        if event_time > now:
            delta = (event_time - now).total_seconds() / 60  # in minutes
            upcoming.append((label, int(delta)))

    return upcoming

def get_3350_price_and_change():
    global latest_usd_to_jpy
    ticker = yf.Ticker("3350.T")
    data = ticker.history(period="2d")

    if len(data) >= 2:
        prev_close = data['Close'].iloc[-2]
        last = data['Close'].iloc[-1]
        change = ((last - prev_close) / prev_close) * 100

        # Get USD/JPY exchange rate
        fx = yf.Ticker("JPY=X")
        fx_data = fx.history(period="1d")
        if not fx_data.empty:
            latest_usd_to_jpy = fx_data['Close'].iloc[-1]
            usd_price = last / latest_usd_to_jpy
        else:
            usd_price = None

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Price fetched: ¥{last:.0f}, Change: {change:+.2f}%, USD: ${usd_price:.2f}" if usd_price else "USD price not available.")
        return last, change, usd_price

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Not enough data to calculate price change.")
    return 0.0, 0.0, None

def get_pts_price_3350():
    url = "https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETsiR001Control&_DataStoreID=DSWPLETsiR001Control&_PageID=WPLETsiR001Idtl10&_ActionID=getInfoOfCurrentMarket&stock_sec_code_mul=3350&exchange_code=PTS"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        print(f"[DEBUG] Fetching PTS price from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        tables = soup.find_all("table")
        print(f"[DEBUG] Found {len(tables)} tables.")

        for idx, table in enumerate(tables):
            text = table.get_text(separator='', strip=True)
            if "現在値" in text:
                print(f"[DEBUG] Raw text from matched table {idx}: {text[:500]}")  # Truncate to avoid overload

                # Regex to match 現在値 + optional whitespace + number (with optional commas or decimals)
                match = re.search(r"現在値\s*([0-9,]+(?:\.\d+)?)", text)
                if match:
                    price_str = match.group(1).replace(',', '')
                    print(f"[DEBUG] 🎯 Extracted PTS Price: {price_str}")
                    return price_str
                else:
                    print(f"[DEBUG] ❌ Could not extract price from table {idx}")

        print("[DEBUG] ❌ Could not find any matching table containing '現在値'")
        return None

    except Exception as e:
        print(f"[ERROR] Failed to fetch or parse PTS price: {e}")
        return None


@bot.event
async def on_ready():
    print(f"3350 Bot Logged in as {bot.user}")
    update_status.start()

@tasks.loop(seconds=15)
async def update_status():
    global last_status
    try:
        print(f"\nUpdate Cycle Starting v7...")

        price, change, usd_price = get_3350_price_and_change()
        price_str = f"¥{price / 10_000:.2f}万" if price >= 10_000 else f"¥{price:.0f}"
        usd_str = f"${usd_price:.2f}" if usd_price else ""
        change_str = f"{change:+.2f}%"
        new_status = f"{price_str}  {usd_str}  {change_str}"

        if new_status != last_status:
            await bot.change_presence(activity=discord.CustomActivity(name=new_status))
            last_status = new_status
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Status updated to: '{new_status}'")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Status unchanged, skipping update.")

    except Exception as e:
        print(f"Error during update cycle: {e}")

@bot.slash_command(name="cy", description="Convert yen to USD")
async def convert_yen(ctx: discord.ApplicationContext, yen: float):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] /cy command called with ¥{yen:,.0f}")
    if latest_usd_to_jpy:
        usd_amount = yen / latest_usd_to_jpy
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Conversion result: ¥{yen:,.0f} = ${usd_amount:,.2f}")
        await ctx.respond(f"¥{yen:,.0f} is approximately ${usd_amount:,.2f} USD.")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] No cached exchange rate available.")
        await ctx.respond("Exchange rate not yet available. Please try again shortly.")

@bot.slash_command(name="pts", description="Get the latest PTS price for 3350 (Metaplanet) from SBI")
async def pts(ctx: discord.ApplicationContext):
    await ctx.defer()

    # Get Yahoo price data
    tse_price, change, usd_price = get_3350_price_and_change()
    tse_price_str = f"¥{tse_price:.0f}"
    usd_str = f"${usd_price:.2f}" if usd_price else ""
    change_str = f"{change:+.2f}%"

    # Get PTS price
    pts_price = get_pts_price_3350()
    pts_price_str = f"¥{pts_price}" if pts_price else "N/A"

    message = f"TSE {tse_price_str} / PTS {pts_price_str} {usd_str} {change_str}"
    await ctx.respond(message)


bot.run(TOKEN)
