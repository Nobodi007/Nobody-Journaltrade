# Nobody Trade Journal v3

MT5 → NobodyCollector (EA) → Supabase → Streamlit

## โครงสร้าง
```
app.py                  หน้า Overview / Performance / Journal
core/trades.py          รวม deal เป็นไม้ + คำนวณสถิติ (pandas ล้วน)
core/data.py            อ่านตาราง mt5_* จาก Supabase (อ่านอย่างเดียว)
core/notes.py           โน้ตต่อไม้ (ตาราง trade_notes)
core/ui.py              ธีม การ์ด กราฟ ปฏิทิน
supabase/trade_notes.sql   รันครั้งเดียวใน SQL Editor เพื่อเปิดใช้โน้ต
legacy/                 แอปเวอร์ชันเก่าทั้งหมด (รันแยกได้: streamlit run legacy/app.py)
```

## Secrets (Streamlit Cloud → Settings → Secrets)
```
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "sb_publishable_..."
APP_PASSWORD = "..."   # ไม่ใส่ก็ได้
```

## หมายเหตุ
- เวลาทั้งหมดเป็นเวลาเซิร์ฟเวอร์โบรกเกอร์ตามที่ MT5 แสดง
- 1 แถวในตารางเทรด = 1 position ที่ปิดครบแล้ว (ไม้ที่ยังเปิด/ปิดบางส่วนไม่นับ)
- Equity curve ใช้ "Balance โดยประมาณ" = balance ปัจจุบัน − กำไรสุทธิที่ปิดแล้ว (นับฝาก/ถอนรวมในเงินทุน)
- EA ที่ใช้: NobodyCollector_Supabase_Pending_v1.43_IgnoreDup.mq5 ขึ้นไป
- legacy/ ต้องใช้แพ็กเกจเพิ่ม: python-dateutil, openpyxl (pip install) ถ้าจะรันแยก
