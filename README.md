# Production-Prepare-Document

ระบบจัดชุดเอกสารสำหรับเตรียมผลิต (Production Document Assembler)

ระบบช่วยจัดชุดเอกสารสำหรับสายการผลิตอัตโนมัติ โดยรวมเอกสารสำคัญ 3 แหล่งเข้าด้วยกัน:
1. **ใบสั่งผลิต (Production Order - PD):** ดึงหน้าประจำแต่ละ Production Order จากไฟล์ PDF รวม
2. **แบบชิ้นงาน (Drawing PDF):** ค้นหาและจับคู่ไฟล์แบบ Drawing ตามรหัส Item No (ตัดขีด `-` ออก) พร้อมเลือก Revision ล่าสุดอัตโนมัติ
3. **ใบตรวจสอบคุณภาพ (QC Check Sheet):** แนบแบบฟอร์มตรวจสอบคุณภาพ พร้อมพิมพ์ระบุเลขที่ Production Order และจำนวนสั่งผลิต (QTY) ลงในช่องให้อัตโนมัติ

---

## ฟังก์ชันการทำงานหลัก (Features)
- **Web Application GUI:** ใช้งานง่ายผ่านหน้าเว็บ
- **Drag & Drop Upload:** รองรับการอัปโหลดไฟล์ Production Order PDF เข้าสู่ระบบ
- **จัดเรียงลำดับเอกสารได้อิสระ:** สามารถเลื่อนสลับลำดับเอกสาร 3 แหล่ง (PD / Drawing / QC Check Sheet) ก่อนจัดชุดได้
- **ตัวเลือกการสร้างไฟล์ (Output Options):**
  - แยกไฟล์ตาม Production Order (เช่น `PD2611023.pdf`, `PD2611024.pdf`, ...)
  - รวมเป็นไฟล์เดียวทั้งหมด (`ALL_PD_COMBINED.pdf`) สำหรับส่งพิมพ์ทีเดียว
  - สร้างทั้งสองแบบ
- **ดาวน์โหลดผลลัพธ์:** ดาวน์โหลดไฟล์แยกรายใบ หรือดาวน์โหลดเป็นไฟล์ ZIP รวมทั้งหมดในคลิกเดียว

---

## โครงสร้างโฟลเดอร์ (Directory Structure)
```
pdo_prepare_print/
│
├── app.py                      # Web Application Backend & Frontend
├── run_app.bat                 # ตัวเปิดใช้งาน Web App (Double-click to run)
├── generate_pd_drawings.py     # สคริปต์ประมวลผลจัดชุดเอกสาร (CLI)
├── requirements.txt            # รายการ Dependencies
│
├── pdf_list/                   # โฟลเดอร์สำหรับเก็บไฟล์ Production Order (PDF)
├── pd_list/                    # โฟลเดอร์สำรอง Production Order
├── att_form/                   # โฟลเดอร์เก็บแบบฟอร์มแนบ (QC_check_sheet.pdf)
└── output/                     # โฟลเดอร์บันทึกไฟล์ผลลัพธ์ที่จัดชุดแล้ว
```

---

## วิธีติดตั้งและเริ่มใช้งาน (Getting Started)

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. เปิดใช้งาน Web Application
สามารถดับเบิลคลิกที่ไฟล์ **`run_app.bat`** หรือรันคำสั่ง:
```bash
python app.py 8088
```
จากนั้นเปิดเบราว์เซอร์ไปที่: `http://localhost:8088`
