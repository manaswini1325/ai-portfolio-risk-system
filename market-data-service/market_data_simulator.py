# market_data_simulator.py
import json
import numpy as np
import time
from datetime import datetime
import boto3
import yfinance as yf

# ── CONFIG ────────────────────────────────────────────────────────────────────
sns = boto3.client("sns", region_name="ap-south-2")   # ← fixed region
TOPIC_ARN = "arn:aws:sns:ap-south-2:529601496163:portfolio-events-topic"

STOCKS = [
    "AAPL","MSFT","NVDA","TSLA","AMZN",
    "META","GOOGL","NFLX","AMD","INTC",
    "ORCL","IBM","SAP","CRM","ADBE",
    "PYPL","UBER","SHOP","SONY","BABA"
]

# GBM parameters
DT = 1 / (252 * 390)   # 1-min bar as fraction of trading year
MU = 0.0               # no drift bias

# ── STEP 1: FETCH ALL PRICES AT ONCE (fast) ───────────────────────────────────
print("\nFetching real stock prices (batch)...\n")

prices = {}
try:
    # Download all 20 stocks in ONE call — much faster than looping
    data = yf.download(
        " ".join(STOCKS),
        period="1d",
        interval="1m",
        progress=False,
        auto_adjust=True
    )["Close"]

    for ticker in STOCKS:
        try:
            price = float(data[ticker].dropna().iloc[-1])
            prices[ticker] = round(price, 2)
            print(f"  {ticker:<6}  ${price:.2f}")
        except Exception:
            prices[ticker] = 100.00
            print(f"  {ticker:<6}  $100.00  (fallback)")

except Exception as e:
    print(f"yFinance error: {e}\nUsing fallback prices.")
    prices = {s: 100.0 for s in STOCKS}

# ── STEP 2: FETCH VOLATILITY (30-day historical) ──────────────────────────────
print("\nFetching historical volatility...\n")

volatilities = {}
try:
    hist = yf.download(
        " ".join(STOCKS),
        period="30d",
        interval="1d",
        progress=False,
        auto_adjust=True
    )["Close"]

    for ticker in STOCKS:
        try:
            returns = hist[ticker].pct_change().dropna()
            vol = float(returns.std())
            volatilities[ticker] = vol
            print(f"  {ticker:<6}  {vol*100:.2f}% daily vol")
        except Exception:
            volatilities[ticker] = 0.02
            print(f"  {ticker:<6}  2.00% daily vol (fallback)")

except Exception as e:
    print(f"Volatility fetch error: {e}\nUsing 2% default.")
    volatilities = {s: 0.02 for s in STOCKS}

# ── STEP 3: CONTINUOUS GBM SIMULATION ────────────────────────────────────────
print(f"\nStarting simulation → publishing ALL prices in ONE SNS message every 5s\n")
print("-" * 60)

tick = 0
while True:
    tick += 1

    # Apply GBM to every stock
    for ticker in STOCKS:
        S     = prices[ticker]
        sigma = volatilities[ticker]
        Z     = np.random.standard_normal()
        drift = (MU - 0.5 * sigma**2) * DT
        shock = sigma * np.sqrt(DT) * Z
        prices[ticker] = round(float(S * np.exp(drift + shock)), 2)

    # ── ONE single SNS message with ALL 20 prices ─────────────────────────
    event = {
        "eventType" : "PriceUpdated",
        "timestamp" : datetime.utcnow().isoformat() + "Z",
        "tick"      : tick,
        "prices"    : prices,          # ← all 20 stocks in one payload
        "source"    : "market-data-gbm"
    }

    try:
        response = sns.publish(
            TopicArn = TOPIC_ARN,
            Message  = json.dumps(event),
            Subject  = "PriceUpdated"
        )
        msg_id = response["MessageId"]

        # Print snapshot of first 5 stocks
        now     = datetime.now().strftime("%H:%M:%S")
        preview = "   ".join(
            f"{s}=${prices[s]}" for s in STOCKS[:5]
        )
        print(f"[{now}]  Tick {tick:04d}  |  {preview} ...")
        print(f"          MsgID: {msg_id}")
        print()

    except Exception as e:
        print(f"✗ SNS publish failed: {e}")
        print("  Check your TOPIC_ARN and region (ap-south-2)")

    time.sleep(5)