import os
import json
import gspread
from flask import Flask, request, jsonify, send_from_directory
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

# ==============================
# إعداد Flask
# ==============================
app = Flask(__name__, static_folder="frontend")
CORS(app)

# ==============================
# إعداد Google Sheets
# ==============================
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")

if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds_dict = json.loads(google_creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("249 – Customer Tracking").sheet1

# ==============================
# Routes للواجهة
# ==============================
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# ==============================
# API لمتابعة الطلب
# ==============================
@app.route("/track")
def track():
    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"error":"الرجاء إدخال كود المتابعة"}), 400

    records = sheet.get_all_records()
    for row in records:
        tracking_code = str(row.get("TrackingCode", "")).strip().upper()
        if tracking_code == code:
            return jsonify({
                "name": row.get("Name", ""),
                "service": row.get("Service", ""),
                "status": row.get("Status", ""),
                "step": row.get("CurrentStep", ""),
                "notes": row.get("Notes", ""),
                "last_update": row.get("LastUpdate", "")
            })

    return jsonify({"error":"كود المتابعة غير صحيح"}), 404

# ==============================
# تشغيل التطبيق
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
