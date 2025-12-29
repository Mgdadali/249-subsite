import os
import json
import secrets
import gspread
from flask import Flask, request, jsonify, session, redirect
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

# ================== App Setup ==================
app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv("SECRET_KEY", "249-secret-key")

# ================== Google Sheets Setup ==================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(google_creds_json),
    scope
)

client = gspread.authorize(creds)
spreadsheet = client.open("249 – Customer Tracking")

clients_sheet   = spreadsheet.worksheet("Clients")
checklist_sheet = spreadsheet.worksheet("Checklist")
admins_sheet    = spreadsheet.worksheet("Admins")

# ================== Helpers ==================
def admin_required():
    return "admin" in session

# ================== Client Tracking ==================
@app.route("/track")
def track():
    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "الرجاء إدخال كود المتابعة"}), 400

    clients = clients_sheet.get_all_records()
    client_data = None

    for row in clients:
        if str(row["TrackingCode"]).strip().upper() == code:
            client_data = row
            break

    if not client_data:
        return jsonify({"error": "كود المتابعة غير صحيح"}), 404

    steps = []
    checklist = checklist_sheet.get_all_records()
    for step in checklist:
        if str(step["TrackingCode"]).strip().upper() == code:
            steps.append({
                "name": step["StepName"],
                "done": bool(step["Done"])
            })

    return jsonify({
        "name": client_data["Name"],
        "service": client_data["Service"],
        "checklist": steps
    })

# ================== Admin Login ==================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        admins = admins_sheet.get_all_records()
        for admin in admins:
            if admin["Username"] == username and str(admin["Password"]) == password:
                session["admin"] = username
                return redirect("/admin/dashboard")

        return "بيانات الدخول غير صحيحة ❌"

    return """
    <h2>تسجيل دخول الأدمن</h2>
    <form method="post">
        <input name="username" placeholder="اسم المستخدم"><br><br>
        <input name="password" type="password" placeholder="كلمة المرور"><br><br>
        <button>دخول</button>
    </form>
    """

# ================== Admin Dashboard ==================
@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect("/admin")

    return """
    <h2>لوحة تحكم الأدمن</h2>
    <ul>
        <li><a href="/admin/add-client">➕ إضافة عميل</a></li>
        <li><a href="/admin/manage">✅ إدارة المراحل</a></li>
        <li><a href="/admin/logout">🚪 تسجيل خروج</a></li>
    </ul>
    """

# ================== Add Client ==================
@app.route("/admin/add-client", methods=["GET", "POST"])
def add_client():
    if not admin_required():
        return redirect("/admin")

    if request.method == "POST":
        name = request.form.get("name")
        service = request.form.get("service")

        tracking_code = secrets.token_hex(4).upper()
        clients_sheet.append_row([tracking_code, name, service])

        return f"""
        <p>تم إضافة العميل بنجاح ✅</p>
        <p>كود المتابعة: <b>{tracking_code}</b></p>
        <a href="/admin/dashboard">رجوع</a>
        """

    return """
    <h3>إضافة عميل جديد</h3>
    <form method="post">
        <input name="name" placeholder="اسم العميل"><br><br>
        <input name="service" placeholder="الخدمة"><br><br>
        <button>حفظ</button>
    </form>
    """

# ================== Manage Checklist ==================
@app.route("/admin/manage", methods=["GET", "POST"])
def manage_steps():
    if not admin_required():
        return redirect("/admin")

    if request.method == "POST":
        code = request.form.get("code").strip().upper()
        step = request.form.get("step")

        checklist_sheet.append_row([code, step, False])
        return "تمت إضافة المرحلة ✅ <br><a href='/admin/manage'>رجوع</a>"

    return """
    <h3>إدارة مراحل الطلب</h3>
    <form method="post">
        <input name="code" placeholder="كود المتابعة"><br><br>
        <input name="step" placeholder="اسم المرحلة"><br><br>
        <button>إضافة مرحلة</button>
    </form>
    """

# ================== Logout ==================
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin")

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
