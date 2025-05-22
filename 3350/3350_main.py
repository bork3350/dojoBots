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


@bot.event
async def on_ready():
    print(f"3350 Bot Logged in as {bot.user}")
    update_status.start()


@tasks.loop(seconds=15)
async def update_status():
    global last_status
    try:
        print(f"\nUpdate Cycle Starting v6...")

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


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip().lower()

    # Handle DMs
    if isinstance(message.channel, discord.DMChannel):
        if content in {"wen", "when", "schedule", "next"}:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DM command received from {message.author}: '{message.content}'")
            
            upcoming = get_tse_market_times()
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
                reply = f"🕐 Next up: **{label}** in **{time_str}**."
                await message.channel.send(reply)
            else:
                await message.channel.send("📉 The Tokyo market is closed for the day.")
            return

        # Yen conversion via DM
        try:
            yen_amount = float(message.content.replace(",", "").strip("¥¥"))
            if latest_usd_to_jpy:
                usd_amount = yen_amount / latest_usd_to_jpy
                await message.channel.send(f"¥{yen_amount:,.0f} is approximately ${usd_amount:,.2f} USD.")
            else:
                await message.channel.send("Exchange rate not yet available. Please try again shortly.")
        except ValueError:
            await message.channel.send("Please send a valid number in yen (e.g., 13000) or type `wen`.")
        return

    # Handle mentions in public channels
    if bot.user in message.mentions and any(word in content for word in {"wen", "when", "schedule", "next"}):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Mention with trigger word received from {message.author}: '{message.content}'")
        
        upcoming = get_tse_market_times()
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
            reply = f"🕐 Next up: **{label}** in **{time_str}**."
            await message.channel.send(reply)
        else:
            await message.channel.send("📉 The Tokyo market is closed for the day.")


@bot.slash_command(name="exportmembers", description="Export the member list with join dates")
async def exportmembers(ctx: discord.ApplicationContext):
    if ctx.guild is None:
        await ctx.respond("This command must be used in a server.", ephemeral=True)
        return

    mod_role = discord.utils.get(ctx.guild.roles, name="Moderator")
    author = ctx.author

    if (mod_role not in author.roles) and (not author.guild_permissions.administrator):
        await ctx.respond("You need the Moderator role or Administrator permission to use this command.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    guild = ctx.guild
    await guild.chunk()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "User ID", "Joined At", "Join Method"])

    for member in guild.members:
        joined_at = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"

        if member.bot:
            join_method = "Bot"
        elif member.pending:
            join_method = "Pending"
        else:
            join_method = "Standard"

        writer.writerow([str(member), member.id, joined_at, join_method])

    output.seek(0)
    file = discord.File(fp=io.BytesIO(output.getvalue().encode()), filename="member_list.csv")

    await ctx.respond("✅ Here is the exported member list with join methods:", file=file, ephemeral=True)


#New slash command: /compare ticker1 ticker2 (only in #btc-derivatives)
@bot.slash_command(name="compare", description="Compare two stock tickers by their current USD value")
async def compare(ctx: discord.ApplicationContext, ticker1: str, ticker2: str):
    
    # Log command usage
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] /compare command used by {ctx.author} with args: {ticker1}, {ticker2}")

	# Restrict to a specific channel
    if ctx.channel.name != "btc-derivatives":
        await ctx.respond("This command can only be used in the #btc-derivatives channel.", ephemeral=True)
        return

    await ctx.defer()

    try:
        stock1 = yf.Ticker(ticker1)
        stock2 = yf.Ticker(ticker2)

        price1 = stock1.history(period="1d")['Close'].iloc[-1]
        price2 = stock2.history(period="1d")['Close'].iloc[-1]

        ratio = price1 / price2

        await ctx.respond(f"**{ticker1.upper()} / {ticker2.upper()} = {ratio:.2f}**\n"
                          f"{ticker1.upper()}: ${price1:.2f}\n"
                          f"{ticker2.upper()}: ${price2:.2f}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error comparing {ticker1} and {ticker2}: {e}")
        await ctx.respond("❌ Failed to fetch or compare ticker prices. Please check the symbols and try again.")

bot.run(TOKEN)
