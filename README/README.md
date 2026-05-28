# RiskPulse — AI-Driven Real-Time Portfolio Risk Alert System

> **An event-driven, cloud-native portfolio risk intelligence platform built on AWS — monitoring 100 client portfolios in real time, detecting risk threshold breaches using deterministic rules, and generating AI-powered explanations via Amazon Bedrock Agent with Nova Pro.**

---

## Table of Contents

- [Overview](#overview)
- [Live Demo](#live-demo)
- [Architecture](#architecture)
- [Microservices](#microservices)
- [AWS Services](#aws-services)
- [AI Integration](#ai-integration)
- [Risk Detection Rules](#risk-detection-rules)
- [Event Schemas](#event-schemas)
- [Dashboard Features](#dashboard-features)
- [Design Decisions](#design-decisions)
- [Architectural Trade-offs](#architectural-trade-offs)
- [Scaling Strategy](#scaling-strategy)
- [AI Prompt Approach](#ai-prompt-approach)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Running the Project](#running-the-project)
- [Stopping the System](#stopping-the-system)
- [Environment Variables](#environment-variables)
- [Technology Stack](#technology-stack)

---

## Overview

RiskPulse is a simplified portfolio risk intelligence platform for a digital wealth management firm serving retail investors. It delivers **real-time portfolio monitoring** and **AI-generated insights** through a fully cloud-native, event-driven architecture on AWS.

The system:
- Tracks **100 client portfolios** with **20 equities** in near real-time
- Simulates live stock price movements using **Geometric Brownian Motion (GBM)** seeded from real **yFinance** data
- Detects **3 risk conditions** using deterministic rule-based logic
- Publishes structured **risk alert events** through an **SNS → SQS pub-sub pipeline**
- Generates **AI-powered explanations** using an **Amazon Bedrock Agent** with **Nova Pro** that fetches real portfolio holdings before responding
- Displays everything on a live **React dashboard** with portfolio list, risk scores, AI commentary, and scrolling ticker bar

---

## Live Demo

```
Dashboard URL : http://localhost:3000
API Base URL  : https://YOUR-API-ID.execute-api.ap-south-2.amazonaws.com
AWS Region    : ap-south-2 (Hyderabad)
Bedrock Region: us-east-1 (cross-region inference)
```

### To run the full system:

```bash
# Terminal 1 — Dashboard
cd dashboard && npm start

# Terminal 2 — Price Simulator
cd market-data-service && python market_data_simulator.py

# Terminal 3 — Generate AI insights for all portfolios
python generate_all_insights.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  YOUR LAPTOP                                                         │
│  Microservice 1 — Market Data Service                                │
│  market_data_simulator.py                                            │
│  yFinance + GBM → publishes PriceUpdated every 5 seconds            │
└────────────────────────────┬────────────────────────────────────────┘
                             │ PriceUpdated event
                             ▼
                    SNS: portfolio-events-topic
                             │ fans out
                             ▼
                    SQS: risk-queue (decoupler)
                             │ triggers
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AWS ap-south-2                                                      │
│                                                                      │
│  Microservice 2 — Risk Service                                       │
│  risk-service-lambda                                                 │
│  ├── Reads 100 portfolios from DynamoDB                              │
│  ├── Recalculates value with live prices                             │
│  ├── Rule 1: daily drop > 3%   → DAILY_LOSS_BREACH                  │
│  ├── Rule 2: stock > 20%       → SINGLE_STOCK_CONCENTRATION         │
│  └── Rule 3: drift > 5%        → ALLOCATION_DRIFT                   │
│                   │ RiskThresholdBreached event                      │
│                   ▼                                                  │
│          SNS: risk-alerts-topic                                      │
│                   │ fans out                                         │
│                   ▼                                                  │
│          SQS: ai-queue (decoupler)                                   │
│                   │ triggers                                         │
│                   ▼                                                  │
│  Microservice 3 — AI Insight Service                                 │
│  ai-insight-service-lambda                                           │
│  └── Calls Bedrock Agent (cross-region → us-east-1)                 │
│                   │                                                  │
│                   ▼                                                  │
│  ┌─────────────────────────────┐                                     │
│  │  Amazon Bedrock (us-east-1) │                                     │
│  │  Agent: riskpulse-agent     │                                     │
│  │  Model: Amazon Nova Pro     │                                     │
│  │  Tool 1: get_portfolio_details                                    │
│  │  Tool 2: get_recent_alerts  │                                     │
│  └──────────────┬──────────────┘                                     │
│                 │ calls tools                                         │
│                 ▼                                                     │
│  riskpulse-agent-tools Lambda                                        │
│  └── Reads DynamoDB → returns real holdings to Agent                 │
│                                                                      │
│  Saves to DynamoDB: RiskAlerts table                                 │
│  {explanation, suggestedAction, riskScore, disclaimer}               │
│                                                                      │
│  Microservice 4 — Portfolio Service                                  │
│  portfolio-api Lambda                                                │
│  └── GET /portfolios  /portfolios/{id}  /alerts                      │
│                   │                                                  │
│                   ▼                                                  │
│          Amazon API Gateway (HTTP API)                               │
└───────────────────┬─────────────────────────────────────────────────┘
                    │
                    ▼
          React Dashboard (localhost:3000)
          100 portfolios · AI insights · Live ticker
```

---

## Microservices

### Microservice 1 — Market Data Service
**File:** `market-data-service/market_data_simulator.py`

Simulates realistic stock price movements using **Geometric Brownian Motion**:

```
S(t+dt) = S(t) × exp((μ - 0.5σ²)dt + σ√dt × Z)
```

Where μ = drift, σ = volatility, Z = random normal shock. Prices are seeded from real **yFinance** data and published as `PriceUpdated` events to SNS every 5 seconds.

---

### Microservice 2 — Risk Service
**Lambda:** `risk-service-lambda`

Subscribes to `risk-queue`, reads all 100 portfolios from DynamoDB, recalculates values with live prices, and evaluates 3 deterministic risk rules. Publishes `RiskThresholdBreached` events when rules are triggered. Includes a **10-minute cooldown per portfolio** to prevent alert flooding and control Bedrock costs.

---

### Microservice 3 — AI Insight Service
**Lambda:** `ai-insight-service`

Subscribes to `ai-queue` and invokes the Amazon Bedrock Agent via **cross-region inference** (ap-south-2 → us-east-1). The Agent uses tool calling to fetch real portfolio data before generating explanations — ensuring every response references actual stock names and percentages rather than generic text.

---

### Microservice 4 — Portfolio Service
**Lambda:** `portfolio-api`

Exposes REST APIs through API Gateway:
- `GET /portfolios` — returns all 100 portfolios (list view, no holdings)
- `GET /portfolios/{id}` — returns full portfolio with latest AI alert
- `GET /alerts` — returns 50 most recent alerts sorted by timestamp

---

## AWS Services

| Service | Role in System |
|---------|---------------|
| **Amazon SNS** | Pub-sub broadcaster — fans out events to multiple subscribers |
| **Amazon SQS** | Message queue — decouples each microservice, prevents data loss |
| **AWS Lambda** | Serverless compute — 4 functions as 4 microservices |
| **Amazon DynamoDB** | NoSQL database — stores portfolios and AI-generated alerts |
| **Amazon API Gateway** | HTTP API — CORS-enabled REST endpoints for React dashboard |
| **Amazon Bedrock Agent** | AI reasoning — Nova Pro with tool calling for grounded responses |
| **Amazon CloudWatch** | Logging and observability — all Lambda logs captured automatically |
| **IAM** | Security — least-privilege roles per Lambda function |

**Total: 6 required services + IAM bonus = exceeds minimum requirement of 4**

---

## AI Integration

RiskPulse implements **Option B — Rule + AI Hybrid**:

- **Deterministic logic** handles all risk detection (fast, reliable, auditable)
- **Amazon Bedrock Agent** handles all explanation and recommendation generation

### Why an Agent over a simple LLM call?

A simple LLM call would receive only the alert text and produce generic responses like:
> *"A stock exceeds the concentration limit. Consider rebalancing."*

The Bedrock Agent with tool calling **fetches real portfolio data** before responding:
1. Agent receives the alert
2. Agent calls `get_portfolio_details("port-001")` → gets actual holdings from DynamoDB
3. Agent calls `get_recent_alerts("port-001")` → checks alert history
4. Agent reasons about the **real data** and generates:
> *"NVDA represents 28.3% of Tushar's Conservative portfolio, significantly exceeding the 20% single-stock concentration limit and drifting 13.3% above the model target of 15%."*

### AI Output Structure

Every agent response returns a validated JSON object:

```json
{
  "riskScore": 84,
  "primaryAlertType": "SINGLE_STOCK_CONCENTRATION",
  "explanation": "NVDA represents 28.3% of Tushar's Conservative portfolio, significantly exceeding the 20% limit.",
  "suggestedAction": "Gradually reduce NVDA by selling 5-7 shares per session over the next 5-7 trading days.",
  "disclaimer": "This is not financial advice. This is an automated risk alert for informational purposes only. Consult a qualified financial advisor before making any investment decisions."
}
```

---

## Risk Detection Rules

| Rule | Condition | Alert Type | Severity |
|------|-----------|------------|----------|
| Daily Loss | Portfolio daily change < -3% | `DAILY_LOSS_BREACH` | HIGH |
| Concentration | Any single stock > 20% of portfolio | `SINGLE_STOCK_CONCENTRATION` | HIGH |
| Drift | Allocation deviates > 5% from model weight | `ALLOCATION_DRIFT` | MEDIUM |

### Edge Cases Handled

- **Cooldown period**: 10-minute cooldown per portfolio prevents alert flooding
- **Price fallback**: Uses `avgPrice` if live price unavailable
- **Empty holdings**: Skips portfolios with no holdings gracefully
- **Decimal precision**: Uses Python `Decimal` for accurate financial calculations
- **DynamoDB TTL**: Alerts auto-delete after 24 hours keeping table clean
- **Throttling guard**: Max 3 parallel Bedrock calls to avoid rate limits

---

## Event Schemas

All events have clearly defined JSON schemas in the `event-schemas/` folder:

### PriceUpdated
Published by Market Data Service → SNS portfolio-events-topic every 5 seconds.
```json
{
  "eventType": "PriceUpdated",
  "timestamp": "2026-05-18T13:00:05Z",
  "tick": 45,
  "prices": { "AAPL": 292.18, "NVDA": 247.31, "..." : "..." }
}
```

### RiskThresholdBreached
Published by Risk Service → SNS risk-alerts-topic when rule triggers.
```json
{
  "eventType": "RiskThresholdBreached",
  "portfolioId": "port-001",
  "clientName": "Tushar Nagpal",
  "alertType": "SINGLE_STOCK_CONCENTRATION",
  "severity": "HIGH",
  "totalValue": 198450.00,
  "dailyChange": -1.2,
  "details": { "ticker": "NVDA", "weight": 28.3, "threshold": 20 }
}
```

### PortfolioRevalued
Emitted internally by Risk Service after each tick recalculation.
```json
{
  "eventType": "PortfolioRevalued",
  "portfolioId": "port-001",
  "totalValue": 198450.00,
  "dayChangePer": -1.2,
  "riskLevel": "HIGH",
  "lastUpdated": "2026-05-18T13:00:10Z"
}
```

---

## Dashboard Features

| Feature | Description |
|---------|-------------|
| Portfolio list | All 100 clients in scrollable sidebar |
| Risk badges | Color-coded HIGH / MEDIUM / LOW per portfolio |
| Portfolio value | Live USD value updating every 15 seconds |
| Day change | Percentage change from market open |
| AI Risk Score | 50-95 scale bar generated by Bedrock Agent |
| AI Explanation | Plain-language risk commentary with real stock names |
| Suggested Action | Mandate-aware rebalancing recommendation |
| Disclaimer | Mandatory financial advisory disclaimer |
| Alert timestamp | Time of last AI-generated alert |
| Live ticker | 20 stocks scrolling at bottom of screen |
| Search | Filter clients by name |
| Filter | Show only HIGH / MED / LOW risk portfolios |
| AUM | Total Assets Under Management |

---

## Design Decisions

### 1. SNS over EventBridge
SNS was chosen over EventBridge for simplicity and lower cost at this scale. EventBridge adds value for complex routing rules and schema registry — both unnecessary for the current 3-event architecture. SNS delivers the same fan-out capability with less configuration overhead.

### 2. SQS Batch Size of 1
Each SQS trigger processes exactly one message at a time. This prevents multiple portfolios from hitting the Bedrock Agent simultaneously, which would cause `ThrottlingException` errors. Batch size 1 guarantees sequential, reliable AI processing at the cost of slightly lower throughput — an acceptable trade-off for a risk intelligence system where accuracy matters more than speed.

### 3. Bedrock Agent over Simple LLM
A plain `InvokeModel` call would require the Lambda to pre-fetch portfolio data and inject it into the prompt, creating tight coupling between the Lambda and DynamoDB schema. The Agent with tool calling keeps this separation clean — the Agent decides what data it needs and fetches it autonomously.

### 4. 10-Minute Cooldown per Portfolio
Without a cooldown, every price tick generates hundreds of alerts for all portfolios, flooding the AI queue and incurring significant Bedrock costs. The cooldown ensures each portfolio is alerted at most once per 10 minutes, reducing Bedrock invocations by ~99% in steady state.

### 5. DynamoDB over RDS
Portfolio holdings are semi-structured (variable number of stocks per portfolio) making DynamoDB a better fit than a relational database. The document model stores each portfolio as a single item with an embedded holdings array, enabling single-item reads in the API with no joins required.

### 6. TTL on RiskAlerts Table
Alerts older than 24 hours auto-delete via DynamoDB TTL. This keeps the table small, reduces scan costs, and ensures the dashboard always shows recent, actionable insights rather than stale historical data.

### 7. Cross-Region Bedrock Inference
Amazon Nova Pro is available in us-east-1 with higher throughput limits than ap-south-2. Cross-region inference adds approximately 200ms of latency but provides access to the best available model with the highest rate limits — a worthwhile trade-off for an asynchronous AI pipeline.

---

## Architectural Trade-offs

| Decision | Chosen Approach | Trade-off |
|----------|----------------|-----------|
| **Region** | Single region ap-south-2 | Simpler vs multi-region HA |
| **Database queries** | DynamoDB Scan | Simple vs GSI for large scale |
| **AI model** | Bedrock Agent + Nova Pro | Higher quality vs simple prompt |
| **Price simulation** | GBM on laptop | Realistic vs cloud-hosted |
| **Auth** | No user auth on API | Fast demo vs production security |
| **Bedrock region** | Cross-region us-east-1 | Better model vs +200ms latency |
| **Alert storage** | DynamoDB | Flexible vs dedicated time-series DB |
| **Frontend** | React on localhost | Fast setup vs hosted deployment |

---

## Scaling Strategy

### Current Scale (Demo)
- 100 portfolios, 20 stocks, 5-second ticks
- Single Lambda instances, DynamoDB on-demand
- ~3-5 AI calls per minute

### Scaling to 10,000 Portfolios

**Compute**
Lambda scales automatically with SQS queue depth. No changes needed — AWS handles concurrency up to 1,000 simultaneous executions.

**Database**
Replace DynamoDB Scan with a **Global Secondary Index (GSI)** on `riskLevel` and `portfolioId` for O(1) lookups instead of full table scans. DynamoDB on-demand billing scales linearly with requests.

**AI throughput**
Increase Bedrock quota limits via AWS Service Quotas. Implement SQS FIFO queues with message groups to ensure ordered processing per portfolio. Add exponential backoff retry logic for throttling.

**Event routing**
Migrate from SNS to **Amazon EventBridge** for content-based routing — different alert severities can route to different SQS queues with different processing priorities.

**Architecture additions at scale**
- **ElastiCache** for caching portfolio summaries (reduce DynamoDB reads by 80%)
- **Kinesis Data Streams** instead of SNS for ordered, replayable price events
- **CloudWatch Alarms** with auto-scaling triggers on SQS queue depth
- **CDK or Terraform** for Infrastructure as Code to manage multi-region deployment

---

## AI Prompt Approach

### Agent Instructions Design Philosophy

The agent prompt is designed around three principles:

**1. Tool-first reasoning**
The agent is explicitly instructed to call `get_portfolio_details` and `get_recent_alerts` before generating any response. This grounds every explanation in real data, preventing hallucination of stock names or percentages.

**2. Mandate-aware recommendations**
Different client mandates receive different action timelines:
- **Conservative (CON)**: Gradual action over 5-7 trading days — capital preservation priority
- **Balanced (BAL)**: Moderate action over 3-5 trading days — balance risk and return
- **Aggressive (AGG)**: Faster action over 2-3 trading days — higher risk tolerance

**3. Strict output contract**
The agent is instructed to return only a JSON object matching an exact schema. No markdown, no preamble, no extra text. This ensures the Lambda can reliably parse the response and the dashboard can always render the explanation panel.

### Prompt Safety Requirements
- **No financial guarantees**: Agent explicitly instructed never to guarantee market performance
- **Mandatory disclaimer**: Every response includes the financial advisory disclaimer
- **Risk score calibration**: Guidelines provided (90-95 = severe, 70-79 = moderate, 50-69 = mild)

### Alert-Type Specific Behavior
Each alert type has dedicated instructions:
- `SINGLE_STOCK_CONCENTRATION`: Name the stock, state exact percentage, suggest gradual selling
- `DAILY_LOSS_BREACH`: State exact loss, explain 3% threshold breach, suggest defensive positioning
- `ALLOCATION_DRIFT`: Name stock, state actual vs model weight, suggest rebalancing direction

---

## Project Structure

```
ai-portfolio-risk-system/
│
├── README.md                          ← This file
│
├── event-schemas/                     ← Event contract definitions
│   ├── price_updated.json
│   ├── risk_threshold_breached.json
│   └── portfolio_revalued.json
│
├── market-data-service/               ← Microservice 1
│   ├── market_data_simulator.py       ← GBM price simulator
│   ├── market_data.json               ← Stock configuration
│   └── requirements.txt
│
├── risk-service/                      ← Microservice 2 (Lambda)
│   └── lambda_function.py             ← 3-rule risk detection engine
│
├── ai-insight-service/                ← Microservice 3 (Lambda)
│   └── lambda_function.py             ← Bedrock Agent invocation
│
├── portfolio-service/                 ← Microservice 4 (Lambda)
│   └── lambda_function.py             ← REST API handler
│
├── dashboard/                         ← React frontend
│   ├── src/
│   │   ├── App.js                     ← Main dashboard component
│   │   └── App.css                    ← Dark theme styling
│   ├── .env                           ← API Gateway URL
│   └── package.json
│
├── scripts/
│   └── seed_dynamodb.py               ← Seeds 100 portfolios to DynamoDB
│
└── generate_all_insights.py           ← Bulk AI insight generator
```

---

## Getting Started

### Prerequisites

```bash
# Python 3.12+
python --version

# Node.js 18+
node --version

# AWS CLI configured
aws configure

# AWS credentials with access to:
# Lambda, DynamoDB, SNS, SQS, API Gateway, Bedrock
```

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/ai-portfolio-risk-system.git
cd ai-portfolio-risk-system

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Mac/Linux

# Install Python dependencies
pip install boto3 yfinance numpy

# Install dashboard dependencies
cd dashboard
npm install
cd ..
```

---

## Running the Project

### Step 1 — Seed DynamoDB (First time only)
```bash
python scripts/seed_dynamodb.py
```

### Step 2 — Enable Lambda Triggers (AWS Console)
```
Lambda → risk-service-lambda → Triggers → risk-queue → Enable
Lambda → ai-insight-service → Triggers → ai-queue → Enable
```

### Step 3 — Start Dashboard
```bash
cd dashboard
npm start
# Opens http://localhost:3000
```

### Step 4 — Start Price Simulator
```bash
cd market-data-service
python market_data_simulator.py
# Prints tick every 5 seconds
```

### Step 5 — Generate AI Insights (optional — bulk fill)
```bash
python generate_all_insights.py
# Processes all 100 portfolios in 6 minutes
```

---

## Stopping the System

```bash
# Stop simulator
Ctrl+C in simulator terminal

# Disable Lambda triggers (AWS Console)
Lambda → risk-service-lambda → Triggers → Disable
Lambda → ai-insight-service → Triggers → Disable

# Stop dashboard
Ctrl+C in dashboard terminal
```

---

## Environment Variables

### dashboard/.env
```
REACT_APP_API_URL=https://YOUR-API-ID.execute-api.ap-south-2.amazonaws.com
```

### Lambda Environment Variables

**risk-service-lambda**
```
RISK_SNS_ARN=arn:aws:sns:ap-south-2:YOUR-ACCOUNT-ID:risk-alerts-topic
```

**ai-insight-service**
```
AGENT_ID=your-agent-id
AGENT_ALIAS_ID=your-agent-alias-id
AGENT_REGION=us-east-1
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Price simulation | Python, yFinance, NumPy, GBM |
| Cloud platform | AWS (ap-south-2) |
| Serverless compute | AWS Lambda (Python 3.12) |
| Messaging | Amazon SNS + SQS |
| Database | Amazon DynamoDB |
| AI model | Amazon Bedrock Agent, Nova Pro |
| API layer | Amazon API Gateway (HTTP API) |
| Observability | Amazon CloudWatch |
| Security | AWS IAM (least privilege) |
| Frontend | React, Axios, CSS3 |
| Region | ap-south-2 (primary), us-east-1 (Bedrock) |

---

## Evaluation Criteria Mapping

| Criteria | Implementation |
|----------|---------------|
| **Architecture 30%** | 4 microservices, SNS/SQS pub-sub, loose coupling |
| **Problem Solving 25%** | 3 correct risk rules, cooldown, TTL, error handling |
| **AI Usage 20%** | Bedrock Agent + tool calling, structured JSON, disclaimer |
| **AWS Design 15%** | 6 AWS services, CloudWatch logs, IAM roles |
| **Demo 10%** | Live dashboard, end-to-end flow, AI explanation panel |

---

*Built for the AWS AI Mini Project* 
*Region: ap-south-2 (Hyderabad) | AI: Amazon Bedrock Nova Pro | Architecture: Event-driven microservices*