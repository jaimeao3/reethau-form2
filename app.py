from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from functools import wraps
app = Flask(__name__)
app.secret_key = "reethau_secret_key_2024"

SPREADSHEET_ID = "1M76I4Ryik_oRX81hyjI_7mpWhwUfGYq-rIscEqJ_YwI"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ============================================================
# KONFIGURASI ADMIN — ganti username dan password di sini
# ============================================================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "reethau1"
# ============================================================

def get_sheet():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

def ensure_sheet(sheet_obj, title, headers):
    try:
        ws = sheet_obj.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet_obj.add_worksheet(title=title, rows=1000, cols=30)
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(headers)
    elif first_row != headers:
        ws.update('A1', [headers])
    return ws

def get_next_row_id(sheet):
    records = sheet.get_all_values()
    return len(records) if len(records) > 1 else 1

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ==================== MAIN FORM ====================

@app.route("/")
def index():
    return render_template("form.html")

@app.route("/get-all-ids")
def get_all_ids():
    try:
        sheet_obj = get_sheet()
        id_sheet = sheet_obj.worksheet("ID Request")
        all_values = id_sheet.get_all_values()
        ids = []
        if len(all_values) > 1:
            for row in all_values[1:]:
                try:
                    val = str(row[1]).strip()
                    if val:
                        ids.append(val)
                except IndexError:
                    pass
        unique_ids = list(dict.fromkeys(ids))
        return jsonify({"status": "success", "ids": unique_ids})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/get-data-by-id/<id_request>")
def get_data_by_id(id_request):
    try:
        sheet_obj = get_sheet()
        hasil = {}

        # Cari di "ID Request" — kolom B
        try:
            id_sheet = sheet_obj.worksheet("ID Request")
            id_values = id_sheet.get_all_values()
            id_headers = id_values[0] if id_values else []
            for row in id_values[1:]:
                if str(row[1]).strip() == str(id_request).strip():
                    hasil = dict(zip(id_headers, row))
                    break
        except Exception:
            pass

        # Cari di "Hasil Input" — ambil Tanggal Request PTK
        try:
            hasil_sheet = sheet_obj.worksheet("Hasil Input")
            hasil_values = hasil_sheet.get_all_values()
            hasil_headers = hasil_values[0] if hasil_values else []
            for row in hasil_values[1:]:
                for val in row:
                    if str(val).strip() == str(id_request).strip():
                        hasil_data = dict(zip(hasil_headers, row))
                        hasil.update(hasil_data)
                        break
        except Exception:
            pass

        # Cari di "Form Permintaan"
        try:
            fpk_sheet = sheet_obj.worksheet("Form Permintaan")
            fpk_values = fpk_sheet.get_all_values()
            fpk_headers = fpk_values[0] if fpk_values else []
            for row in fpk_values[1:]:
                if str(row[1]).strip() == str(id_request).strip():
                    fpk_data = dict(zip(fpk_headers, row))
                    hasil.update(fpk_data)
                    break
        except Exception:
            pass

        if hasil:
            return jsonify({"status": "success", "data": hasil})
        return jsonify({"status": "not_found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.form
        required = ["nama_pelamar", "no_tlp", "posisi_lamaran", "penempatan", "grade", "induk_perusahaan"]
        for field in required:
            if not data.get(field, "").strip():
                return jsonify({"status": "error", "message": f"Field '{field}' wajib diisi!"}), 400

        sheet_obj = get_sheet()
        tahun = datetime.now().year
        tgl_request = datetime.now().strftime("%Y-%m-%d")
        id_request_dipilih = data.get("id_request", "")

        # ---- Hasil Input ----
        HEADERS_HASIL = [
            "NO", "Tahun Request", "ID Request", "Tanggal Request FPK",
            "Tanggal Rerquest PTK", "Nama", "Posisi Lamaran", "Penempatan", "Grade",
            "Induk Perusahaan", "Link Form", "No Tlp", "Email", "ID Request Dipilih"
        ]
        hasil_sheet = ensure_sheet(sheet_obj, "Hasil Input", HEADERS_HASIL)
        no_urut = get_next_row_id(hasil_sheet)

        hasil_sheet.append_row([
            no_urut, tahun, id_request_dipilih, tgl_request,
            data.get("tgl_request_ptk", ""),
            data.get("nama_pelamar", ""),
            data.get("posisi_lamaran", ""),
            data.get("penempatan", ""),
            data.get("grade", ""),
            data.get("induk_perusahaan", ""),
            data.get("link_form", ""),
            data.get("no_tlp", ""),
            data.get("email", ""),
            id_request_dipilih,
        ])

        # ---- Form Permintaan ----
        HEADERS_FPK = [
            "Divisi", "ID Form Permintaan Tenaga Kerja", "FPK Name", "PT Induk",
            "Lokasi Penempatan", "Grade", "Tanggal Request FPK", "Tanggal Approve FPK",
            "Form FPK", "Budget/Non Budget", "Category", "Detail Category",
            "Tahun Request", "Jumlah Hari", "Vacancy Request", "Joined", "CV Process"
        ]
        fpk_sheet = ensure_sheet(sheet_obj, "Form Permintaan", HEADERS_FPK)
        fpk_sheet.append_row([
            data.get("divisi", ""), id_request_dipilih,
            data.get("fpk_name", ""), data.get("induk_perusahaan", ""),
            data.get("penempatan", ""), data.get("grade", ""),
            tgl_request, data.get("tgl_approve_fpk", ""),
            data.get("form_fpk", "NO"), data.get("budget_status", "Non Budget"),
            data.get("category", ""), data.get("detail_category", ""),
            tahun, data.get("jumlah_hari", ""),
            data.get("vacancy_request", 1),
            data.get("joined", ""), data.get("cv_process", ""),
        ])

        # ---- ID Request ----
        HEADERS_ID = [
            "Timestamp", "ID Request Dipilih", "Nama Pelamar", "No Tlp", "Email",
            "Posisi Lamaran", "Penempatan", "Grade", "Induk Perusahaan",
            "FPK Name", "Divisi", "Budget/Non Budget", "Category", "Detail Category",
            "Vacancy Request", "Form FPK", "Tanggal Approve BOD", "Tanggal Approve FPK",
            "Joined", "CV Process", "Link Form"
        ]
        id_sheet = ensure_sheet(sheet_obj, "ID Request", HEADERS_ID)
        id_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            id_request_dipilih,
            data.get("nama_pelamar", ""), data.get("no_tlp", ""), data.get("email", ""),
            data.get("posisi_lamaran", ""), data.get("penempatan", ""),
            data.get("grade", ""), data.get("induk_perusahaan", ""),
            data.get("fpk_name", ""), data.get("divisi", ""),
            data.get("budget_status", ""), data.get("category", ""),
            data.get("detail_category", ""), data.get("vacancy_request", ""),
            data.get("form_fpk", ""), data.get("tgl_request_ptk", ""),
            data.get("tgl_approve_bod", ""),
            data.get("joined", ""), data.get("cv_process", ""),
            data.get("link_form", ""),
        ])

        return jsonify({
            "status": "success",
            "message": f"Data berhasil disimpan! ID Request: {id_request_dipilih}",
            "id_request": id_request_dipilih,
        })

    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File credentials.json tidak ditemukan."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== ADMIN DASHBOARD ====================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Username atau password salah."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    try:
        sheet_obj = get_sheet()
        id_sheet = sheet_obj.worksheet("ID Request")
        all_values = id_sheet.get_all_values()

        if not all_values or len(all_values) < 2:
            return render_template("admin_dashboard.html", rows=[], headers=[], summary={})

        headers = all_values[0]
        rows = all_values[1:]

        # Hitung summary per ID Request
        summary = {}
        for row in rows:
            try:
                id_req = str(row[1]).strip()  # Kolom B = ID Request Dipilih
                if not id_req:
                    continue
                cv_process = str(row[headers.index("CV Process")] if "CV Process" in headers else "").strip()
                timestamp  = str(row[0]).strip()  # Kolom A = Timestamp

                if id_req not in summary:
                    summary[id_req] = {
                        "total_cv": 0,
                        "entries": [],
                        "posisi": str(row[headers.index("Posisi Lamaran")] if "Posisi Lamaran" in headers else "").strip(),
                        "penempatan": str(row[headers.index("Penempatan")] if "Penempatan" in headers else "").strip(),
                    }
                summary[id_req]["total_cv"] += 1
                summary[id_req]["entries"].append({
                    "nama": str(row[headers.index("Nama Pelamar")] if "Nama Pelamar" in headers else "").strip(),
                    "timestamp": timestamp,
                    "cv_process": cv_process,
                    "posisi": str(row[headers.index("Posisi Lamaran")] if "Posisi Lamaran" in headers else "").strip(),
                })
            except (ValueError, IndexError):
                continue

        return render_template("admin_dashboard.html",
                               headers=headers, rows=rows, summary=summary)
    except Exception as e:
        return render_template("admin_dashboard.html", rows=[], headers=[], summary={}, error=str(e))

@app.route("/admin/api/dashboard-data")
@login_required
def dashboard_data():
    """API untuk refresh data dashboard tanpa reload halaman."""
    try:
        sheet_obj = get_sheet()
        id_sheet = sheet_obj.worksheet("ID Request")
        all_values = id_sheet.get_all_values()
        if not all_values or len(all_values) < 2:
            return jsonify({"status": "success", "rows": [], "headers": []})
        return jsonify({
            "status": "success",
            "headers": all_values[0],
            "rows": all_values[1:]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/data")
def view_data():
    try:
        sheet_obj = get_sheet()
        hasil_sheet = sheet_obj.worksheet("Hasil Input")
        records = hasil_sheet.get_all_values()
        headers = records[0] if records else []
        rows = records[1:] if len(records) > 1 else []
        return render_template("data.html", headers=headers, rows=rows)
    except Exception as e:
        return render_template("data.html", headers=[], rows=[], error=str(e))

if __name__ == "__main__":
    app.run(debug=True, port=5000)git commit -m "deploy reethau"git rm --cached credentials.json