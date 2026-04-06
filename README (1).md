# 🎵 Discord Music Bot

บอทฟังเพลง Discord สมบูรณ์แบบ — อยู่ในห้องตลอด ไม่ออกแม้เพลงจบ

## ✨ Features
- ▶️ เล่น YouTube / Playlist
- ⏭️ Skip, Pause, Resume
- 📋 Queue system
- 🔂 Loop เพลง / Loop Queue
- 🔀 Shuffle queue
- 🔊 ปรับ Volume 0-200%
- 🗑️ Remove / Clear queue
- 🏠 **อยู่ในห้องตลอด ไม่ disconnect เองเมื่อเพลงจบ**

## 📦 Commands

| คำสั่ง | ความหมาย |
|--------|----------|
| `!play <ชื่อ/URL>` | เล่นเพลงหรือเพิ่มใน queue |
| `!skip` | ข้ามเพลง |
| `!pause` / `!resume` | หยุด / เล่นต่อ |
| `!stop` | หยุดและล้าง queue |
| `!queue` | ดู queue |
| `!np` | เพลงที่กำลังเล่น |
| `!loop [song/queue/off]` | ตั้งค่า loop |
| `!volume <0-200>` | ปรับเสียง |
| `!shuffle` | สับ queue |
| `!remove <เลข>` | ลบเพลงใน queue |
| `!clear` | ล้าง queue |
| `!join` / `!leave` | เรียก / ไล่บอทออก |

## 🚀 วิธี Deploy บน Railway

### 1. สร้าง Discord Bot
1. ไปที่ https://discord.com/developers/applications
2. **New Application** → ตั้งชื่อ
3. ไปที่ **Bot** → **Add Bot**
4. เปิด **Message Content Intent**, **Server Members Intent**, **Presence Intent**
5. คัดลอก **Token**

### 2. Invite บอทเข้า Server
1. ไปที่ **OAuth2 → URL Generator**
2. เลือก Scopes: `bot`, `applications.commands`
3. เลือก Permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Read Message History`, `View Channels`
4. เปิด URL ที่ได้ แล้ว Invite เข้า server

### 3. Deploy บน Railway
1. Push โค้ดขึ้น GitHub repo
2. ไปที่ https://railway.com/ → **New Project → Deploy from GitHub**
3. เลือก repo ที่มีไฟล์นี้
4. ไปที่ **Variables** แล้วเพิ่ม:
   - `DISCORD_TOKEN` = โทเค็นของบอท
   - `PREFIX` = `!` (หรือเปลี่ยนได้)
5. Railway จะ build และ deploy อัตโนมัติ ✅

> Railway ใช้ `Dockerfile` ในการ build — ffmpeg จะถูกติดตั้งอัตโนมัติ

## ⚙️ Environment Variables

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
|--------|-----------|---------|
| `DISCORD_TOKEN` | *(จำเป็น)* | Token ของ Discord Bot |
| `PREFIX` | `!` | Prefix คำสั่ง |
