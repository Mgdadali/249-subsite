import os, json, secrets
import gspread
from flask import Flask, request, jsonify, session, redirect, render_template
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

# ================== App Setup ==================
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "249-secret-key")

# ================== Google Sheets ==================
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(google_creds_json), scope)
client = gspread.authorize(creds)
spreadsheet = client.open("249 – Customer Tracking")
clients_sheet   = spreadsheet.worksheet("Clients")
checklist_sheet = spreadsheet.worksheet("Checklist")
admins_sheet    = spreadsheet.worksheet("Admins")

# ================== Helpers ==================
def admin_required():
    return "admin" in session

# ================== Home Page ==================
@app.route("/")
def home():
    return render_template("index.html")  # واجهة رئيسية ثابتة

# ================== Client Checklist Page ==================
@app.route("/client/<code>")
def client_page(code):
    code = code.strip().upper()
    clients = clients_sheet.get_all_records()
    client_data = None
    for row in clients:
        if str(row["TrackingCode"]).strip().upper() == code:
            client_data = row
            break
    if not client_data:
        return "كود المتابعة غير صحيح ❌", 404
    return render_template("checklist.html", code=code, client_name=client_data["Name"], service=client_data["Service"])

# ================== Client Tracking API ==================
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
            steps.append({"name": step["StepName"], "done": bool(step["Done"])})

    return jsonify({
        "name": client_data["Name"],
        "service": client_data["Service"],
        "checklist": steps
    })

# ================== Admin Login ==================
@app.route("/admin", methods=["GET","POST"])
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
    return render_template("admin_login.html")

# ================== Admin Dashboard ==================
@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect("/admin")
    return render_template("admin_dashboard.html")

# ================== Add Client ==================
@app.route("/admin/add-client", methods=["GET","POST"])
def add_client():
    if not admin_required():
        return redirect("/admin")
    if request.method == "POST":
        name = request.form.get("name")
        service = request.form.get("service")
        tracking_code = secrets.token_hex(4).upper()
        clients_sheet.append_row([tracking_code, name, service])
        return f"<p>تم إضافة العميل بنجاح ✅</p><p>كود المتابعة: <b>{tracking_code}</b></p><a href='/admin/dashboard'>رجوع</a>"
    return render_template("admin_add.html")

# ================== Manage Checklist ==================
@app.route("/admin/manage", methods=["GET","POST"])
def manage_steps():
    if not admin_required():
        return redirect("/admin")
    if request.method == "POST":
        code = request.form.get("code").strip().upper()
        step = request.form.get("step")
        checklist_sheet.append_row([code, step, False])
        return "تمت إضافة المرحلة ✅ <br><a href='/admin/manage'>رجوع</a>"
    return render_template("admin_manage.html")

# ================== Admin Logout ==================
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin")

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
