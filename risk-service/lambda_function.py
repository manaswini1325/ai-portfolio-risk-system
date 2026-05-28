import json
import uuid
import boto3
from datetime import datetime

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')


risk_table = dynamodb.Table('RiskAlerts')

# SNS setup
sns = boto3.client('sns')

# Replace with your SNS Topic ARN
TOPIC_ARN = "arn:aws:sns:ap-south-2:529601496163:risk-alerts-topic"


def create_alert(pid, client_name, ticker, severity, alert_type, details):

    # Alert object
    alert = {
        "alertId": str(uuid.uuid4()),
        "portfolioId": pid,
        "clientName": client_name,
        "ticker": ticker,
        "severity": severity,
        "alertType": alert_type,
        "details": json.dumps(details),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ttl": int(datetime.utcnow().timestamp()) + 86400
    }

    # Save alert to DynamoDB
    risk_table.put_item(Item=alert)

    # Publish alert to SNS
    sns.publish(
        TopicArn=TOPIC_ARN,

        Message=json.dumps({
            "eventType": "RiskThresholdBreached",
            "portfolioId": pid,
            "clientName": client_name,
            "alertType": alert_type,
            "severity": severity,
            "details": details,
            "timestamp": alert["timestamp"]
        }, default=float),

        Subject="RiskThresholdBreached"
    )

    # Print log
    print(f"⚠ ALERT - {pid} - {alert_type} - {ticker}")