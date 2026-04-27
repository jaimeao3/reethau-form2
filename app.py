from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
from functools import wraps
import os
import json
import io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reethau_secret_key_2024")
app.jinja_env.filters['enumerate'] = enumerate

SPREADSHEET_ID = "1M76I4Ryik_oRX81hyjI_7mpWhwUfGYq-rIscEqJ_YwI"

# ============================================================
# GANTI dengan ID folder Google Drive tempat CV disimpan
# Cara dapat ID folder: buka folder di Google Drive,
# lihat URL: https://drive.google.com/drive/folders/[FOLDER_ID]
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "GANTI_FOLDER_ID_DRIVE")
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "reethau2024")

def get_credentials():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

def get_sheet():
    creds = get_credentials()
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

def get_drive_service():
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds)

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

def get_next_id(sheet):
    records = sheet.get_all_values()
    return len(records) if len(records) > 1 else 1

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ==================== UPLOAD CV ====================

@app.route("/upload-cv", methods=["POST"])
def upload_cv():
    """Upload CV ke Google Drive dan kembalikan link."""
    try:
        if 'cv_file' not in request.files:
            return jsonify({"status": "error", "message": "File CV tidak ditemukan"}), 400

        file = request.files['cv_file']
        nama_pelamar = request.form.get("nama_pelamar", "Kandidat")

        if file.filename == '':
            return jsonify({"status": "error", "message": "Tidak ada file dipilih"}), 400

        # Validasi tipe file
        allowed = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed:
            return jsonify({"status": "error", "message": f"Tipe file tidak didukung. Gunakan: PDF, DOC, DOCX, JPG, PNG"}), 400

        # Nama file di Drive: CV_NamaPelamar_Timestamp.ext
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = nama_pelamar.replace(" ", "_").replace("/", "_")
        filename = f"CV_{safe_name}_{timestamp}.{ext}"

        # Upload ke Google Drive
        drive_service = get_drive_service()

        file_metadata = {
            'name': filename,
            'parents': [DRIVE_FOLDER_ID]
        }

        mime_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

        file_content = file.read()
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=False
        )

        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        # Set permission: anyone with link can view
        drive_service.permissions().create(
            fileId=uploaded['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        link = uploaded.get('webViewLink', '')

        return jsonify({
            "status": "success",
            "link": link,
            "filename": filename,
            "file_id": uploaded['id']
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
        return jsonify({"status": "success", "ids": list(dict.fromkeys(ids))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/get-data-by-id/<id_request>")
def get_data_by_id(id_request):
    try:
        sheet_obj = get_sheet()
        hasil = {}

        try:
            id_sheet = sheet_obj.worksheet("ID Request")
            id_values = id_sheet.get_all_values()
            id_headers = id_values[0] if id_values else []
            for row in id_values[1:]:
                if len(row) > 1 and str(row[1]).strip() == str(id_request).strip():
                    hasil = dict(zip(id_headers, row))
                    break
        except Exception:
            pass

        try:
            hasil_sheet = sheet_obj.worksheet("Hasil Input")
            hasil_values = hasil_sheet.get_all_values()
            hasil_headers = hasil_values[0] if hasil_values else []
            for row in hasil_values[1:]:
                for val in row:
                    if str(val).strip() == str(id_request).strip():
                        hasil.update(dict(zip(hasil_headers, row)))
                        break
        except Exception:
            pass

        try:
            fpk_sheet = sheet_obj.worksheet("Form Permintaan")
            fpk_values = fpk_sheet.get_all_values()
            fpk_headers = fpk_values[0] if fpk_values else []
            for row in fpk_values[1:]:
                if len(row) > 1 and str(row[1]).strip() == str(id_request).strip():
                    hasil.update(dict(zip(fpk_headers, row)))
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
        cv_link = data.get("cv_link", "")  # Link CV dari Google Drive

        # ---- Hasil Input ----
        HEADERS_HASIL = [
            "NO", "Tahun Request", "ID Request", "Tanggal Request FPK",
            "Tanggal Request PTK", "Nama", "Posisi Lamaran", "Penempatan", "Grade",
            "Induk Perusahaan", "Link CV", "No Tlp", "Email", "ID Request Dipilih"
        ]
        hasil_sheet = ensure_sheet(sheet_obj, "Hasil Input", HEADERS_HASIL)
        hasil_sheet.append_row([
            get_next_id(hasil_sheet), tahun, id_request_dipilih, tgl_request,
            data.get("tgl_request_ptk", ""),
            data.get("nama_pelamar", ""),
            data.get("posisi_lamaran", ""),
            data.get("penempatan", ""),
            data.get("grade", ""),
            data.get("induk_perusahaan", ""),
            cv_link,
            data.get("no_tlp", ""),
            data.get("email", ""),
            id_request_dipilih,
        ])

        # ---- Form Permintaan ----
        HEADERS_FPK = [
            "Divisi", "ID Form Permintaan Tenaga Kerja", "FPK Name", "PT Induk",
            "Lokasi Penempatan", "Grade", "Tanggal Request FPK", "Tanggal Approve BOD",
            "Form FPK", "Budget/Non Budget", "Category", "Detail Category",
            "Tahun Request", "Jumlah Hari", "Vacancy Request", "Joined", "CV Process"
        ]
        fpk_sheet = ensure_sheet(sheet_obj, "Form Permintaan", HEADERS_FPK)
        fpk_sheet.append_row([
            data.get("divisi", ""), id_request_dipilih,
            data.get("fpk_name", ""), data.get("induk_perusahaan", ""),
            data.get("penempatan", ""), data.get("grade", ""),
            tgl_request, data.get("tgl_approve_bod", ""),
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
            "Vacancy Request", "Form FPK", "Tanggal Request PTK", "Tanggal Approve BOD",
            "Joined", "CV Process", "Link CV"
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
            cv_link,
        ])

        return jsonify({
            "status": "success",
            "message": f"Data berhasil disimpan! ID Request: {id_request_dipilih}",
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

# ==================== ADMIN ====================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
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
        summary = {}

        for row in rows:
            try:
                id_req = str(row[1]).strip()
                if not id_req:
                    continue
                def get_col(col_name, r=row):
                    try:
                        return str(r[headers.index(col_name)]).strip() if col_name in headers else ""
                    except (ValueError, IndexError):
                        return ""
                if id_req not in summary:
                    summary[id_req] = {"total_cv": 0, "entries": [],
                                       "posisi": get_col("Posisi Lamaran"),
                                       "penempatan": get_col("Penempatan")}
                summary[id_req]["total_cv"] += 1
                summary[id_req]["entries"].append({
                    "nama":       get_col("Nama Pelamar"),
                    "timestamp":  str(row[0]).strip(),
                    "cv_process": get_col("CV Process"),
                    "posisi":     get_col("Posisi Lamaran"),
                    "cv_link":    get_col("Link CV"),
                })
            except Exception:
                continue

        return render_template("admin_dashboard.html", headers=headers, rows=rows, summary=summary)
    except Exception as e:
        return render_template("admin_dashboard.html", rows=[], headers=[], summary={}, error=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", debug=False, port=port)
