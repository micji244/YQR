# YQR – QR Code Generator

แอปสร้างและสแกน QR Code บน Windows (Python + customtkinter)

- สร้าง QR ได้หลายแบบ: URL, Wi-Fi, นามบัตร (vCard), อีเมล, SMS, ข้อความ
- แม่แบบดีไซน์ ปรับสี รูปทรงโมดูล ใส่โลโก้ และข้อความใต้ QR ได้
- บันทึกเป็น PNG / JPG / SVG / PDF หรือคัดลอกไปคลิปบอร์ด
- สแกน QR จากไฟล์รูปหรือจากคลิปบอร์ด
- ตรวจให้อัตโนมัติว่า QR ที่สร้างสแกนได้จริง

## รันจากโค้ด

ต้องมี Python 3.11 ขึ้นไป

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Build เป็น .exe

```powershell
python -m PyInstaller --noconfirm YQR.spec
```

ไฟล์ที่ได้จะอยู่ที่ `dist\YQR.exe`

> ควรใช้ `python -m PyInstaller` แทนการพิมพ์ `pyinstaller` เฉยๆ
> เพื่อให้ build ด้วย Python ตัวเดียวกับที่ติดตั้งไลบรารีไว้
> (ถ้าใช้คนละตัว exe จะเปิดแล้วขึ้น `No module named 'customtkinter'`)

## หมายเหตุเรื่องฟอนต์

แอปใช้ฟอนต์ Tahoma (รองรับภาษาไทย) จาก `C:\Windows\Fonts` โดยอัตโนมัติ
ถ้าต้องการฝังฟอนต์ไว้ใน exe ให้วาง `tahoma.ttf` ไว้ในโฟลเดอร์ `fonts\`
ก่อน build (โฟลเดอร์นี้ไม่ได้อัปขึ้น git เพราะฟอนต์มีลิขสิทธิ์ของ Microsoft)
