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

def _sheet_header_map(sheet):
    """Return dict mapping header name -> 1-based col index."""
    header = sheet.row_values(1)
    return {h: i+1 for i, h in enumerate(header)}

# find checklist row matching code + stepName, return row number and current Done value (string)
def _find_checklist_row(code, step_name):
    values = checklist_sheet.get_all_values()
    if not values:
        return None
    header = values[0]
    try:
        code_i = header.index("TrackingCode")
        step_i = header.index("StepName")
        done_i = header.index("Done")
    except ValueError:
        return None
    for idx, row in enumerate(values[1:], start=2):
        # safe access
        rc = row[code_i] if len(row) > code_i else ""
        rs = row[step_i] if len(row) > step_i else ""
        rd = row[done_i] if len(row) > done_i else ""
        if str(rc).strip().upper() == code and str(rs).strip() == str(step_name).strip():
            return idx, rd
    return None

# ================== Home Page ==================
@app.route("/")
def home():
    return render_template("index.html")  # home static page

# ================== Client page route ==================
@app.route("/client/<code>")
def client_page(code):
    code = code.strip().upper()
    clients = clients_sheet.get_all_records()
    client_data = None
    for row in clients:
        if str(row.get("TrackingCode","")).strip().upper() == code:
            client_data = row
            break
    if not client_data:
        return "كود المتابعة غير صحيح ❌", 404
    # render checklist page (client-side will fetch /track for checklist JSON)
    return render_template("checklist.html", code=code, client_name=client_data.get("Name",""), service=client_data.get("Service",""))

# ================== Client Tracking API ==================
@app.route("/track")
def track():
    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "الرجاء إدخال كود المتابعة"}), 400

    clients = clients_sheet.get_all_records()
    client_data = None
    for row in clients:
        if str(row.get("TrackingCode","")).strip().upper() == code:
            client_data = row
            break
    if not client_data:
        return jsonify({"error": "كود المتابعة غير صحيح"}), 404

    steps = []
    checklist = checklist_sheet.get_all_records()
    for step in checklist:
        if str(step.get("TrackingCode","")).strip().upper() == code:
            steps.append({"name": step.get("StepName",""), "done": bool(step.get("Done", False))})

    return jsonify({
        "name": client_data.get("Name",""),
        "service": client_data.get("Service",""),
        "checklist": steps
    })

# ================== Admin Login (render) ==================
@app.route("/admin", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        admins = admins_sheet.get_all_records()
        for admin in admins:
            if admin.get("Username") == username and str(admin.get("Password")) == password:
                session["admin"] = username
                return redirect("/admin/dashboard")
        return render_template("admin_login.html", error="بيانات الدخول غير صحيحة")
    return render_template("admin_login.html")

# ================== Admin Dashboard (render) ==================
@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect("/admin")
    return render_template("admin_dashboard.html")

# ================== Admin API: list clients ==================
@app.route("/admin/api/clients")
def admin_api_clients():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403
    clients = clients_sheet.get_all_records()
    # return minimal info
    out = [{"code": str(r.get("TrackingCode","")), "name": r.get("Name",""), "service": r.get("Service","")} for r in clients]
    return jsonify(out)

# ================== Admin API: get client checklist ==================
@app.route("/admin/api/client/<code>/checklist")
def admin_api_client_checklist(code):
    if not admin_required():
        return jsonify({"error":"unauth"}), 403
    code = code.strip().upper()
    checklist = checklist_sheet.get_all_records()
    steps = []
    for s in checklist:
        if str(s.get("TrackingCode","")).strip().upper() == code:
            steps.append({"name": s.get("StepName",""), "done": bool(s.get("Done", False))})
    return jsonify({"code": code, "steps": steps})

# ================== Admin API: toggle step done (POST) ==================
@app.route("/admin/api/client/<code>/toggle-step", methods=["POST"])
def admin_api_toggle_step(code):
    if not admin_required():
        return jsonify({"error":"unauth"}), 403
    payload = request.json or {}
    step_name = payload.get("step")
    if not step_name:
        return jsonify({"error":"missing step"}), 400
    code = code.strip().upper()
    found = _find_checklist_row(code, step_name)
    if not found:
        return jsonify({"error":"step not found"}), 404
    row_num, current_done = found
    # determine new value
    new_val = "FALSE"
    cur = str(current_done).strip().upper()
    if cur in ["TRUE","1","TRUE "]:
        new_val = "FALSE"
    else:
        new_val = "TRUE"
    # find 'Done' column index
    header_map = _sheet_header_map(checklist_sheet)
    done_col = header_map.get("Done")
    if not done_col:
        return jsonify({"error":"sheet header missing Done"}), 500
    checklist_sheet.update_cell(row_num, done_col, new_val)
    return jsonify({"ok": True, "new": new_val})

# ================== Admin API: delete step (POST) ==================
@app.route("/admin/api/client/<code>/delete-step", methods=["POST"])
def admin_api_delete_step(code):
    if not admin_required():
        return jsonify({"error":"unauth"}), 403
    payload = request.json or {}
    step_name = payload.get("step")
    if not step_name:
        return jsonify({"error":"missing step"}), 400
    code = code.strip().upper()
    found = _find_checklist_row(code, step_name)
    if not found:
        return jsonify({"error":"step not found"}), 404
    row_num, _ = found
    checklist_sheet.delete_row(row_num)
    return jsonify({"ok": True})

# ================== Admin API: add client (POST) - AJAX friendly ==================
@app.route("/admin/api/add-client", methods=["POST"])
def admin_api_add_client():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403
    payload = request.json or {}
    name = payload.get("name") or ""
    service = payload.get("service") or ""
    if not name:
        return jsonify({"error":"missing name"}), 400
    tracking_code = secrets.token_hex(4).upper()
    clients_sheet.append_row([tracking_code, name, service])
    return jsonify({"ok": True, "code": tracking_code, "name": name, "service": service})

# ================== Add client page (render) - fallback for form POST too ==================
@app.route("/admin/add-client", methods=["GET","POST"])
def add_client():
    if not admin_required():
        return redirect("/admin")
    if request.method == "POST":
        name = request.form.get("name")
        service = request.form.get("service")
        tracking_code = secrets.token_hex(4).upper()
        clients_sheet.append_row([tracking_code, name, service])
        return render_template("admin_add.html", message=f"تم إضافة العميل ✅ كود: {tracking_code}")
    return render_template("admin_add.html")

# ================== Manage Checklist (render fallback) ==================
@app.route("/admin/manage", methods=["GET"])
def manage_steps():
    if not admin_required():
        return redirect("/admin")
    # render management UI (we rely on admin_clients.html which contains client management)
    return render_template("admin_manage.html")

# ================== Admin Logout ==================
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin")

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))






# ================== Admin API: add step (POST) ==================
# ================== Admin API: add step (POST) ==================
@app.route("/admin/api/add-step", methods=["POST"])
def admin_api_add_step():
    if not admin_required():
        return jsonify({"error":"unauth"}), 403

    payload = request.json or {}
    step_name = payload.get("step") or ""
    code = payload.get("code", "").strip().upper()
    if not step_name or not code:
        return jsonify({"error":"missing step or code"}), 400

    # Append row with proper column order: A=Done, B=StepName, C=TrackingCode
    checklist_sheet.append_row(["FALSE", step_name, code], value_input_option='RAW')
    return jsonify({"ok": True})
