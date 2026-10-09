import os
import re
import sys
import json
import shutil
import zipfile
import subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse
import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_LIST_DIR = os.path.join(BASE_DIR, "pdf_list")
PD_LIST_DIR = os.path.join(BASE_DIR, "pd_list")
ATT_FORM_DIR = os.path.join(BASE_DIR, "att_form")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")

DEFAULT_DWG_INPUT = "https://drive.google.com/drive/folders/1M-QDPilC7Nn-YW_5YxLQITUS6ZOYEyFm?usp=drive_link"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'dwg_source': DEFAULT_DWG_INPUT}

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

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

def get_active_pd_pdf():
    for d in [PDF_LIST_DIR, PD_LIST_DIR]:
        if os.path.exists(d):
            pdfs = [f for f in os.listdir(d) if f.lower().endswith('.pdf')]
            if pdfs:
                return os.path.join(d, sorted(pdfs)[-1])
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

        if path == "/api/preview":
            cfg = load_config()
            dwg_source = cfg.get('dwg_source', DEFAULT_DWG_INPUT)
            resolved_dwg_path = resolve_dwg_dir(dwg_source)

            active_pdf = get_active_pd_pdf()
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
                    out_exists = os.path.exists(os.path.join(OUTPUT_DIR, out_file))

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

            output_files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith('.pdf')] if os.path.exists(OUTPUT_DIR) else []

            self.send_json({
                'dwg_source': dwg_source,
                'resolved_dwg_path': resolved_dwg_path,
                'dwg_files_count': len(dwg_files),
                'active_file': os.path.basename(active_pdf) if active_pdf else None,
                'total_pds': len(items_list),
                'matched_dwg': matched_count,
                'missing_dwg': missing_count,
                'items': items_list,
                'output_files_count': len(output_files)
            })
            return

        if path.startswith("/output/"):
            filename = urllib.parse.unquote(path[8:])
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
            zip_path = os.path.join(BASE_DIR, "PD_OUTPUTS_ALL.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in os.listdir(OUTPUT_DIR):
                    if f.lower().endswith('.pdf'):
                        zipf.write(os.path.join(OUTPUT_DIR, f), arcname=f)
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

            del_input = 0
            del_output = 0

            # 1. Clear input files
            if target in ['input', 'all']:
                for d in [PDF_LIST_DIR, PD_LIST_DIR]:
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
                if os.path.exists(OUTPUT_DIR):
                    for f in os.listdir(OUTPUT_DIR):
                        if f != '.gitkeep':
                            p = os.path.join(OUTPUT_DIR, f)
                            try:
                                if os.path.isfile(p):
                                    os.remove(p)
                                    del_output += 1
                                elif os.path.isdir(p):
                                    shutil.rmtree(p)
                            except Exception as e:
                                print(f"Error removing {p}: {e}")
                # Also delete zip archive if present
                zip_path = os.path.join(BASE_DIR, "PD_OUTPUTS_ALL.zip")
                if os.path.exists(zip_path):
                    try:
                        os.remove(zip_path)
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
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            cfg = load_config()
            if 'dwg_source' in payload:
                cfg['dwg_source'] = payload['dwg_source'].strip()
                save_config(cfg)
            self.send_json({'success': True, 'config': cfg})
            return

        if path == "/api/open-folder":
            try:
                if sys.platform == 'win32':
                    os.startfile(OUTPUT_DIR)
                self.send_json({'success': True})
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
                            target_path = os.path.join(PDF_LIST_DIR, clean_fname)
                            with open(target_path, 'wb') as f_out:
                                f_out.write(body)
                            shutil.copy2(target_path, os.path.join(PD_LIST_DIR, clean_fname))
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

            cfg = load_config()
            dwg_source = cfg.get('dwg_source', DEFAULT_DWG_INPUT)
            resolved_dwg_path = resolve_dwg_dir(dwg_source)

            active_pdf = get_active_pd_pdf()
            if not active_pdf or not os.path.exists(active_pdf):
                self.send_json({'success': False, 'error': 'No active Production Order PDF found'}, status=400)
                return

            qc_form_path = os.path.join(ATT_FORM_DIR, "QC_check_sheet.pdf")
            if not os.path.exists(qc_form_path):
                self.send_json({'success': False, 'error': 'QC_check_sheet.pdf not found in att_form'}, status=400)
                return

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
                    out_path = os.path.join(OUTPUT_DIR, f"{pd_no}.pdf")
                    single_doc.save(out_path)
                    files_created_count += 1

                if combined_doc is not None:
                    combined_doc.insert_pdf(single_doc)

                single_doc.close()

            src_doc.close()

            if combined_doc is not None:
                combined_path = os.path.join(OUTPUT_DIR, "ALL_PD_COMBINED.pdf")
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
