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
DWG_DIR = r"G:\My Drive\staus overview\dwg"

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

def get_dwg_files():
    dwg_files = []
    if os.path.exists(DWG_DIR):
        for root, dirs, files in os.walk(DWG_DIR):
            for f in files:
                if f.lower().endswith('.pdf'):
                    dwg_files.append((f, os.path.join(root, f)))
    return dwg_files

def get_active_pd_pdf():
    # Check pdf_list first, then pd_list
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

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ระบบจัดชุดเอกสารเตรียมผลิต (Production Order & Drawing)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Sarabun', sans-serif; background-color: #f1f5f9; }
    .drag-item { cursor: grab; user-select: none; }
    .drag-item:active { cursor: grabbing; }
  </style>
</head>
<body class="text-slate-800 antialiased min-h-screen">

  <!-- Navbar -->
  <header class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-lg sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-400 shadow-inner">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            ระบบจัดชุดเอกสารสำหรับเตรียมผลิต
            <span class="text-xs bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 px-2 py-0.5 rounded-full font-normal">v2.0</span>
          </h1>
          <p class="text-xs text-slate-400">Automated Production Order, Drawing & QC Checklist Bundler</p>
        </div>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <button onclick="refreshStatus()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          รีเฟรชข้อมูล
        </button>
        <button onclick="openOutputFolder()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition font-medium flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
          เปิดโฟลเดอร์ Output
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

    <!-- Top Grid: Upload & Sources Config -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      <!-- Card 1: Upload Production Order (4 cols) -->
      <div class="lg:col-span-4 bg-white rounded-2xl shadow-sm border border-slate-200 p-5 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs">1</span>
              อัปโหลดไฟล์ Production Order
            </h2>
            <span class="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">เก็บที่ pdf_list</span>
          </div>
          <p class="text-xs text-slate-500 mb-4">รองรับไฟล์ PDF รวมที่มีหลายใบสั่งผลิต หรือไฟล์เดี่ยว</p>

          <!-- Drop zone -->
          <div id="dropZone" class="border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-xl p-5 text-center transition bg-slate-50/50 hover:bg-indigo-50/30 cursor-pointer">
            <input type="file" id="fileInput" accept=".pdf" class="hidden" onchange="handleFileSelect(this.files)">
            <div class="space-y-2">
              <div class="w-10 h-10 mx-auto rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
              </div>
              <p class="text-xs font-semibold text-slate-700">คลิกเลือกไฟล์ หรือลากไฟล์มาวางที่นี่</p>
              <p class="text-[11px] text-slate-400">เฉพาะไฟล์ .pdf</p>
            </div>
          </div>
          <div id="uploadProgress" class="hidden mt-3">
            <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div id="progressBar" class="bg-indigo-600 h-2 rounded-full w-0 transition-all"></div>
            </div>
            <p id="uploadText" class="text-[11px] text-slate-500 mt-1 text-center">กำลังอัปโหลด...</p>
          </div>
        </div>

        <!-- Active file info -->
        <div id="activeFileInfo" class="mt-4 pt-3 border-t border-slate-100">
          <div class="flex items-center justify-between text-xs">
            <span class="text-slate-500">ไฟล์ปัจจุบันในระบบ:</span>
            <span id="activeFileName" class="font-semibold text-slate-800 truncate max-w-[180px]">-</span>
          </div>
          <div class="flex items-center justify-between text-xs mt-1">
            <span class="text-slate-500">จำนวนใบสั่งผลิต (PD):</span>
            <span id="activeFileCount" class="font-bold text-indigo-600">0 ใบ</span>
          </div>
        </div>
      </div>

      <!-- Card 2: 3 Sources Sequence Arranger (4 cols) -->
      <div class="lg:col-span-4 bg-white rounded-2xl shadow-sm border border-slate-200 p-5 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs">2</span>
              จัดเรียงลำดับเอกสารทั้ง 3 แหล่ง
            </h2>
            <span class="text-[11px] text-slate-400">เลื่อนขึ้น/ลงได้</span>
          </div>
          <p class="text-xs text-slate-500 mb-4">กำหนดว่าหน้าเอกสารส่วนใดจะอยู่ลำดับก่อน-หลัง ในแต่ละชุด</p>

          <!-- 3 Sources List -->
          <div id="sourcesList" class="space-y-2.5">
            <!-- Source Item 1 -->
            <div class="source-card bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between hover:border-indigo-300 transition" data-id="pd">
              <div class="flex items-center gap-3">
                <div class="order-badge w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">1</div>
                <div>
                  <h3 class="text-xs font-bold text-slate-800">📄 ใบสั่งผลิต (Production Order)</h3>
                  <p class="text-[11px] text-slate-500">จากโฟลเดอร์ pdf_list</p>
                </div>
              </div>
              <div class="flex gap-1">
                <button onclick="moveSource('pd', -1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนขึ้น">▲</button>
                <button onclick="moveSource('pd', 1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนลง">▼</button>
              </div>
            </div>

            <!-- Source Item 2 -->
            <div class="source-card bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between hover:border-indigo-300 transition" data-id="dwg">
              <div class="flex items-center gap-3">
                <div class="order-badge w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">2</div>
                <div>
                  <h3 class="text-xs font-bold text-slate-800">📐 แบบ Drawing (Drawing PDF)</h3>
                  <p class="text-[11px] text-slate-500">จับคู่ตามรหัส Item No (ตัด - ออก)</p>
                </div>
              </div>
              <div class="flex gap-1">
                <button onclick="moveSource('dwg', -1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนขึ้น">▲</button>
                <button onclick="moveSource('dwg', 1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนลง">▼</button>
              </div>
            </div>

            <!-- Source Item 3 -->
            <div class="source-card bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between hover:border-indigo-300 transition" data-id="qc">
              <div class="flex items-center gap-3">
                <div class="order-badge w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">3</div>
                <div>
                  <h3 class="text-xs font-bold text-slate-800">📋 ใบตรวจสอบคุณภาพ (QC Check Sheet)</h3>
                  <p class="text-[11px] text-slate-500">พิมพ์เลขที่ PD และ QTY ลงในช่อง</p>
                </div>
              </div>
              <div class="flex gap-1">
                <button onclick="moveSource('qc', -1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนขึ้น">▲</button>
                <button onclick="moveSource('qc', 1)" class="p-1 hover:bg-slate-200 rounded text-slate-600" title="เลื่อนลง">▼</button>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
          ลำดับปัจจุบัน: <span id="currentSequenceText" class="font-semibold text-slate-800">ใบสั่งผลิต ➔ แบบ Drawing ➔ QC Check Sheet</span>
        </div>
      </div>

      <!-- Card 3: Output Options & Action (4 cols) -->
      <div class="lg:col-span-4 bg-white rounded-2xl shadow-sm border border-slate-200 p-5 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs">3</span>
              ตัวเลือกการสร้างไฟล์ Output
            </h2>
          </div>
          <p class="text-xs text-slate-500 mb-4">เลือกรูปแบบผลลัพธ์ที่ต้องการบันทึกในโฟลเดอร์ output</p>

          <div class="space-y-3">
            <label class="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-indigo-400 bg-slate-50/50 cursor-pointer transition">
              <input type="radio" name="outputMode" value="split" class="mt-0.5 text-indigo-600 focus:ring-indigo-500" checked>
              <div>
                <span class="text-xs font-bold text-slate-800 block">🗂️ แยกไฟล์ตาม Production Order (รายใบ)</span>
                <span class="text-[11px] text-slate-500">สร้างแยกเป็น PD2611023.pdf, PD2611024.pdf ...</span>
              </div>
            </label>

            <label class="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-indigo-400 bg-slate-50/50 cursor-pointer transition">
              <input type="radio" name="outputMode" value="merge" class="mt-0.5 text-indigo-600 focus:ring-indigo-500">
              <div>
                <span class="text-xs font-bold text-slate-800 block">📑 รวมเป็นไฟล์เดียว (Single Merged PDF)</span>
                <span class="text-[11px] text-slate-500">รวมทุก PD เข้าเป็นไฟล์ ALL_PD_COMBINED.pdf สำหรับส่งพิมพ์ทีเดียว</span>
              </div>
            </label>

            <label class="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-indigo-400 bg-slate-50/50 cursor-pointer transition">
              <input type="radio" name="outputMode" value="both" class="mt-0.5 text-indigo-600 focus:ring-indigo-500">
              <div>
                <span class="text-xs font-bold text-slate-800 block">📦 สร้างทั้งสองแบบ (แยกรายใบ + ไฟล์รวมทั้งหมด)</span>
                <span class="text-[11px] text-slate-500">ได้ทั้งไฟล์เดี่ยวราย PD และไฟล์รวมพิมพ์ชุดใหญ่</span>
              </div>
            </label>
          </div>
        </div>

        <!-- Big Process Button -->
        <div class="mt-6 pt-4 border-t border-slate-100">
          <button id="btnProcess" onclick="startProcessing()" class="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold rounded-xl shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 transform active:scale-[0.99]">
            <svg class="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
            <span>จัดชุดเอกสารสำหรับเตรียมผลิต</span>
          </button>
        </div>
      </div>

    </div>

    <!-- Processing Status Banner -->
    <div id="processingBanner" class="hidden bg-indigo-50 border border-indigo-200 rounded-2xl p-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <svg class="animate-spin h-5 w-5 text-indigo-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <div>
          <h4 class="text-xs font-bold text-indigo-900">กำลังจัดชุดเอกสารเตรียมผลิต...</h4>
          <p id="processingDetail" class="text-[11px] text-indigo-700">กำลังจับคู่ Drawing และใส่ข้อมูลใบ QC...</p>
        </div>
      </div>
      <div class="w-32 bg-indigo-200 rounded-full h-2 overflow-hidden">
        <div id="processBarInner" class="bg-indigo-600 h-2 rounded-full w-1/3 animate-pulse"></div>
      </div>
    </div>

    <!-- Stats & Outputs Section -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <h3 class="text-base font-bold text-slate-900">รายการใบสั่งผลิตและการจับคู่แบบ (PD Preview & Status)</h3>
          <p class="text-xs text-slate-500">ตรวจสอบสถานะการค้นหาแบบ Drawing และผลการสร้างไฟล์ล่าสุด</p>
        </div>
        <div class="flex items-center gap-3">
          <span id="statTotal" class="px-3 py-1 bg-slate-100 text-slate-700 rounded-full text-xs font-semibold">ทั้งหมด: 0 รายการ</span>
          <span id="statMatched" class="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-semibold">พบ Drawing: 0</span>
          <span id="statMissing" class="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-semibold">รอ Drawing: 0</span>
          <a id="btnZip" href="/api/download-zip" class="hidden px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-medium transition flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
            ดาวน์โหลด ZIP ทั้งหมด
          </a>
        </div>
      </div>

      <!-- Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="bg-slate-50/75 text-slate-600 border-b border-slate-200">
              <th class="py-2.5 px-3 font-semibold w-12 text-center">#</th>
              <th class="py-2.5 px-3 font-semibold">Production Order</th>
              <th class="py-2.5 px-3 font-semibold">Item No</th>
              <th class="py-2.5 px-3 font-semibold">ชิ้นงาน (Item Name)</th>
              <th class="py-2.5 px-3 font-semibold text-center">จำนวน (QTY)</th>
              <th class="py-2.5 px-3 font-semibold">สถานะ Drawing</th>
              <th class="py-2.5 px-3 font-semibold text-center">ไฟล์ Output</th>
            </tr>
          </thead>
          <tbody id="tableBody" class="divide-y divide-slate-100">
            <tr>
              <td colspan="7" class="py-8 text-center text-slate-400">กำลังโหลดข้อมูล...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </main>

  <script>
    let currentOrder = ['pd', 'dwg', 'qc'];
    const sourceNames = {
      'pd': 'ใบสั่งผลิต',
      'dwg': 'แบบ Drawing',
      'qc': 'QC Check Sheet'
    };

    function updateSequenceText() {
      const text = currentOrder.map(id => sourceNames[id]).join(' ➔ ');
      document.getElementById('currentSequenceText').innerText = text;
    }

    function renderSourceCards() {
      const list = document.getElementById('sourcesList');
      const cards = Array.from(list.children);
      cards.sort((a, b) => {
        return currentOrder.indexOf(a.dataset.id) - currentOrder.indexOf(b.dataset.id);
      });
      cards.forEach((card, idx) => {
        card.querySelector('.order-badge').innerText = idx + 1;
        list.appendChild(card);
      });
      updateSequenceText();
    }

    function moveSource(id, direction) {
      const idx = currentOrder.indexOf(id);
      const newIdx = idx + direction;
      if (newIdx < 0 || newIdx >= currentOrder.length) return;
      currentOrder.splice(idx, 1);
      currentOrder.splice(newIdx, 0, id);
      renderSourceCards();
    }

    async function refreshStatus() {
      try {
        const res = await fetch('/api/preview');
        const data = await res.json();
        
        document.getElementById('activeFileName').innerText = data.active_file || 'ไม่มีไฟล์';
        document.getElementById('activeFileCount').innerText = `${data.total_pds || 0} ใบ`;

        document.getElementById('statTotal').innerText = `ทั้งหมด: ${data.total_pds || 0} รายการ`;
        document.getElementById('statMatched').innerText = `พบ Drawing: ${data.matched_dwg || 0}`;
        document.getElementById('statMissing').innerText = `รอ Drawing: ${data.missing_dwg || 0}`;

        if (data.output_files_count > 0) {
          document.getElementById('btnZip').classList.remove('hidden');
        } else {
          document.getElementById('btnZip').classList.add('hidden');
        }

        const tbody = document.getElementById('tableBody');
        if (!data.items || data.items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-slate-400">ยังไม่มีข้อมูลใบสั่งผลิต กรุณาอัปโหลดไฟล์ PDF</td></tr>';
          return;
        }

        tbody.innerHTML = data.items.map((item, idx) => {
          const dwgBadge = item.has_drawing 
            ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">✓ ${item.drawing_file}</span>`
            : `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">⚠ ยังไม่พบแบบ</span>`;

          const outputBtn = item.output_exists
            ? `<a href="/output/${item.output_file}" target="_blank" class="px-2.5 py-1 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 rounded text-[11px] font-medium text-slate-700 border border-slate-200 transition">📄 เปิด PDF</a>`
            : `<span class="text-slate-400 text-[11px]">-</span>`;

          return `<tr class="hover:bg-slate-50/80 transition">
            <td class="py-2.5 px-3 text-center text-slate-400">${idx + 1}</td>
            <td class="py-2.5 px-3 font-bold text-slate-900">${item.pd_no}</td>
            <td class="py-2.5 px-3 font-mono text-slate-700">${item.item_no}</td>
            <td class="py-2.5 px-3 text-slate-800">${item.item_name}</td>
            <td class="py-2.5 px-3 text-center font-semibold text-slate-900">${item.qty} ${item.unit}</td>
            <td class="py-2.5 px-3">${dwgBadge}</td>
            <td class="py-2.5 px-3 text-center">${outputBtn}</td>
          </tr>`;
        }).join('');

      } catch (e) {
        console.error(e);
      }
    }

    // File Drag & Drop
    const dropZone = document.getElementById('dropZone');
    dropZone.onclick = () => document.getElementById('fileInput').click();
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('border-indigo-500', 'bg-indigo-50/50'); };
    dropZone.ondragleave = () => { dropZone.classList.remove('border-indigo-500', 'bg-indigo-50/50'); };
    dropZone.ondrop = (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-indigo-500', 'bg-indigo-50/50');
      if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files);
    };

    async function handleFileSelect(files) {
      if (!files.length) return;
      const file = files[0];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        alert('กรุณาเลือกไฟล์ PDF เท่านั้น');
        return;
      }

      const progressDiv = document.getElementById('uploadProgress');
      const progressBar = document.getElementById('progressBar');
      const progressText = document.getElementById('uploadText');
      progressDiv.classList.remove('hidden');
      progressBar.style.width = '30%';
      progressText.innerText = 'กำลังส่งไฟล์...';

      const formData = new FormData();
      formData.append('file', file);

      try {
        progressBar.style.width = '70%';
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const result = await res.json();
        progressBar.style.width = '100%';
        progressText.innerText = 'อัปโหลดสำเร็จ!';
        setTimeout(() => {
          progressDiv.classList.add('hidden');
          progressBar.style.width = '0%';
        }, 1200);
        await refreshStatus();
      } catch (err) {
        alert('เกิดข้อผิดพลาดในการอัปโหลด: ' + err);
        progressDiv.classList.add('hidden');
      }
    }

    async function startProcessing() {
      const mode = document.querySelector('input[name="outputMode"]:checked').value;
      const btn = document.getElementById('btnProcess');
      const banner = document.getElementById('processingBanner');

      btn.disabled = true;
      btn.classList.add('opacity-50', 'cursor-not-allowed');
      banner.classList.remove('hidden');

      try {
        const res = await fetch('/api/process', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order: currentOrder,
            mode: mode
          })
        });
        const result = await res.json();
        if (result.success) {
          await refreshStatus();
          alert(`จัดชุดเอกสารเรียบร้อยแล้ว!\\n- สร้างไฟล์ทั้งหมด: ${result.files_created} ไฟล์\\n- ดูผลลัพธ์ได้ที่ตารางด้านล่างหรือกดเปิดโฟลเดอร์ Output`);
        } else {
          alert('เกิดข้อผิดพลาด: ' + result.error);
        }
      } catch (e) {
        alert('เกิดข้อผิดพลาดในการประมวลผล: ' + e);
      } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        banner.classList.add('hidden');
      }
    }

    async function openOutputFolder() {
      await fetch('/api/open-folder', { method: 'POST' });
    }

    // Init
    window.onload = () => {
      renderSourceCards();
      refreshStatus();
    };
  </script>
</body>
</html>
"""

class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging
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
            body = HTML_TEMPLATE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/preview":
            active_pdf = get_active_pd_pdf()
            items_list = []
            matched_count = 0
            missing_count = 0

            if active_pdf and os.path.exists(active_pdf):
                pd_groups = parse_pd_pdf(active_pdf)
                dwg_files = get_dwg_files()

                for pd_no, data in pd_groups.items():
                    item_no = data['item_no']
                    item_name = data['item_name']
                    qty_fmt = format_qty(data['qty'])

                    # check drawing match
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

            # Simple robust multipart boundary extraction
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
                            # Also copy to pd_list for consistency
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
            mode = payload.get('mode', 'split') # split, merge, both

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
            dwg_files = get_dwg_files()

            files_created_count = 0
            combined_doc = fitz.open() if mode in ['merge', 'both'] else None

            for pd_no, data in pd_groups.items():
                item_no = data['item_no']
                qty_formatted = format_qty(data['qty'])

                # 1. Matching Drawing
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

                # Document for this single PD
                single_doc = fitz.open()

                # Assemble in the requested order!
                for source_key in order:
                    if source_key == 'pd':
                        # Append PD pages
                        for p in data['pages']:
                            single_doc.insert_pdf(src_doc, from_page=p, to_page=p)
                    elif source_key == 'dwg':
                        # Append Drawing pages
                        if selected_dwg:
                            try:
                                d_doc = fitz.open(selected_dwg[2])
                                single_doc.insert_pdf(d_doc)
                                d_doc.close()
                            except Exception as e:
                                print(f"Error reading dwg: {e}")
                    elif source_key == 'qc':
                        # Append QC page stamped
                        qc_doc = fitz.open(qc_form_path)
                        qc_page = qc_doc[0]
                        # Stamp PD
                        qc_page.draw_rect(fitz.Rect(132, 69, 204, 81), color=None, fill=(1, 1, 1))
                        qc_page.insert_text(fitz.Point(133, 78.5), pd_no, fontsize=8.5, fontname='helv', color=(0, 0, 0))
                        # Stamp QTY
                        qc_page.draw_rect(fitz.Rect(415, 69, 454, 81), color=None, fill=(1, 1, 1))
                        text_width = len(qty_formatted) * 5.2
                        x_qty = 415 + (454 - 415 - text_width) / 2
                        qc_page.insert_text(fitz.Point(max(416, x_qty), 78.5), qty_formatted, fontsize=8.5, fontname='helv', color=(0, 0, 0))
                        single_doc.insert_pdf(qc_doc)
                        qc_doc.close()

                # Save split file if required
                if mode in ['split', 'both']:
                    out_path = os.path.join(OUTPUT_DIR, f"{pd_no}.pdf")
                    single_doc.save(out_path)
                    files_created_count += 1

                # If merged file is requested, add single_doc into combined_doc
                if combined_doc is not None:
                    combined_doc.insert_pdf(single_doc)

                single_doc.close()

            src_doc.close()

            # Save combined doc if required
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

def run(port=8080):
    server = ThreadingHTTPServer(('0.0.0.0', port), AppHandler)
    print(f"==================================================")
    print(f" Web App started successfully!")
    print(f" URL: http://localhost:{port}")
    print(f"==================================================")
    server.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
