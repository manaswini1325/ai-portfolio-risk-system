import os
import json
import re
from decimal import Decimal
from datetime import datetime
import boto3

dynamodb = boto3.resource("dynamodb", region_name="ap-south-2")

# Agent is in us-east-1 — connect there
bedrock_agent = boto3.client(
    "bedrock-agent-runtime",
    region_name=os.environ.get("AGENT_REGION", "us-east-1")
)

portfolios_table  = dynamodb.Table("Portfolios")
risk_alerts_table = dynamodb.Table("RiskAlerts")

AGENT_ID       = os.environ["AGENT_ID"]
AGENT_ALIAS_ID = os.environ["AGENT_ALIAS_ID"]


def call_agent(risk_event):
    style_map = {
        "CON": "Conservative",
        "BAL": "Balanced",
        "AGG": "Aggressive"
    }
    pid        = risk_event.get("portfolioId", "unknown")
    client     = risk_event.get("clientName",  "Unknown")
    style      = style_map.get(
        risk_event.get("style", "BAL"), "Balanced"
    )
    details    = risk_event.get("details", {})
    message    = details.get("message", "Risk threshold breached")
    alert_type = risk_event.get("alertType", "RISK_ALERT")
    total_val  = float(risk_event.get("totalValue", 0))
    daily_chg  = risk_event.get("dailyChange", 0)
    severity   = risk_event.get("severity", "HIGH")

    user_message = f"""Analyze this portfolio risk alert.

Portfolio ID  : {pid}
Client        : {client}
Mandate       : {style}
Alert Type    : {alert_type}
Alert Message : {message}
Severity      : {severity}
Total Value   : ${total_val:,.2f}
Daily Change  : {daily_chg}%

Instructions:
1. Call get_portfolio_details tool for {pid}
2. Call get_recent_alerts tool for {pid}
3. Analyze the actual holdings data
4. Respond with ONLY this JSON, no other text:

{{
  "riskScore": <integer 50 to 95>,
  "primaryAlertType": "<SINGLE_STOCK_CONCENTRATION or DAILY_LOSS_BREACH or ALLOCATION_DRIFT>",
  "explanation": "<2 sentences. Reference actual stock names and exact percentages from the holdings.>",
  "suggestedAction": "<1-2 sentences. Specific steps matching {style} mandate.>",
  "disclaimer": "This is not financial advice. This is an automated risk alert for informational purposes only. Consult a qualified financial advisor before making any investment decisions."
}}"""

    session_id = f"{pid}-{int(datetime.utcnow().timestamp())}"

    response = bedrock_agent.invoke_agent(
        agentId      = AGENT_ID,
        agentAliasId = AGENT_ALIAS_ID,
        sessionId    = session_id,
        inputText    = user_message
    )

    full_response = ""
    for chunk_event in response["completion"]:
        if "chunk" in chunk_event:
            chunk         = chunk_event["chunk"]["bytes"].decode("utf-8")
            full_response += chunk

    print(f"Agent response for {pid}: {full_response[:400]}")

    text  = re.sub(r"```json|```", "", full_response).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def lambda_handler(event, context):
    for record in event["Records"]:
        body       = json.loads(record["body"])
        risk_event = json.loads(body["Message"])

        pid         = risk_event.get("portfolioId", "unknown")
        client_name = risk_event.get("clientName",  "Unknown")

        print(f"Agent analyzing {pid} — {risk_event.get('alertType')}")

        try:
            insight  = call_agent(risk_event)
            alert_id = f"{pid}-{int(datetime.utcnow().timestamp())}"
            now      = datetime.utcnow().isoformat() + "Z"

            risk_alerts_table.put_item(Item={
                "alertId"         : alert_id,
                "portfolioId"     : pid,
                "clientName"      : client_name,
                "timestamp"       : now,
                "riskScore"       : Decimal(str(insight["riskScore"])),
                "primaryAlertType": insight["primaryAlertType"],
                "explanation"     : insight["explanation"],
                "suggestedAction" : insight["suggestedAction"],
                "disclaimer"      : insight["disclaimer"],
                "riskLevel"       : risk_event.get("severity", "HIGH"),
                "alertType"       : risk_event.get("alertType", ""),
                "ttl"             : int(
                    datetime.utcnow().timestamp()
                ) + 86400
            })

            portfolios_table.update_item(
                Key={"portfolioId": pid},
                UpdateExpression="""
                    SET latestAlertId   = :a,
                        latestAlertTime = :t,
                        aiRiskScore     = :s
                """,
                ExpressionAttributeValues={
                    ":a": alert_id,
                    ":t": now,
                    ":s": Decimal(str(insight["riskScore"]))
                }
            )

            print(f"✓ {pid} — Score: {insight['riskScore']}/100")
            print(f"  {insight['explanation'][:80]}...")

        except Exception as e:
            print(f"✗ Error for {pid}: {e}")
            import traceback
            traceback.print_exc()

    return {"statusCode": 200}