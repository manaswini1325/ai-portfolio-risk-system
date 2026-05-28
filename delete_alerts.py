import boto3

dynamodb = boto3.resource("dynamodb", region_name="ap-south-2")
table    = dynamodb.Table("RiskAlerts")

deleted = 0
while True:
    response = table.scan(Limit=25)
    items    = response.get("Items", [])
    if not items:
        break
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"alertId": item["alertId"]})
            deleted += 1
    print(f"Deleted {deleted} so far...")

print(f"Done! Total deleted: {deleted}")