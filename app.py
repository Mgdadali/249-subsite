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

# ================== Simple Cache ==================
class SimpleCache:
    def __init__(self, ttl=30):
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

cache = SimpleCache(ttl=30)

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
    if use_cache:
        cached = cache.get("all_clients")
        if cached:
            return cached
    clients = clients_sheet.get_all_records()
    cache.set("all_clients", clients)
    return clients

def get_all_steps(use_cache=True):
    if use_cache:
        cached = cache.get("all_steps")
        if cached:
            return cached
    steps = [r["StepName"] for r in steps_sheet.get_all_records()]
    cache.set("all_steps", steps)
    return steps

def get_client_checklist(code):
    """جلب جميع المراحل المفعّلة للعميل مع حالاتها"""
    checklist_data = checklist_sheet.get_all_records()
    result = {}
    for row in checklist_data:
        if row.get("TrackingCode", "").strip().upper() == code:
            step_name = row.get("StepName", "").strip()
            is_done = str(row.get("Done", "")).strip().upper() == "TRUE"
            result[step_name] = is_done
    return result

def find_checklist_row(code, step_name):
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
    
    # جلب المراحل المفعّلة فقط للعميل
    client_checklist = get_client_checklist(code)
    
    # ترتيب المراحل حسب القائمة العامة
    all_steps = get_all_steps()
    checklist = []
    for step in all_steps:
        if step in client_checklist:
            checklist.append({"name": step, "done": client_checklist[step]})
    
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
                return redirect("/admin/manage")  # توجيه مباشر لصفحة الإدارة
        
        return render_template("admin_login.html", error="بيانات غير صحيحة")
    
    return render_template("admin_login.html")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin")

@app.route("/admin/manage")
@admin_required
def admin_manage():
    return render_template("admin_manage.html")

# ================== API: Admin - Clients ==================
@app.route("/admin/api/clients")
@admin_required
def admin_clients():
    clients = get_all_clients(use_cache=False)
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

# ================== API: Admin - Steps Management ==================
@app.route("/admin/api/client/<code>/all-steps")
@admin_required
def admin_all_steps(code):
    """جلب جميع المراحل العامة مع حالة التفعيل والإكمال للعميل"""
    code = code.strip().upper()
    all_steps = get_all_steps(use_cache=False)
    client_checklist = get_client_checklist(code)
    
    result = []
    for step in all_steps:
        result.append({
            "name": step,
            "enabled": step in client_checklist,  # هل المرحلة مفعّلة للعميل؟
            "done": client_checklist.get(step, False)  # هل مكتملة؟
        })
    
    return jsonify(result)

@app.route("/admin/api/client/<code>/toggle-step", methods=["POST"])
@admin_required
def toggle_step_enabled(code):
    """تفعيل/إلغاء تفعيل مرحلة للعميل"""
    code = code.strip().upper()
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    row_num = find_checklist_row(code, step_name)
    
    if row_num:
        # المرحلة موجودة - حذفها (إلغاء التفعيل)
        checklist_sheet.delete_rows(row_num)
    else:
        # المرحلة غير موجودة - إضافتها (تفعيل)
        checklist_sheet.append_row(["FALSE", step_name, code])
    
    cache.clear(f"client_checklist_{code}")
    return jsonify({"ok": True})

@app.route("/admin/api/client/<code>/toggle-done", methods=["POST"])
@admin_required
def toggle_step_done(code):
    """تبديل حالة الإكمال للمرحلة"""
    code = code.strip().upper()
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    row_num = find_checklist_row(code, step_name)
    
    if not row_num:
        return jsonify({"error": "step not enabled"}), 400
    
    # قراءة الحالة الحالية وعكسها
    current_value = checklist_sheet.cell(row_num, 1).value
    new_value = "FALSE" if current_value == "TRUE" else "TRUE"
    checklist_sheet.update_cell(row_num, 1, new_value)
    
    cache.clear(f"client_checklist_{code}")
    return jsonify({"ok": True})

@app.route("/admin/api/add-step", methods=["POST"])
@admin_required
def admin_add_step():
    """إضافة مرحلة جديدة للقائمة العامة"""
    step = request.json.get("step", "").strip()
    
    if not step:
        return jsonify({"error": "missing step"}), 400
    
    steps_sheet.append_row([step])
    cache.clear("all_steps")
    
    return jsonify({"ok": True})

@app.route("/admin/api/delete-step", methods=["POST"])
@admin_required
def delete_general_step():
    """حذف مرحلة من القائمة العامة"""
    step_name = request.json.get("step", "").strip()
    
    if not step_name:
        return jsonify({"error": "missing step"}), 400
    
    values = steps_sheet.get_all_values()
    for idx, row in enumerate(values[1:], start=2):
        if row and row[0].strip() == step_name:
            steps_sheet.delete_rows(idx)
            
            # حذف المرحلة من جميع العملاء
            checklist_values = checklist_sheet.get_all_values()
            rows_to_delete = []
            for i, r in enumerate(checklist_values[1:], start=2):
                if len(r) >= 2 and r[1].strip() == step_name:
                    rows_to_delete.append(i)
            
            for row_idx in reversed(rows_to_delete):
                checklist_sheet.delete_rows(row_idx)
            
            cache.clear()
            return jsonify({"ok": True})
    
    return jsonify({"error": "step not found"}), 404

@app.route("/admin/api/reorder-steps", methods=["POST"])
@admin_required
def reorder_steps():
    """إعادة ترتيب المراحل العامة"""
    new_order = request.json.get("steps", [])
    
    if not new_order:
        return jsonify({"error": "missing steps"}), 400
    
    try:
        # حذف جميع الصفوف الحالية (ما عدا الهيدر)
        row_count = steps_sheet.row_count
        if row_count > 1:
            steps_sheet.delete_rows(2, row_count)
        
        # إضافة المراحل بالترتيب الجديد
        for step in new_order:
            steps_sheet.append_row([step])
        
        cache.clear("all_steps")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================== Run ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
