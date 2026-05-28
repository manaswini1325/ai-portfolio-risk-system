from flask import Flask

from flask_cors import CORS

import boto3

from decimal import Decimal

import json

app = Flask(__name__)

CORS(app)

dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-2"
)

risk_table = dynamodb.Table(
    "RiskAlerts"
)

ai_table = dynamodb.Table(
    "AIInsights"
)


class DecimalEncoder(
    json.JSONEncoder
):

    def default(self, obj):

        if isinstance(obj, Decimal):

            return float(obj)

        return super().default(obj)


@app.route("/alerts")

def get_alerts():

    response = risk_table.scan()

    return json.dumps(
        response["Items"],
        cls=DecimalEncoder
    )


@app.route("/insights")

def get_insights():

    response = ai_table.scan()

    return json.dumps(
        response["Items"],
        cls=DecimalEncoder
    )


if __name__ == "__main__":

    app.run(debug=True)