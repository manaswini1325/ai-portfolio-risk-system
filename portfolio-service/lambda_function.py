import json
import boto3
import re
from decimal import Decimal

dynamodb = boto3.resource("dynamodb", region_name="ap-south-2")

portfolios_table  = dynamodb.Table("Portfolios")
risk_alerts_table = dynamodb.Table("RiskAlerts")

HEADERS = {
    "Content-Type"                 : "application/json",
    "Access-Control-Allow-Origin"  : "*",
    "Access-Control-Allow-Methods" : "GET,OPTIONS",
    "Access-Control-Allow-Headers" : "Content-Type"
}


def to_json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def lambda_handler(event, context):
    path   = event.get("rawPath") or event.get("path", "")
    method = (event.get("requestContext", {})
                   .get("http", {})
                   .get("method", "GET"))

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": HEADERS, "body": ""}

    # ── GET /portfolios ───────────────────────────────────────────
    if path == "/portfolios" and method == "GET":
        response   = portfolios_table.scan()
        portfolios = response["Items"]
        for p in portfolios:
            p.pop("holdings", None)
        return {
            "statusCode": 200,
            "headers"   : HEADERS,
            "body"      : json.dumps(
                {"portfolios": portfolios},
                default=to_json
            )
        }

    # ── GET /portfolios/{id} ──────────────────────────────────────
    match = re.match(r"^/portfolios/([^/]+)$", path)
    if match and method == "GET":
        pid      = match.group(1)
        response = portfolios_table.get_item(
            Key={"portfolioId": pid}
        )
        item = response.get("Item")
        if not item:
            return {
                "statusCode": 404,
                "headers"   : HEADERS,
                "body"      : json.dumps({"error": "Not found"})
            }
        if "holdings" in item and isinstance(item["holdings"], str):
            item["holdings"] = json.loads(item["holdings"])

        # Get latest alert for this portfolio
        alerts_resp = risk_alerts_table.scan(
            FilterExpression="portfolioId = :pid",
            ExpressionAttributeValues={":pid": pid}
        )
        alerts = alerts_resp.get("Items", [])
        if alerts:
            alerts.sort(
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            item["latestAlert"] = alerts[0]

        return {
            "statusCode": 200,
            "headers"   : HEADERS,
            "body"      : json.dumps(item, default=to_json)
        }

    # ── GET /alerts ───────────────────────────────────────────────
    if path == "/alerts" and method == "GET":
        response = risk_alerts_table.scan(Limit=50)
        alerts   = response.get("Items", [])
        alerts.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        return {
            "statusCode": 200,
            "headers"   : HEADERS,
            "body"      : json.dumps(
                {"alerts": alerts},
                default=to_json
            )
        }

    return {
        "statusCode": 404,
        "headers"   : HEADERS,
        "body"      : json.dumps({"error": "Route not found"})
    }