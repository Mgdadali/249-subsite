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

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json", scope
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
