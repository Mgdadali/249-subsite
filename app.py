import os, json, gspread
from flask import Flask, request, jsonify, send_from_directory
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

app = Flask(__name__, static_folder="frontend")
CORS(app)

# ==============================
# Google Sheets Setup
# ==============================
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(google_creds_json), scope)
client = gspread.authorize(creds)
sheet = client.open("249 – Customer Tracking").sheet1

# ==============================
# Serve Frontend
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
        return jsonify({"error":"الرجاء إدخال كود المتابعة"}),400

    for row in sheet.get_all_records():
        if row["TrackingCode"].strip().upper() == code:
            return jsonify({
                "name": row["Name"],  # الاسم من Google Sheet فقط
                "service": row["Service"],
                "status": row["Status"],
                "step": row["CurrentStep"],
                "notes": row["Notes"],
                "last_update": row["LastUpdate"]
            })
    return jsonify({"error":"كود المتابعة غير صحيح"}),404

# ==============================
# تشغيل التطبيق
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
