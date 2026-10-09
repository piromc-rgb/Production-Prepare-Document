import os
import re
import sys
import json
import shutil
import zipfile
import subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse

# กำหนด stdout ให้ปลอดภัยต่อ Windows CP874
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ตรวจสอบแพ็กเกจที่จำเป็น หากยังไม่ได้ติดตั้งให้ติดตั้งให้อัตโนมัติ
REQUIRED_PACKAGES = {
    'fitz': 'pymupdf>=1.23.0',
    'pandas': 'pandas>=2.0.0',
    'openpyxl': 'openpyxl>=3.1.0'
}

def check_and_install_dependencies():
    missing = []
    for mod_name, pip_spec in REQUIRED_PACKAGES.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_spec)
    
    if missing:
        print("==================================================")
        print(" [!] ตรวจพบสิ่งที่ต้องใช้ยังไม่ได้ติดตั้ง:")
        for pkg in missing:
            print(f"     - {pkg}")
        print(" [*] กำลังดำเนินการติดตั้งให้อัตโนมัติ (Installing dependencies)...")
        print("==================================================")
        try:
            cmd = [sys.executable, "-m", "pip", "install", *missing]
            subprocess.check_call(cmd)
            print(" [OK] ติดตั้งแพ็กเกจที่จำเป็นสำเร็จเรียบร้อยแล้ว!")
        except Exception as e:
            print(f" [ERROR] เกิดข้อผิดพลาดในการติดตั้งแพ็กเกจ: {e}")
            print(" กรุณาติดตั้งด้วยตนเอง: pip install -r requirements.txt")
            sys.exit(1)
    else:
        print(" [OK] ตรวจสอบ Dependencies: ติดตั้งครบถ้วนพร้อมใช้งาน (PyMuPDF, pandas, openpyxl)")

check_and_install_dependencies()

import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_LIST_DIR = os.path.join(BASE_DIR, "pdf_list")
PD_LIST_DIR = os.path.join(BASE_DIR, "pd_list")
ATT_FORM_DIR = os.path.join(BASE_DIR, "att_form")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")

DEFAULT_DWG_INPUT = "https://drive.google.com/drive/folders/1M-QDPilC7Nn-YW_5YxLQITUS6ZOYEyFm?usp=drive_link"
DEFAULT_CONFIG = {
    'dwg_source': DEFAULT_DWG_INPUT,
    'pd_dir': 'pdf_list',
    'att_dir': 'att_form',
    'output_dir': 'output'
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def resolve_dir_path(path_str, default_subfolder):
    if not path_str or not str(path_str).strip():
        p = os.path.join(BASE_DIR, default_subfolder)
    else:
        path_str = str(path_str).strip()
        if os.path.isabs(path_str):
            p = path_str
        else:
            p = os.path.join(BASE_DIR, path_str)
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return os.path.normpath(p)

def resolve_dwg_dir(path_or_url):
    m = re.search(r'/folders/([a-zA-Z0-9_-]+)', path_or_url)
    if m:
        folder_id = m.group(1)
        shortcut_path = os.path.join(r"G:\.shortcut-targets-by-id", folder_id)
        if os.path.exists(shortcut_path):
            return shortcut_path
    if os.path.exists(path_or_url):
        return path_or_url
    fallback = r"G:\My Drive\staus overview\dwg"
    if os.path.exists(fallback):
        return fallback
    return path_or_url

def get_current_paths():
    cfg = load_config()
    dwg_source = cfg.get('dwg_source', DEFAULT_DWG_INPUT)
    pd_dir = resolve_dir_path(cfg.get('pd_dir', 'pdf_list'), 'pdf_list')
    att_dir = resolve_dir_path(cfg.get('att_dir', 'att_form'), 'att_form')
    output_dir = resolve_dir_path(cfg.get('output_dir', 'output'), 'output')
    resolved_dwg = resolve_dwg_dir(dwg_source)
    return {
        'dwg_source': dwg_source,
        'resolved_dwg_dir': resolved_dwg,
        'pd_dir_raw': cfg.get('pd_dir', 'pdf_list'),
        'pd_dir': pd_dir,
        'att_dir_raw': cfg.get('att_dir', 'att_form'),
        'att_dir': att_dir,
        'output_dir_raw': cfg.get('output_dir', 'output'),
        'output_dir': output_dir,
    }

os.makedirs(PDF_LIST_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ATT_FORM_DIR, exist_ok=True)

PUA_MAP = {
    0xF700: 0x0E31, 0xF701: 0x0E34, 0xF702: 0x0E35, 0xF703: 0x0E36, 0xF704: 0x0E37,
    0xF705: 0x0E48, 0xF706: 0x0E49, 0xF707: 0x0E4A, 0xF708: 0x0E4B, 0xF709: 0x0E4C,
    0xF70A: 0x0E48, 0xF70B: 0x0E49, 0xF70C: 0x0E4A, 0xF70D: 0x0E4B, 0xF70E: 0x0E4C,
    0xF710: 0x0E38, 0xF711: 0x0E39, 0xF712: 0x0E3A, 0xF713: 0x0E48, 0xF714: 0x0E49,
    0xF715: 0x0E4A, 0xF716: 0x0E4B, 0xF717: 0x0E4C,
}

def clean_thai(t):
    return t.translate(PUA_MAP)

def clean_code(s):
    return re.sub(r'[^A-Za-z0-9]', '', s).upper()

def extract_rev(filename):
    m = re.search(r'Rev\.?(\d+)', filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0

def format_qty(qty_str):
    try:
        val = float(qty_str)
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}"
    except Exception:
        return str(qty_str)

def get_dwg_files(resolved_dwg_path):
    dwg_files = []
    if os.path.exists(resolved_dwg_path):
        for root, dirs, files in os.walk(resolved_dwg_path):
            for f in files:
                if f.lower().endswith('.pdf'):
                    dwg_files.append((f, os.path.join(root, f)))
    return dwg_files

def get_active_pd_pdf(custom_pd_dir=None):
    dirs_to_check = []
    if custom_pd_dir and os.path.exists(custom_pd_dir):
        dirs_to_check.append(custom_pd_dir)
    for d in [PDF_LIST_DIR, PD_LIST_DIR]:
        if d not in dirs_to_check and os.path.exists(d):
            dirs_to_check.append(d)
    for d in dirs_to_check:
        try:
            pdfs = [f for f in os.listdir(d) if f.lower().endswith('.pdf')]
            if pdfs:
                return os.path.join(d, sorted(pdfs)[-1])
        except Exception:
            continue
    return None

def parse_pd_pdf(pdf_path):
    if not pdf_path or not os.path.exists(pdf_path):
        return {}
    src_doc = fitz.open(pdf_path)
    pd_groups = {}
    for p_idx in range(len(src_doc)):
        text = src_doc[p_idx].get_text()
        m_pd = re.search(r'Production Order\s*:\s*(PD\d+)', text)
        m_item = re.search(r'Item\s*:\s*\n([^\n]+)\n([^\n]+)', text)
        m_qty = re.search(r'Quantity Ordered\s*:\s*([\d\.]+)\s*(\w+)?', text)

        pd_no = m_pd.group(1).strip() if m_pd else f"PAGE_{p_idx+1}"
        item_no = m_item.group(1).strip() if m_item else ""
        item_name = clean_thai(m_item.group(2).strip()) if m_item else ""
        qty_str = m_qty.group(1).strip() if m_qty else "1"
        unit = m_qty.group(2).strip() if (m_qty and m_qty.group(2)) else "PCS"

        if pd_no not in pd_groups:
            pd_groups[pd_no] = {
                'pages': [],
                'item_no': item_no,
                'item_name': item_name,
                'qty': qty_str,
                'unit': unit
            }
        pd_groups[pd_no]['pages'].append(p_idx)
    src_doc.close()
    return pd_groups

def get_html_bytes():
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, 'rb') as f:
            return f.read()
    return b"<h1>index.html not found</h1>"

class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            body = get_html_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/settings":
            paths = get_current_paths()
            dwg_files = get_dwg_files(paths['resolved_dwg_dir'])
            pd_files = [f for f in os.listdir(paths['pd_dir']) if f.lower().endswith('.pdf')] if os.path.exists(paths['pd_dir']) else []
            att_files = [f for f in os.listdir(paths['att_dir']) if f.lower().endswith('.pdf')] if os.path.exists(paths['att_dir']) else []
            output_files = [f for f in os.listdir(paths['output_dir']) if f.lower().endswith('.pdf')] if os.path.exists(paths['output_dir']) else []

            self.send_json({
                'success': True,
                'config': {
                    'dwg_source': paths['dwg_source'],
                    'pd_dir': paths['pd_dir_raw'],
                    'att_dir': paths['att_dir_raw'],
                    'output_dir': paths['output_dir_raw']
                },
                'resolved': {
                    'dwg': paths['resolved_dwg_dir'],
                    'dwg_exists': os.path.exists(paths['resolved_dwg_dir']),
                    'dwg_count': len(dwg_files),
                    'pd': paths['pd_dir'],
                    'pd_exists': os.path.exists(paths['pd_dir']),
                    'pd_count': len(pd_files),
                    'att': paths['att_dir'],
                    'att_exists': os.path.exists(paths['att_dir']),
                    'att_count': len(att_files),
                    'output': paths['output_dir'],
                    'output_exists': os.path.exists(paths['output_dir']),
                    'output_count': len(output_files)
                }
            })
            return

        if path == "/api/preview":
            paths = get_current_paths()
            dwg_source = paths['dwg_source']
            resolved_dwg_path = paths['resolved_dwg_dir']
            pd_dir = paths['pd_dir']
            output_dir = paths['output_dir']

            active_pdf = get_active_pd_pdf(pd_dir)
            items_list = []
            matched_count = 0
            missing_count = 0

            dwg_files = get_dwg_files(resolved_dwg_path)

            if active_pdf and os.path.exists(active_pdf):
                pd_groups = parse_pd_pdf(active_pdf)

                for pd_no, data in pd_groups.items():
                    item_no = data['item_no']
                    item_name = data['item_name']
                    qty_fmt = format_qty(data['qty'])

                    matched_dwgs = []
                    clean_target = clean_code(item_no)
                    for fname, fpath in dwg_files:
                        clean_f = clean_code(os.path.splitext(fname)[0])
                        if clean_target in clean_f:
                            rev = extract_rev(fname)
                            matched_dwgs.append((rev, fname))

                    has_dwg = len(matched_dwgs) > 0
                    if has_dwg:
                        matched_dwgs.sort(key=lambda x: x[0], reverse=True)
                        dwg_name = matched_dwgs[0][1]
                        matched_count += 1
                    else:
                        dwg_name = ""
                        missing_count += 1

                    out_file = f"{pd_no}.pdf"
                    out_exists = os.path.exists(os.path.join(output_dir, out_file))

                    items_list.append({
                        'pd_no': pd_no,
                        'item_no': item_no,
                        'item_name': item_name,
                        'qty': qty_fmt,
                        'unit': data['unit'],
                        'has_drawing': has_dwg,
                        'drawing_file': dwg_name,
                        'output_file': out_file,
                        'output_exists': out_exists
                    })

            output_files = [f for f in os.listdir(output_dir) if f.lower().endswith('.pdf')] if os.path.exists(output_dir) else []

            self.send_json({
                'dwg_source': dwg_source,
                'resolved_dwg_path': resolved_dwg_path,
                'dwg_files_count': len(dwg_files),
                'active_file': os.path.basename(active_pdf) if active_pdf else None,
                'total_pds': len(items_list),
                'matched_dwg': matched_count,
                'missing_dwg': missing_count,
                'items': items_list,
                'output_files_count': len(output_files),
                'locations': {
                    'dwg_source': dwg_source,
                    'resolved_dwg': resolved_dwg_path,
                    'pd_dir': paths['pd_dir_raw'],
                    'resolved_pd': pd_dir,
                    'att_dir': paths['att_dir_raw'],
                    'resolved_att': paths['att_dir'],
                    'output_dir': paths['output_dir_raw'],
                    'resolved_output': output_dir,
                }
            })
            return

        if path.startswith("/output/"):
            paths = get_current_paths()
            filename = urllib.parse.unquote(path[8:])
            filepath = os.path.join(paths['output_dir'], filename)
            if not os.path.exists(filepath):
                filepath = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', f'inline; filename="{filename}"')
                self.send_header('Content-Length', str(os.path.getsize(filepath)))
                self.end_headers()
                with open(filepath, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            else:
                self.send_error(404, "File not found")
                return

        if path == "/api/download-zip":
            paths = get_current_paths()
            out_dir = paths['output_dir']
            zip_path = os.path.join(BASE_DIR, "PD_OUTPUTS_ALL.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists(out_dir):
                    for f in os.listdir(out_dir):
                        if f.lower().endswith('.pdf'):
                            zipf.write(os.path.join(out_dir, f), arcname=f)
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="PD_OUTPUTS_ALL.zip"')
            self.send_header('Content-Length', str(os.path.getsize(zip_path)))
            self.end_headers()
            with open(zip_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/clear":
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}
            target = payload.get('target', 'all') # 'input', 'output', 'all'
            paths = get_current_paths()

            del_input = 0
            del_output = 0

            # 1. Clear input files
            if target in ['input', 'all']:
                input_dirs = set([paths['pd_dir'], PDF_LIST_DIR, PD_LIST_DIR])
                for d in input_dirs:
                    if os.path.exists(d):
                        for f in os.listdir(d):
                            if f != '.gitkeep':
                                p = os.path.join(d, f)
                                try:
                                    if os.path.isfile(p):
                                        os.remove(p)
                                        del_input += 1
                                    elif os.path.isdir(p):
                                        shutil.rmtree(p)
                                except Exception as e:
                                    print(f"Error removing {p}: {e}")

            # 2. Clear output files
            if target in ['output', 'all']:
                output_dirs = set([paths['output_dir'], OUTPUT_DIR])
                for d in output_dirs:
                    if os.path.exists(d):
                        for f in os.listdir(d):
                            if f != '.gitkeep':
                                p = os.path.join(d, f)
                                try:
                                    if os.path.isfile(p):
                                        os.remove(p)
                                        del_output += 1
                                    elif os.path.isdir(p):
                                        shutil.rmtree(p)
                                except Exception as e:
                                    print(f"Error removing {p}: {e}")

                # Also delete zip archive if present
                for zp in [os.path.join(BASE_DIR, "PD_OUTPUTS_ALL.zip"), os.path.join(paths['output_dir'], "PD_OUTPUTS_ALL.zip")]:
                    if os.path.exists(zp):
                        try:
                            os.remove(zp)
                        except Exception:
                            pass

            self.send_json({
                'success': True,
                'target': target,
                'deleted_input': del_input,
                'deleted_output': del_output
            })
            return

        if path == "/api/settings":
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}
            cfg = load_config()
            for key in ['dwg_source', 'pd_dir', 'att_dir', 'output_dir']:
                if key in payload and payload[key] is not None:
                    cfg[key] = str(payload[key]).strip()
            save_config(cfg)
            paths = get_current_paths()
            self.send_json({
                'success': True,
                'config': cfg,
                'resolved': {
                    'dwg': paths['resolved_dwg_dir'],
                    'pd': paths['pd_dir'],
                    'att': paths['att_dir'],
                    'output': paths['output_dir']
                }
            })
            return

        if path == "/api/open-folder":
            try:
                length = int(self.headers.get('Content-Length', 0))
                payload = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}
                target = payload.get('target', 'output')
                paths = get_current_paths()

                target_dir = paths.get('output_dir')
                if target in ['pd', 'input']:
                    target_dir = paths.get('pd_dir')
                elif target == 'att':
                    target_dir = paths.get('att_dir')
                elif target == 'dwg':
                    target_dir = paths.get('resolved_dwg_dir')
                elif target == 'output':
                    target_dir = paths.get('output_dir')
                elif os.path.exists(target):
                    target_dir = target

                if target_dir and os.path.exists(target_dir):
                    if sys.platform == 'win32':
                        os.startfile(target_dir)
                    self.send_json({'success': True, 'path': target_dir})
                else:
                    self.send_json({'success': False, 'error': f'โฟลเดอร์ {target_dir} ไม่พบในระบบ'}, status=400)
            except Exception as e:
                self.send_json({'success': False, 'error': str(e)})
            return

        if path == "/api/upload":
            content_type = self.headers.get('Content-Type', '')
            if 'boundary=' not in content_type:
                self.send_json({'success': False, 'error': 'Invalid content type'}, status=400)
                return

            boundary = content_type.split('boundary=')[1].strip()
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            boundary_bytes = boundary.encode('latin1')
            parts = post_data.split(b'--' + boundary_bytes)

            paths = get_current_paths()
            upload_target_dir = paths['pd_dir']
            os.makedirs(upload_target_dir, exist_ok=True)

            saved_filename = None
            for p in parts:
                if b'filename="' in p:
                    head, body = p.split(b'\r\n\r\n', 1)
                    body = body.rstrip(b'\r\n--')
                    fname_m = re.search(rb'filename="([^"]+)"', head)
                    if fname_m:
                        orig_fname = fname_m.group(1).decode('utf-8', errors='ignore')
                        clean_fname = os.path.basename(orig_fname)
                        if clean_fname.lower().endswith('.pdf'):
                            target_path = os.path.join(upload_target_dir, clean_fname)
                            with open(target_path, 'wb') as f_out:
                                f_out.write(body)
                            if os.path.normpath(upload_target_dir) != os.path.normpath(PDF_LIST_DIR):
                                try:
                                    shutil.copy2(target_path, os.path.join(PDF_LIST_DIR, clean_fname))
                                except Exception:
                                    pass
                            try:
                                shutil.copy2(target_path, os.path.join(PD_LIST_DIR, clean_fname))
                            except Exception:
                                pass
                            saved_filename = clean_fname

            if saved_filename:
                self.send_json({'success': True, 'filename': saved_filename})
            else:
                self.send_json({'success': False, 'error': 'No PDF file saved'}, status=400)
            return

        if path == "/api/process":
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            order = payload.get('order', ['pd', 'dwg', 'qc'])
            mode = payload.get('mode', 'split')

            paths = get_current_paths()
            dwg_source = paths['dwg_source']
            resolved_dwg_path = paths['resolved_dwg_dir']
            pd_dir = paths['pd_dir']
            att_dir = paths['att_dir']
            output_dir = paths['output_dir']

            active_pdf = get_active_pd_pdf(pd_dir)
            if not active_pdf or not os.path.exists(active_pdf):
                self.send_json({'success': False, 'error': 'No active Production Order PDF found'}, status=400)
                return

            qc_form_path = os.path.join(att_dir, "QC_check_sheet.pdf")
            if not os.path.exists(qc_form_path):
                if os.path.exists(att_dir):
                    pdfs = [f for f in os.listdir(att_dir) if f.lower().endswith('.pdf')]
                    if pdfs:
                        qc_form_path = os.path.join(att_dir, pdfs[0])
            if not os.path.exists(qc_form_path):
                qc_form_path = os.path.join(ATT_FORM_DIR, "QC_check_sheet.pdf")

            if not os.path.exists(qc_form_path):
                self.send_json({'success': False, 'error': f'QC_check_sheet.pdf not found in {att_dir}'}, status=400)
                return

            os.makedirs(output_dir, exist_ok=True)

            pd_groups = parse_pd_pdf(active_pdf)
            src_doc = fitz.open(active_pdf)
            dwg_files = get_dwg_files(resolved_dwg_path)

            files_created_count = 0
            combined_doc = fitz.open() if mode in ['merge', 'both'] else None

            for pd_no, data in pd_groups.items():
                item_no = data['item_no']
                qty_formatted = format_qty(data['qty'])

                matched_dwgs = []
                clean_target = clean_code(item_no)
                for fname, fpath in dwg_files:
                    clean_f = clean_code(os.path.splitext(fname)[0])
                    if clean_target in clean_f:
                        rev = extract_rev(fname)
                        matched_dwgs.append((rev, fname, fpath))

                selected_dwg = None
                if matched_dwgs:
                    matched_dwgs.sort(key=lambda x: x[0], reverse=True)
                    selected_dwg = matched_dwgs[0]

                single_doc = fitz.open()

                for source_key in order:
                    if source_key == 'pd':
                        for p in data['pages']:
                            single_doc.insert_pdf(src_doc, from_page=p, to_page=p)
                    elif source_key == 'dwg':
                        if selected_dwg:
                            try:
                                d_doc = fitz.open(selected_dwg[2])
                                single_doc.insert_pdf(d_doc)
                                d_doc.close()
                            except Exception as e:
                                print(f"Error reading dwg: {e}")
                    elif source_key == 'qc':
                        qc_doc = fitz.open(qc_form_path)
                        qc_page = qc_doc[0]
                        qc_page.draw_rect(fitz.Rect(132, 69, 204, 81), color=None, fill=(1, 1, 1))
                        qc_page.insert_text(fitz.Point(133, 78.5), pd_no, fontsize=8.5, fontname='helv', color=(0, 0, 0))

                        qc_page.draw_rect(fitz.Rect(415, 69, 454, 81), color=None, fill=(1, 1, 1))
                        text_width = len(qty_formatted) * 5.2
                        x_qty = 415 + (454 - 415 - text_width) / 2
                        qc_page.insert_text(fitz.Point(max(416, x_qty), 78.5), qty_formatted, fontsize=8.5, fontname='helv', color=(0, 0, 0))
                        single_doc.insert_pdf(qc_doc)
                        qc_doc.close()

                if mode in ['split', 'both']:
                    out_path = os.path.join(output_dir, f"{pd_no}.pdf")
                    single_doc.save(out_path)
                    files_created_count += 1

                if combined_doc is not None:
                    combined_doc.insert_pdf(single_doc)

                single_doc.close()

            src_doc.close()

            if combined_doc is not None:
                combined_path = os.path.join(output_dir, "ALL_PD_COMBINED.pdf")
                combined_doc.save(combined_path)
                combined_doc.close()
                files_created_count += 1

            self.send_json({
                'success': True,
                'files_created': files_created_count,
                'total_pds': len(pd_groups)
            })
            return

        self.send_error(404, "Not Found")

def run(port=8088):
    server = ThreadingHTTPServer(('0.0.0.0', port), AppHandler)
    print(f"==================================================")
    print(f" Web App started successfully on port {port}!")
    print(f" URL: http://localhost:{port}")
    print(f"==================================================")
    server.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    run(port)
