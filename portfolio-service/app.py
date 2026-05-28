from flask import Flask, jsonify
import json

app = Flask(__name__)

@app.route("/portfolios")
def get_portfolios():

    with open("portfolios.json") as f:
        data = json.load(f)

    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)