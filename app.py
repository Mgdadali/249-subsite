import os, json, secrets
from functools import wraps
from datetime import datetime, timedelta
import gspread
from flask import Flask, request, jsonify, session, redirect, render_template
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

# ================== App Setup ==================
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "249-secret-key")

# ================== Simple Cache (تخزين مؤقت) ==================
class SimpleCache:
    def __init__(self, ttl=60):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return data
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, datetime.now())
    
    def clear(self, pattern=None):
        if pattern:
            keys = [k for k in self.cache.keys() if pattern in k]
            for k in keys:
                del self.cache[k]
        else:
            self.cache.clear()

cache = SimpleCache(ttl=30)  # 30 ثانية

# ================== Google Sheets ==================
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable not set")

creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(google_creds_json), scope)
client = gspread.authorize(creds)
spreadsheet = client.open("249 – Customer Tracking")

clients_sheet = spreadsheet.worksheet("Clients")
checklist_sheet = spreadsheet.worksheet("Checklist")
admins_sheet = spreadsheet.worksheet("Admins")
steps_sheet = spreadsheet.worksheet("Steps")

# ================== Decorators ==================
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin" not in session:
            return jsonify({"error": "unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated

# ================== Helper Functions ==================
def get_all_clients(use_cache=True):
    """جلب جميع العملاء مع التخزين المؤقت"""
    if use_cache:
        cached = cache.get("all_clients")
        if cached:
            return cached
    
    clients = clients_sheet.get_all_records()
    cache.set("all_clients", clients)
    return clients

def get_all_steps(use_cache=True):
    """جلب جميع المراحل العامة"""
    if use_cache:
        cached = cache.get("all_steps")
        if cached:
            return cached
    
    steps = [r["StepName"] for r in steps_sheet.get_all_records()]
    cache.set("all_steps", steps)
    return steps

def get_client_steps(code, use_cache=True):
    """جلب مراحل عميل محدد"""
    cache_key = f"client_steps_{code}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            return cached
    
    steps = {}
    for r in checklist_sheet.get_all_records():
        if r.get("TrackingCode", "").strip().upper() == code:
            steps[r["StepName"]] = str(r.get("Done", "")).strip().upper() == "TRUE"
    
    cache.set(cache_key, steps)
    return steps

def find_checklist_row(code, step_name):
    """العثور على صف في الـ Checklist"""
    values = checklist_sheet.get_all_values()
    for idx, row in enumerate(values[1:], start=2):
        if len(row) >= 3:
            track = row[2].strip().upper()
            step = row[1].strip()
            if track == code and step == step_name:
                return idx
    return None

# ================== Routes: Public ==================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/client/<code>")
def client_page(code):
    code = code.strip().upper()
    clients = get_all_clients()
    
    for row in clients:
        if str(row.get("TrackingCode", "")).strip().upper() == code:
            return render_template(
                "checklist.html",
                code=code,
                client_name=row.get("Name", ""),
                service=row.get("Service", "")
            )
    return "كود المتابعة غير صحيح ❌", 404

@app.route("/track")
def track():
    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "missing code"}), 400
    
    clients = get_all_clients()
    client_data = next((c for c in clients if str(c.get("TrackingCode", "")).strip().upper() == code), None)
    
    if not client_data:
        return jsonify({"error": "invalid code"}), 404
    
    all_steps = get_all_steps()
    client_steps = get_client_steps(code)
    
    checklist = [{"name": s, "done": client_steps.get(s, False)} for s in all_steps]
    
    return jsonify({
        "name": client_data.get("Name", ""),
        "service": client_data.get("Service", ""),
        "checklist": checklist
    })

# ================== Routes: Admin Auth ==================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        for admin in admins_sheet.get_all_records():
            if admin.get("Username") == username and str(admin.get("Password")) == password:
                session["admin"] = username
                return redirect("/admin/dashboard")
        
        return render_template("admin_login.html", error="بيانات غير صحيحة")
    
    return render_template("admin_login.html")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin")

# ================== Routes: Admin Dashboard ==================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/manage")
@admin_required
def admin_manage():
    return render_template("admin_manage.html")

# ================== API: Admin - Clients ==================
@app.route("/admin/api/clients")
@admin_required
def admin_clients():
    clients = get_all_clients(use_cache=False)  # دائماً بيانات محدثة للأدمن
    
    return jsonify([{
        "code": r.get("TrackingCode", ""),
        "name": r.get("Name", ""),
        "service": r.get("Service", "")
    } for r in clients])

@app.route("/admin/api/add-client", methods=["POST"])
@admin_required
def admin_add_client():
    data = request.json or {}
    name = data.get("name", "").strip()
    service = data.get("service", "").strip()
    
    if not name:
        return jsonify({"error": "missing name"}), 400
    
    code = secrets.token_hex(4).upper()
    clients_sheet.append_row([code, name, service])
    
    cache.clear("all_clients")
    
    return jsonify({"ok": True, "code": code})

# ================== API: Admin - Steps ==================
@app.route("/admin/api/client/<code>/steps")
@admin_required
def admin_client_steps(code):
    code = code.strip().upper()
    all_steps = get_all_steps(use_cache=False)
    client_steps = get_client_steps(code, use_cache=False)
    
    return jsonify([{
        "name": s,
        "done": client_steps.get(s, False)
    } for s in all_steps])

@app.route("/admin/api/client/<code>/toggle-step", methods=["POST"])
@admin_required
def toggle_step(code):
    code = code.strip().upper()
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    row_num = find_checklist_row(code, step_name)
    
    if row_num:
        # قراءة الحالة الحالية
        current_value = checklist_sheet.cell(row_num, 1).value
        new_value = "FALSE" if current_value == "TRUE" else "TRUE"
        checklist_sheet.update_cell(row_num, 1, new_value)
    else:
        # إضافة صف جديد
        checklist_sheet.append_row(["TRUE", step_name, code])
    
    cache.clear(f"client_steps_{code}")
    
    return jsonify({"ok": True})

@app.route("/admin/api/client/<code>/delete-step", methods=["POST"])
@admin_required
def delete_step(code):
    code = code.strip().upper()
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    row_num = find_checklist_row(code, step_name)
    
    if row_num:
        checklist_sheet.delete_rows(row_num)
        cache.clear(f"client_steps_{code}")
        return jsonify({"ok": True})
    
    return jsonify({"error": "step not found"}), 404

@app.route("/admin/api/add-step", methods=["POST"])
@admin_required
def admin_add_step():
    step = request.json.get("step", "").strip()
    
    if not step:
        return jsonify({"error": "missing step"}), 400
    
    steps_sheet.append_row([step])
    cache.clear("all_steps")
    
    return jsonify({"ok": True})

@app.route("/admin/api/delete-general-step", methods=["POST"])
@admin_required
def delete_general_step():
    """حذف مرحلة من القائمة العامة"""
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    # البحث عن الصف في Steps sheet
    values = steps_sheet.get_all_values()
    for idx, row in enumerate(values[1:], start=2):
        if row and row[0].strip() == step_name:
            steps_sheet.delete_rows(idx)
            cache.clear("all_steps")
            return jsonify({"ok": True})
    
    return jsonify({"error": "step not found"}), 404

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
