import os
import json
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# قراءة credentials من Environment Variable
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")

if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds_dict = json.loads(google_creds_json)

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, scope
)

client = gspread.authorize(creds)
sheet = client.open("249 – Customer Tracking").sheet1


@app.route("/track")
def track():
    code = request.args.get("code")

    if not code:
        return jsonify({"error": "الرجاء إدخال كود المتابعة"}), 400

    records = sheet.get_all_records()

    for row in records:
        if row["TrackingCode"] == code:
            return jsonify({
                "name": row["Name"],
                "service": row["Service"],
                "status": row["Status"],
                "step": row["CurrentStep"],
                "notes": row["Notes"],
                "last_update": row["LastUpdate"]
            })

    return jsonify({"error": "كود المتابعة غير صحيح"}), 404


if __name__ == "__main__":
    app.run()
