# seed_dynamodb.py
import json
import boto3
import random
from decimal import Decimal

# ✅ FIXED REGION
dynamodb = boto3.resource("dynamodb", region_name="ap-south-2")
table    = dynamodb.Table("Portfolios")

# Your 20 stocks — NO prices here, simulator provides those
STOCKS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN",
    "META","TSLA","NFLX","JPM","BAC",
    "WFC","GS","KO","PEP","PG",
    "JNJ","DIS","INTC","AMD","ORCL"
]

NAMES = [
    "Tushar Nagpal",  "Akash Mallick",  "Sneha Kulkarni", "Kabir Grover",
    "Priya Sharma",   "Rahul Mehta",    "Anjali Singh",   "Vikram Nair",
    "Pooja Iyer",     "Arjun Kapoor",   "Neha Gupta",     "Rohan Verma",
    "Divya Reddy",    "Sanjay Patel",   "Meera Joshi",    "Karan Bose",
    "Sunita Rao",     "Amit Chandra",   "Ritu Desai",     "Manish Tiwari",
]

STYLES = ["CON", "BAL", "AGG"]

RISK_MAP    = {"CON": "LOW",          "BAL": "MEDIUM",   "AGG": "HIGH"}
PROFILE_MAP = {"CON": "CONSERVATIVE", "BAL": "MODERATE", "AGG": "AGGRESSIVE"}

# ── BUILD PORTFOLIOS ──────────────────────────────────────────────────────────
portfolios = []

for i in range(1, 101):
    style = STYLES[(i - 1) % 3]

    # Pick 5 random stocks for this portfolio
    chosen = random.sample(STOCKS, 5)

    # Assign modelWeights that sum to 100
    # These are the TARGET allocations — drift is measured against these
    weights    = sorted([random.randint(10, 30) for _ in range(4)])
    w1,w2,w3,w4 = weights
    w5          = 100 - w1 - w2 - w3 - w4
    model_weights = [w1, w2, w3, w4, abs(w5)]

    # Build holdings — NO currentPrice, simulator will provide that
    holdings = []
    for j, ticker in enumerate(chosen):
        holdings.append({
            "ticker"     : ticker,
            "quantity"   : random.randint(5, 50),   # number of shares owned
            "avgPrice"   : Decimal(str(round(random.uniform(50, 500), 2))),
            "modelWeight": model_weights[j]          # ← target % allocation
        })

    # Introduce concentration in ~15% of portfolios → triggers Rule 2
    if i % 7 == 0:
        holdings[0]["quantity"] = 200   # large qty → will be > 20% of portfolio

    # Base portfolio value estimate (simulator will recalculate with real prices)
    # We set dailyOpenValue to a fixed number — simulator updates totalValue live
    # When totalValue drops 3% below dailyOpenValue → Rule 1 triggers
    base_value = Decimal(str(random.randint(50000, 500000)))

    # ~20% of portfolios start with openValue higher → easier to trigger Rule 1
    if i % 5 == 0:
        open_value = base_value * Decimal("1.05")  # opened 5% higher today
    else:
        open_value = base_value

    portfolio = {
        "portfolioId"       : f"port-{str(i).zfill(3)}",
        "clientId"          : f"client-{str(i).zfill(3)}",
        "clientName"        : NAMES[(i - 1) % len(NAMES)],
        "investmentStyle"   : style,
        "riskProfile"       : PROFILE_MAP[style],
        "riskClassification": RISK_MAP[style],
        "riskLevel"         : RISK_MAP[style],

        # ✅ holdings stored as JSON string (no prices — simulator provides them)
        "holdings"          : json.dumps(
                                  [{**h, "avgPrice": float(h["avgPrice"])}
                                   for h in holdings]
                              ),

        # ✅ dailyOpenValue — Rule 1 compares totalValue against this
        "dailyOpenValue"    : open_value,

        # These get updated live by the risk-service Lambda
        "totalValue"        : base_value,
        "dayChangePer"      : Decimal("0"),
        "aiRiskScore"       : Decimal("0"),
        "lastUpdated"       : "2026-05-16T00:00:00Z",
    }

    portfolios.append(portfolio)

# ── INSERT INTO DYNAMODB ──────────────────────────────────────────────────────
print(f"Inserting {len(portfolios)} portfolios into DynamoDB...\n")

for portfolio in portfolios:
    try:
        table.put_item(Item=portfolio)
        print(f"Inserted: {portfolio['portfolioId']}")
    except Exception as e:
        print(f"Error inserting {portfolio['portfolioId']}: {e}")

print("\n✅ All portfolios inserted successfully.")
print("\nWhat's stored (static — never changes):")
print("  portfolioId, clientName, investmentStyle")
print("  holdings → ticker, quantity, avgPrice, modelWeight")
print("  dailyOpenValue → used by Risk Service for Rule 1")
print("\nWhat the simulator updates (live — changes every 5s):")
print("  totalValue, dayChangePer, riskLevel, lastUpdated")