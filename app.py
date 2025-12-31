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
steps_sheet     = spreadsheet.worksheet("Steps")  # ⭐ جديد

# ================== Helpers ==================
def admin_required():
    return "admin" in session

def _find_checklist_row(code, step_name):
    values = checklist_sheet.get_all_values()
    if not values:
        return None

    for idx, row in enumerate(values[1:], start=2):
        done  = row[0] if len(row) > 0 else ""
        step  = row[1] if len(row) > 1 else ""
        track = row[2] if len(row) > 2 else ""

        if track.strip().upper() == code and step.strip() == step_name.strip():
            return idx, done
    return None

# ================== Home ==================
@app.route("/")
def home():
    return render_template("index.html")

# ================== Client Page ==================
@app.route("/client/<code>")
def client_page(code):
    code = code.strip().upper()
    for row in clients_sheet.get_all_records():
        if str(row.get("TrackingCode","")).strip().upper() == code:
            return render_template(
                "checklist.html",
                code=code,
                client_name=row.get("Name",""),
                service=row.get("Service","")
            )
    return "كود المتابعة غير صحيح ❌", 404

# ================== Client Tracking API ==================
@app.route("/track")
def track():
    code = request.args.get("code","").strip().upper()
    if not code:
        return jsonify({"error":"missing code"}), 400

    client_data = None
    for r in clients_sheet.get_all_records():
        if str(r.get("TrackingCode","")).strip().upper() == code:
            client_data = r
            break
    if not client_data:
        return jsonify({"error":"invalid code"}), 404

    steps = []
    for s in checklist_sheet.get_all_records():
        if s.get("TrackingCode","").strip().upper() == code:
            steps.append({
                "name": s.get("StepName",""),
                "done": bool(s.get("Done"))
            })

    return jsonify({
        "name": client_data.get("Name",""),
        "service": client_data.get("Service",""),
        "checklist": steps
    })

# ================== Admin Login ==================
@app.route("/admin", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        for admin in admins_sheet.get_all_records():
            if admin.get("Username")==username and str(admin.get("Password"))==password:
                session["admin"] = username
                return redirect("/admin/dashboard")
        return render_template("admin_login.html", error="بيانات غير صحيحة")
    return render_template("admin_login.html")

# ================== Admin Dashboard ==================
@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect("/admin")
    return render_template("admin_dashboard.html")

# ================== Admin API: Clients ==================
@app.route("/admin/api/clients")
def admin_clients():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    return jsonify([
        {
            "code": r.get("TrackingCode",""),
            "name": r.get("Name",""),
            "service": r.get("Service","")
        }
        for r in clients_sheet.get_all_records()
    ])

# ================== Admin API: ALL Steps (⭐ الأهم) ==================
@app.route("/admin/api/client/<code>/all-steps")
def admin_all_steps(code):
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    code = code.strip().upper()

    all_steps = [r["StepName"] for r in steps_sheet.get_all_records()]

    client_steps = {
        r["StepName"]: bool(r["Done"])
        for r in checklist_sheet.get_all_records()
        if r["TrackingCode"].strip().upper() == code
    }

    return jsonify([
        {"name": s, "done": client_steps.get(s, False)}
        for s in all_steps
    ])

# ================== Admin API: SAVE Steps (زر حفظ) ==================
@app.route("/admin/api/client/<code>/save-steps", methods=["POST"])
def save_steps(code):
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    code = code.strip().upper()
    steps = request.json.get("steps", {})

    for step_name, done in steps.items():
        found = _find_checklist_row(code, step_name)
        if found:
            row_num, _ = found
            checklist_sheet.update_cell(row_num, 1, "TRUE" if done else "FALSE")
        else:
            if done:
                checklist_sheet.append_row(["TRUE", step_name, code])

    return jsonify({"ok": True})

# ================== Admin API: Add Step (عام) ==================
@app.route("/admin/api/add-step", methods=["POST"])
def admin_add_step():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    step = (request.json or {}).get("step","").strip()
    if not step:
        return jsonify({"error":"missing step"}), 400

    steps_sheet.append_row([step])
    return jsonify({"ok": True})

# ================== Admin API: Add Client ==================
@app.route("/admin/api/add-client", methods=["POST"])
def admin_add_client():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    name = request.json.get("name","")
    service = request.json.get("service","")
    if not name:
        return jsonify({"error":"missing name"}), 400

    code = secrets.token_hex(4).upper()
    clients_sheet.append_row([code, name, service])
    return jsonify({"ok":True, "code":code})

# ================== Admin Manage ==================
@app.route("/admin/manage")
def admin_manage():
    if not admin_required():
        return redirect("/admin")
    return render_template("admin_manage.html")

# ================== Logout ==================
@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin")

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
