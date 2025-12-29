import os
import json
from flask import Flask, request, jsonify, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================
# Google Sheets Setup
# ==============================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# قراءة credentials من Environment Variable
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds_dict = json.loads(google_creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("249 – Customer Tracking").sheet1

# ==============================
# الصفحة الرئيسية - ترحيب بالعميل
# ==============================
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>249 | متابعة الإجراءات</title>
    <style>
        body {
            font-family: Tahoma, Arial;
            background: #f2f6fb;
        }
        .container {
            max-width: 420px;
            margin: 90px auto;
            background: #fff;
            padding: 35px 30px;
            border-radius: 12px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.08);
            text-align: center;
        }
        h1 { color: #0a3d62; margin-bottom: 10px; }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border-radius: 6px;
            border: 1px solid #ccc;
        }
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(90deg,#0a3d62,#1e90ff);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover { opacity: 0.9; }
        .card {
            margin-top: 25px;
            background: #f9fbff;
            padding: 20px;
            border-radius: 10px;
            text-align: right;
            border-right: 4px solid #0a3d62;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>متابعة سير الإجراءات</h1>
    <p>من فضلك أدخل بيانات المتابعة</p>

    <input type="text" id="name" placeholder="اسم العميل">
    <input type="text" id="code" placeholder="كود المتابعة">

    <button onclick="track()">متابعة الطلب</button>

    <div id="result"></div>
</div>

<script>
function track() {
    const name = document.getElementById("name").value;
    const code = document.getElementById("code").value.trim().toUpperCase();
    const result = document.getElementById("result");

    if (!code) {
        alert("من فضلك أدخل كود المتابعة");
        return;
    }

    result.innerHTML = "جاري البحث...";

    fetch(`/track?code=${code}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                result.innerHTML = `<strong>${data.error}</strong>`;
                return;
            }

            result.innerHTML = `
                <div class="card">
                    <p><strong>مرحباً:</strong> ${name || "عميلنا الكريم"}</p>
                    <p><strong>الخدمة:</strong> ${data.service}</p>
                    <p><strong>الحالة:</strong> ${data.status}</p>
                    <p><strong>المرحلة الحالية:</strong> ${data.step}</p>
                    <p><strong>ملاحظات:</strong> ${data.notes}</p>
                    <p><strong>آخر تحديث:</strong> ${data.last_update}</p>
                </div>
            `;
        })
        .catch(() => {
            result.innerHTML = "حدث خطأ في الاتصال";
        });
}
</script>

</body>
</html>
""")

# ==============================
# API لمتابعة الطلب
# ==============================
@app.route("/track")
def track():
    code = request.args.get("code", "").strip().upper()

    if not code:
        return jsonify({"error": "الرجاء إدخال كود المتابعة"}), 400

    records = sheet.get_all_records()
    for row in records:
        if row["TrackingCode"].strip().upper() == code:
            return jsonify({
                "name": row["Name"],
                "service": row["Service"],
                "status": row["Status"],
                "step": row["CurrentStep"],
                "notes": row["Notes"],
                "last_update": row["LastUpdate"]
            })

    return jsonify({"error": "كود المتابعة غير صحيح"}), 404

# ==============================
# تشغيل التطبيق
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
