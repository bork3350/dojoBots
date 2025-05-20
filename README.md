# dojoBots
The metaplanet dojo discord uses a number of Price ticker bots with various features. Storing them here for posterity.

## How to run
In the event Bork is no longer able to host the bots, here's how someone else would go about doing it:
- Download and install Python
- Install the required packages: pip install discord.py yfinance python-dotenv aiohttp pytz
- Create the required .env files as outlined in the code
- Add the Discord_bot_token keys to the .env files (see Dojo mod post)
- Use the appropriate command to launch each bot: start python c:\users\username\path\to\bot\main_mp.py for example

Here is the current post regarding bots in the #useful-posts channel:
# **Dojo Price Bots Overview**

Click the People icon (top-right) to see the 4 active price bots:

## **BTC**
Shows Bitcoin price in USD, ¥, and % change.

## **3350 (TSE)**
Tracks semi-delayed 3350.T in ¥, USD, and % change.
Commands:
- /cy [amount] — Convert yen to USD
- /compare [ticker1] [ticker2] — Compare tickers

DM Options:
- Send "wen", "when", "schedule", or "market" — Get next TSE market event.
- Send a number — Convert yen to USD.

## **DN3 (Frankfurt)**
Tracks real-time DN3.F in €, USD, and % change.
DM:
- Send "wen", "when", "schedule", or "market" — Get next Frankfurt event.

## **MTPLF (NYSE)**
Tracks semi-delayed MTPLF in USD, ¥, and % change.
DM:
- Send "wen", "when", "schedule", or "market" — Get next NYSE event.

Misc:
- All bots currently maintained by @bork - hit me up with suggestions for new features.
- Bots are hosted on a personal machine, so if they're missing its likely the machine was rebooted. Patience grasshopper!
