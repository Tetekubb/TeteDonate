# 💖 Discord Donation Bot

บอทรับโดเนทผ่าน PromptPay สำหรับ Discord พร้อม Leaderboard และแจ้งเตือนอัตโนมัติ

## 🚀 ฟีเจอร์

| คำสั่ง | คำอธิบาย |
|--------|----------|
| `/donate` | แสดง QR Code PromptPay ตามจำนวนเงินที่กำหนด |
| `/confirm` | แจ้งยืนยันการโดเนท พร้อมแนบสลิปได้ |
| `/leaderboard` | ดูอันดับผู้โดเนทสูงสุด 🏆 |
| `/donateinfo` | ดูสถิติโดเนทรวม |
| `/resetdonations` | [Admin] รีเซ็ตข้อมูลทั้งหมด |

---

## ⚙️ วิธีติดตั้ง

### 1. สร้างบอทใน Discord Developer Portal

1. ไปที่ https://discord.com/developers/applications
2. กด **New Application** → ตั้งชื่อ
3. เลือก **Bot** → กด **Add Bot**
4. เปิด **MESSAGE CONTENT INTENT**, **SERVER MEMBERS INTENT**
5. คัดลอก **Token**
6. ไปที่ **OAuth2 → URL Generator** → เลือก `bot` + `applications.commands`
7. เลือก Permission: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`
8. คัดลอก URL แล้วเชิญบอทเข้าเซิร์ฟเวอร์

### 2. ตั้งค่า Environment Variables

คัดลอก `.env.example` → `.env` แล้วแก้ไขค่า:

```
DISCORD_TOKEN=  ← Token จากข้อ 1
OWNER_ID=       ← User ID ของคุณ (เปิด Developer Mode → คลิกขวาที่ตัวเอง → Copy ID)
PROMPTPAY_NUMBER= ← เบอร์โทร หรือ เลขบัตรประจำตัว 13 หลัก
```

### 3. รันในเครื่อง (ทดสอบ)

```bash
pip install -r requirements.txt
python bot.py
```

---

## 🚂 Deploy บน Railway

### วิธีที่ 1: GitHub (แนะนำ)

1. Push โค้ดทั้งหมดขึ้น GitHub repository
2. ไปที่ https://railway.com → **New Project** → **Deploy from GitHub**
3. เลือก repo ของคุณ
4. ไปที่ **Variables** → เพิ่ม ENV ทีละตัว:
   - `DISCORD_TOKEN`
   - `OWNER_ID`
   - `PROMPTPAY_NUMBER`
5. Railway จะ deploy อัตโนมัติ ✅

### วิธีที่ 2: Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set DISCORD_TOKEN=xxx OWNER_ID=xxx PROMPTPAY_NUMBER=xxx
```

### ⚠️ หมายเหตุสำหรับ Railway

- ไฟล์ `donations.json` จะหายเมื่อ redeploy เพราะ Railway ไม่มี persistent disk ฟรี
- หากต้องการเก็บข้อมูลถาวร ให้ใช้ **Railway PostgreSQL** หรือ **Google Sheets API**
- ใช้ `Procfile` เพื่อบอก Railway ว่าให้รัน `python bot.py` เป็น worker (ไม่ใช่ web server)

---

## 📁 โครงสร้างไฟล์

```
donate_bot/
├── bot.py              ← โค้ดหลัก
├── requirements.txt    ← dependencies
├── Procfile            ← บอก Railway วิธีรัน
├── .env.example        ← ตัวอย่าง ENV
└── donations.json      ← ข้อมูลโดเนท (สร้างอัตโนมัติ)
```

---

## 💡 Tips

- **หา User ID:** เปิด Discord Developer Mode (Settings → Advanced → Developer Mode) แล้วคลิกขวาที่ตัวเอง → Copy ID
- **QR Code:** สร้างตามมาตรฐาน EMVCo PromptPay ที่ธนาคารไทยรองรับทุกเจ้า
- **สลิป:** ผู้โดเนทสามารถแนบรูปสลิปพร้อมกับ `/confirm` ได้เลย
