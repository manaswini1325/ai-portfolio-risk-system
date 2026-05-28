import json
import boto3

# AWS Clients
sqs = boto3.client(
    "sqs",
    region_name="ap-south-1"
)

sns = boto3.client(
    "sns",
    region_name="ap-south-1"
)

QUEUE_URL = "PASTE_RISK_QUEUE_URL"

TOPIC_ARN = "PASTE_TOPIC_ARN"

# Load portfolios
with open("../portfolio-service/portfolios.json") as f:

    portfolios = json.load(f)

print("Risk Service Listening...\n")

while True:

    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=10
    )

    messages = response.get(
        "Messages",
        []
    )

    for message in messages:

        body = json.loads(
            message["Body"]
        )

        event = json.loads(
            body["Message"]
        )

        print("Received Event:", event)

        ticker = event["ticker"]

        new_price = event["newPrice"]

        old_price = event["oldPrice"]

        for portfolio in portfolios:

            total_value = 0

            stock_values = {}

            # Calculate portfolio value
            for holding in portfolio["holdings"]:

                if holding["ticker"] == ticker:

                    holding["currentPrice"] = new_price

                stock_value = (
                    holding["shares"]
                    * holding["currentPrice"]
                )

                stock_values[
                    holding["ticker"]
                ] = stock_value

                total_value += stock_value

            # Allocation calculations
            for stock, value in stock_values.items():

                allocation = (
                    value / total_value
                ) * 100

                # CONDITION 1
                # Single stock exposure >20%
                if allocation > 20:

                    risk_event = {
                        "eventType":
                            "RiskThresholdBreached",

                        "portfolioId":
                            portfolio["portfolioId"],

                        "severity":
                            "HIGH",

                        "reason":
                            f"{stock} exposure "
                            f"exceeded 20%"
                    }

                    sns.publish(
                        TopicArn=TOPIC_ARN,
                        Message=json.dumps(
                            risk_event
                        )
                    )

                    print(
                        "Exposure Alert:",
                        risk_event
                    )

                # CONDITION 2
                # Allocation drift >5%

                model_allocation = (
                    100 / len(stock_values)
                )

                drift = abs(
                    allocation
                    - model_allocation
                )

                if drift > 5:

                    risk_event = {
                        "eventType":
                            "RiskThresholdBreached",

                        "portfolioId":
                            portfolio["portfolioId"],

                        "severity":
                            "MEDIUM",

                        "reason":
                            f"{stock} allocation "
                            f"drift exceeded 5%"
                    }

                    sns.publish(
                        TopicArn=TOPIC_ARN,
                        Message=json.dumps(
                            risk_event
                        )
                    )

                    print(
                        "Drift Alert:",
                        risk_event
                    )

            # CONDITION 3
            # Daily drop >3%

            drop_percent = (
                (
                    old_price
                    - new_price
                )
                / old_price
            ) * 100

            if drop_percent > 3:

                risk_event = {
                    "eventType":
                        "RiskThresholdBreached",

                    "portfolioId":
                        portfolio["portfolioId"],

                    "severity":
                        "HIGH",

                    "reason":
                        "Portfolio drop "
                        "exceeded 3%"
                }

                sns.publish(
                    TopicArn=TOPIC_ARN,
                    Message=json.dumps(
                        risk_event
                    )
                )

                print(
                    "Drop Alert:",
                    risk_event
                )

        # Delete message
        sqs.delete_message(
            QueueUrl=QUEUE_URL,
            ReceiptHandle=
                message["ReceiptHandle"]
        )