# generate_all_insights.py
# Generates AI insights for all 100 portfolios
# Uses parallel threads — 3 at a time to avoid throttling

import boto3
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

lambda_client    = boto3.client("lambda", region_name="ap-south-2")
dynamodb         = boto3.resource("dynamodb", region_name="ap-south-2")
portfolios_table = dynamodb.Table("Portfolios")


def generate_insight(portfolio):
    pid         = portfolio["portfolioId"]
    client_name = portfolio.get("clientName", "Unknown")
    style       = portfolio.get("investmentStyle", "BAL")
    total_value = float(portfolio.get("totalValue", 10000))
    day_change  = float(portfolio.get("dayChangePer", 0))
    risk_level  = portfolio.get("riskLevel", "HIGH")

    if day_change < -3:
        alert_type = "DAILY_LOSS_BREACH"
        message    = f"Portfolio dropped {abs(round(day_change,2))}% today breaching 3% daily loss limit"
    elif risk_level == "HIGH":
        alert_type = "SINGLE_STOCK_CONCENTRATION"
        message    = f"Single stock concentration exceeding 20% limit detected in {pid}"
    else:
        alert_type = "ALLOCATION_DRIFT"
        message    = f"Allocation drift greater than 5% from model target detected in {pid}"

    event = {
        "Records": [{
            "body": json.dumps({
                "Message": json.dumps({
                    "portfolioId": pid,
                    "clientName" : client_name,
                    "style"      : style,
                    "alertType"  : alert_type,
                    "severity"   : risk_level,
                    "totalValue" : total_value,
                    "dailyChange": day_change,
                    "details"    : {"message": message}
                })
            })
        }]
    }

    try:
        response = lambda_client.invoke(
            FunctionName   = "ai-insight-service-lambda",
            InvocationType = "RequestResponse",
            Payload        = json.dumps(event)
        )
        response["Payload"].read()
        return pid, client_name, True, None
    except Exception as e:
        return pid, client_name, False, str(e)


def main():
    print("Fetching all 100 portfolios...")
    response   = portfolios_table.scan()
    portfolios = response["Items"]
    print(f"Found {len(portfolios)} portfolios\n")
    print("-" * 60)

    success = 0
    failed  = 0
    total   = len(portfolios)

    # Process 3 at a time with 10 second gap between batches
    batch_size = 3
    batches    = [
        portfolios[i:i+batch_size]
        for i in range(0, len(portfolios), batch_size)
    ]

    print(f"Processing {total} portfolios in {len(batches)} batches of {batch_size}")
    print(f"Estimated time: ~{len(batches) * 12} seconds ({len(batches) * 12 // 60} minutes)\n")

    for batch_num, batch in enumerate(batches):
        print(f"Batch {batch_num+1}/{len(batches)}:")

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = {
                executor.submit(generate_insight, p): p
                for p in batch
            }
            for future in as_completed(futures):
                pid, name, ok, err = future.result()
                if ok:
                    success += 1
                    print(f"  ✓ {pid} — {name}")
                else:
                    failed += 1
                    print(f"  ✗ {pid} — {err}")

        # Wait 10 seconds between batches to avoid throttling
        if batch_num < len(batches) - 1:
            print(f"  Waiting 10s before next batch...\n")
            time.sleep(10)

    print("-" * 60)
    print(f"\n✅ Complete!")
    print(f"  Success : {success}/{total}")
    print(f"  Failed  : {failed}/{total}")
    print(f"\nOpen localhost:3000 → click any portfolio → see AI insights!")


if __name__ == "__main__":
    main()