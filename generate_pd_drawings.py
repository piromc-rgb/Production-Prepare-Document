import os
import re
import fitz
import pandas as pd

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

def main():
    base_dir = r"g:\My Drive\pdo_prepare_print"
    pdf_source = os.path.join(base_dir, "pd_list", "PD2611023-PD26110963.pdf")
    dwg_root = r"G:\My Drive\staus overview\dwg"
    qc_form_path = os.path.join(base_dir, "att_form", "QC_check_sheet.pdf")
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    print("Reading source PD PDF...")
    src_doc = fitz.open(pdf_source)
    print(f"Total pages in source: {len(src_doc)}")

    # 1. Parse all pages in source PD
    pua_map = {
        0xF700: 0x0E31, 0xF701: 0x0E34, 0xF702: 0x0E35, 0xF703: 0x0E36, 0xF704: 0x0E37,
        0xF705: 0x0E48, 0xF706: 0x0E49, 0xF707: 0x0E4A, 0xF708: 0x0E4B, 0xF709: 0x0E4C,
        0xF70A: 0x0E48, 0xF70B: 0x0E49, 0xF70C: 0x0E4A, 0xF70D: 0x0E4B, 0xF70E: 0x0E4C,
        0xF710: 0x0E38, 0xF711: 0x0E39, 0xF712: 0x0E3A, 0xF713: 0x0E48, 0xF714: 0x0E49,
        0xF715: 0x0E4A, 0xF716: 0x0E4B, 0xF717: 0x0E4C,
    }
    def clean_thai(t):
        return t.translate(pua_map)

    pd_groups = {} # pd_no -> {'pages': [page_idx...], 'item_no': ..., 'item_name': ..., 'qty': ...}
    for p_idx in range(len(src_doc)):
        text = src_doc[p_idx].get_text()
        m_pd = re.search(r'Production Order\s*:\s*(PD\d+)', text)
        m_item = re.search(r'Item\s*:\s*\n([^\n]+)\n([^\n]+)', text)
        m_qty = re.search(r'Quantity Ordered\s*:\s*([\d\.]+)\s*(\w+)?', text)

        pd_no = m_pd.group(1).strip() if m_pd else f"UNKNOWN_P{p_idx+1}"
        item_no = m_item.group(1).strip() if m_item else ""
        item_name = clean_thai(m_item.group(2).strip()) if m_item else ""
        qty_str = m_qty.group(1).strip() if m_qty else ""
        unit = m_qty.group(2).strip() if (m_qty and m_qty.group(2)) else ""

        if pd_no not in pd_groups:
            pd_groups[pd_no] = {
                'pages': [],
                'item_no': item_no,
                'item_name': item_name,
                'qty': qty_str,
                'unit': unit
            }
        pd_groups[pd_no]['pages'].append(p_idx)

    print(f"Identified {len(pd_groups)} unique Production Orders.")

    # 2. Index all drawings
    print(f"Scanning drawings in {dwg_root}...")
    dwg_files = []
    for root, dirs, files in os.walk(dwg_root):
        for f in files:
            if f.lower().endswith('.pdf'):
                dwg_files.append((f, os.path.join(root, f)))

    print(f"Total drawings found: {len(dwg_files)}")

    # 3. Generate merged PDF per PD
    summary = []
    for pd_no, data in pd_groups.items():
        item_no = data['item_no']
        item_name = data['item_name']
        pages = data['pages']
        qty_formatted = format_qty(data['qty'])

        # Find matching drawing
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

        # Build output PDF
        out_doc = fitz.open()

        # Step A: Insert PD order pages
        for p in pages:
            out_doc.insert_pdf(src_doc, from_page=p, to_page=p)

        # Step B: Insert Drawing pages if found
        dwg_pages_added = 0
        if selected_dwg:
            try:
                dwg_doc = fitz.open(selected_dwg[2])
                dwg_pages_added = len(dwg_doc)
                out_doc.insert_pdf(dwg_doc)
                dwg_doc.close()
            except Exception as e:
                print(f"Error reading drawing {selected_dwg[1]}: {e}")

        # Step C: Prepare QC Check Sheet with PD & QTY stamped, then append as LAST page
        qc_doc = fitz.open(qc_form_path)
        qc_page = qc_doc[0]

        # White out dots for PD slot and print PD number
        qc_page.draw_rect(fitz.Rect(132, 69, 204, 81), color=None, fill=(1, 1, 1))
        qc_page.insert_text(fitz.Point(133, 78.5), pd_no, fontsize=8.5, fontname='helv', color=(0, 0, 0))

        # White out dots for QTY slot and print centered QTY
        qc_page.draw_rect(fitz.Rect(415, 69, 454, 81), color=None, fill=(1, 1, 1))
        # Center the QTY text
        text_width = len(qty_formatted) * 5.2
        x_qty = 415 + (454 - 415 - text_width) / 2
        qc_page.insert_text(fitz.Point(max(416, x_qty), 78.5), qty_formatted, fontsize=8.5, fontname='helv', color=(0, 0, 0))

        # Append customized QC page to out_doc
        out_doc.insert_pdf(qc_doc)
        qc_doc.close()

        # Save merged PDF
        out_filename = f"{pd_no}.pdf"
        out_filepath = os.path.join(output_dir, out_filename)
        out_doc.save(out_filepath)
        total_pages = len(out_doc)
        out_doc.close()

        summary.append({
            'production_order': pd_no,
            'item_no': item_no,
            'item_name': item_name,
            'qty': qty_formatted,
            'unit': data['unit'],
            'pd_pages': len(pages),
            'has_drawing': bool(selected_dwg),
            'drawing_file': selected_dwg[1] if selected_dwg else "NOT FOUND",
            'drawing_pages': dwg_pages_added,
            'qc_sheet_attached': True,
            'total_pages': total_pages,
            'output_file': out_filename
        })

    summary_df = pd.DataFrame(summary)
    summary_path = os.path.join(base_dir, "output_generation_summary.xlsx")
    summary_df.to_excel(summary_path, index=False)
    print(f"Finished generating {len(summary)} PDF files in {output_dir}")
    print(f"Summary saved to {summary_path}")

    with_dwg = summary_df[summary_df['has_drawing']]
    without_dwg = summary_df[~summary_df['has_drawing']]
    print(f"PDs with Drawing attached: {len(with_dwg)}")
    print(f"PDs without Drawing: {len(without_dwg)}")

if __name__ == '__main__':
    main()
