"""
╔══════════════════════════════════════════════════════╗
║         Discord Donation Bot  –  by Claude           ║
║  PromptPay QR  |  TrueMoney Wallet  |  Leaderboard  ║
╚══════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import datetime
import qrcode
import io
from dotenv import load_dotenv

load_dotenv()

# ╔══════════════════════════════════════════════════╗
# ║                    CONFIG                        ║
# ╚══════════════════════════════════════════════════╝
TOKEN               = os.getenv("DISCORD_TOKEN")
OWNER_ID            = int(os.getenv("OWNER_ID", "0"))
PROMPTPAY_NUMBER    = os.getenv("PROMPTPAY_NUMBER", "0812345678")
TRUEMONEY_NUMBER    = os.getenv("TRUEMONEY_NUMBER", "0812345678")
TRUEMONEY_NAME      = os.getenv("TRUEMONEY_NAME", "ชื่อ นามสกุล")
LOG_FILE            = "donations.json"

# ── สีธีม ──────────────────────────────────────────
COLOR_DONATE   = 0xFF69B4
COLOR_CONFIRM  = 0xFFD700
COLOR_BOARD    = 0x5865F2
COLOR_OWNER_DM = 0x00FF88
COLOR_INFO     = 0x36393F


# ╔══════════════════════════════════════════════════╗
# ║                   HELPERS                        ║
# ╚══════════════════════════════════════════════════╝

def load_donations() -> dict:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"donations": [], "total": 0}


def save_donations(data: dict):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_promptpay_payload(number: str, amount: float) -> str:
    """สร้าง EMVCo PromptPay payload พร้อม CRC-16"""
    number = number.replace("-", "").replace(" ", "")
    if len(number) == 10 and number.startswith("0"):
        number = "0066" + number[1:]

    amount_str = f"{amount:.2f}"

    def crc16(data: str) -> str:
        crc = 0xFFFF
        for byte in data.encode("ascii"):
            crc ^= byte << 8
            for _ in range(8):
                crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
        return format(crc & 0xFFFF, "04X")

    def tlv(tag: str, value: str) -> str:
        return f"{tag}{len(value):02d}{value}"

    aid      = tlv("00", "A000000677010111")
    mobile   = tlv("01", number)
    merchant = tlv("29", aid + mobile)
    payload  = (
        tlv("00", "01")
        + tlv("01", "12")
        + merchant
        + tlv("53", "764")
        + tlv("54", amount_str)
        + tlv("58", "TH")
        + "6304"
    )
    return payload + crc16(payload)


def generate_promptpay_qr(amount: float) -> discord.File:
    payload = build_promptpay_payload(PROMPTPAY_NUMBER, amount)
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="promptpay_qr.png")


def truemoney_link(amount: float) -> str:
    number = TRUEMONEY_NUMBER.replace("-", "").replace(" ", "")
    return f"https://tmn.app.link/transfer?mobile={number}&amount={amount:.2f}"


# ╔══════════════════════════════════════════════════╗
# ║                     BOT                          ║
# ╚══════════════════════════════════════════════════╝

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


async def notify_owner(embed: discord.Embed):
    """DM แจ้งเจ้าของบอทเมื่อมีโดเนท"""
    if not OWNER_ID:
        return
    try:
        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(embed=embed)
    except Exception:
        pass


# ── Events ───────────────────────────────────────────

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ บอทออนไลน์: {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="💖 รับโดเนท | /donate"
        )
    )


# ── /donate ──────────────────────────────────────────

@tree.command(name="donate", description="โดเนทให้เซิร์ฟเวอร์ 💖 รองรับ PromptPay & TrueMoney")
@app_commands.describe(
    amount  = "จำนวนเงินที่ต้องการโดเนท (บาท)",
    method  = "ช่องทางการชำระเงิน",
    message = "ข้อความที่อยากฝากถึงเจ้าของ (ไม่บังคับ)",
)
@app_commands.choices(method=[
    app_commands.Choice(name="💳 PromptPay (สแกน QR)", value="promptpay"),
    app_commands.Choice(name="🧡 TrueMoney Wallet",     value="truemoney"),
])
async def donate(
    interaction: discord.Interaction,
    amount: float,
    method: str = "promptpay",
    message: str = "",
):
    if amount <= 0:
        await interaction.response.send_message("❌ จำนวนเงินต้องมากกว่า 0 บาท", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if method == "promptpay":
        qr_file = generate_promptpay_qr(amount)
        embed = discord.Embed(
            title="💳 โดเนทผ่าน PromptPay",
            description=(
                f"**จำนวน:** `{amount:,.2f}` บาท\n"
                f"**PromptPay:** `{PROMPTPAY_NUMBER}`\n\n"
                f"📱 สแกน QR Code ด้านล่างได้เลยครับ\n"
                + (f"\n💬 *{message}*" if message else "")
            ),
            color=COLOR_DONATE,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_image(url="attachment://promptpay_qr.png")
        embed.set_footer(text="หลังโอนแล้ว ใช้ /confirm เพื่อแจ้งยืนยันด้วยนะครับ 🙏")
        await interaction.followup.send(embed=embed, file=qr_file, ephemeral=True)

    else:  # TrueMoney
        tmn_link = truemoney_link(amount)
        embed = discord.Embed(
            title="🧡 โดเนทผ่าน TrueMoney Wallet",
            description=(
                f"**จำนวน:** `{amount:,.2f}` บาท\n"
                f"**เบอร์:** `{TRUEMONEY_NUMBER}`\n"
                f"**ชื่อบัญชี:** {TRUEMONEY_NAME}\n\n"
                f"👉 กด **[เปิดแอป TrueMoney]({tmn_link})** หรือโอนหาเบอร์ด้านบนได้เลยครับ\n"
                + (f"\n💬 *{message}*" if message else "")
            ),
            color=0xFF6600,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text="หลังโอนแล้ว ใช้ /confirm เพื่อแจ้งยืนยันด้วยนะครับ 🙏")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ── /confirm ─────────────────────────────────────────

@tree.command(name="confirm", description="แจ้งยืนยันการโดเนทหลังโอนเงินแล้ว ✅")
@app_commands.describe(
    amount  = "จำนวนเงินที่โอน (บาท)",
    method  = "ช่องทางที่ใช้โอน",
    slip    = "แนบสลิปการโอน (ไม่บังคับ)",
    message = "ข้อความถึงเจ้าของ",
)
@app_commands.choices(method=[
    app_commands.Choice(name="💳 PromptPay", value="PromptPay"),
    app_commands.Choice(name="🧡 TrueMoney", value="TrueMoney"),
])
async def confirm(
    interaction: discord.Interaction,
    amount: float,
    method: str = "PromptPay",
    slip: discord.Attachment = None,
    message: str = "",
):
    if amount <= 0:
        await interaction.response.send_message("❌ จำนวนเงินต้องมากกว่า 0 บาท", ephemeral=True)
        return

    await interaction.response.defer()

    data = load_donations()
    record = {
        "user_id":   interaction.user.id,
        "user_name": str(interaction.user),
        "amount":    amount,
        "method":    method,
        "message":   message,
        "slip_url":  slip.url if slip else None,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    data["donations"].append(record)
    data["total"] = round(data["total"] + amount, 2)
    save_donations(data)

    method_icon = "💳" if method == "PromptPay" else "🧡"

    # Embed สาธารณะ
    embed = discord.Embed(
        title="🎉 มีโดเนทเข้ามา!",
        color=COLOR_CONFIRM,
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="👤 ผู้โดเนท",           value=interaction.user.mention,       inline=True)
    embed.add_field(name="💰 จำนวน",               value=f"`{amount:,.2f}` บาท",          inline=True)
    embed.add_field(name=f"{method_icon} ช่องทาง", value=method,                          inline=True)
    embed.add_field(name="📊 รวมทั้งหมด",          value=f"`{data['total']:,.2f}` บาท",   inline=False)
    if message:
        embed.add_field(name="💬 ข้อความ", value=message, inline=False)
    if slip:
        embed.set_image(url=slip.url)
    embed.set_footer(text="ขอบคุณมากๆ ครับ/ค่ะ 💖")

    await interaction.followup.send(embed=embed)

    # DM แจ้งเจ้าของ
    dm_embed = discord.Embed(
        title=f"💌 โดเนทใหม่! {method_icon}",
        description=(
            f"**จาก:** {interaction.user} (`{interaction.user.id}`)\n"
            f"**จำนวน:** `{amount:,.2f}` บาท\n"
            f"**ช่องทาง:** {method}\n"
            f"**ข้อความ:** {message or '-'}\n"
            f"**สลิป:** {slip.url if slip else 'ไม่มี'}\n"
            f"**เซิร์ฟเวอร์:** {interaction.guild.name if interaction.guild else 'DM'}\n"
            f"**ยอดรวม:** `{data['total']:,.2f}` บาท"
        ),
        color=COLOR_OWNER_DM,
        timestamp=datetime.datetime.utcnow(),
    )
    await notify_owner(dm_embed)


# ── /leaderboard ─────────────────────────────────────

@tree.command(name="leaderboard", description="ดูอันดับผู้โดเนทสูงสุด 🏆")
async def leaderboard(interaction: discord.Interaction):
    data      = load_donations()
    donations = data.get("donations", [])

    totals: dict[int, float] = {}
    names:  dict[int, str]   = {}
    for d in donations:
        uid         = d["user_id"]
        totals[uid] = round(totals.get(uid, 0) + d["amount"], 2)
        names[uid]  = d["user_name"]

    sorted_users = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]

    if not sorted_users:
        await interaction.response.send_message("ยังไม่มีข้อมูลโดเนทครับ 🥲", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines  = [
        f"{medals[i]} **{names[uid]}** — `{total:,.2f}` บาท"
        for i, (uid, total) in enumerate(sorted_users)
    ]

    embed = discord.Embed(
        title       = "🏆 Leaderboard ผู้โดเนท",
        description = "\n".join(lines),
        color       = COLOR_BOARD,
        timestamp   = datetime.datetime.utcnow(),
    )
    embed.set_footer(text=f"ยอดรวมทั้งหมด: {data['total']:,.2f} บาท  •  {len(donations)} ครั้ง")
    await interaction.response.send_message(embed=embed)


# ── /donateinfo ───────────────────────────────────────

@tree.command(name="donateinfo", description="ดูสถิติการโดเนทรวม 📊")
async def donateinfo(interaction: discord.Interaction):
    data      = load_donations()
    donations = data.get("donations", [])
    count     = len(donations)
    total     = data.get("total", 0)
    avg       = (total / count) if count else 0

    by_method: dict[str, float] = {}
    for d in donations:
        m = d.get("method", "PromptPay")
        by_method[m] = round(by_method.get(m, 0) + d["amount"], 2)

    embed = discord.Embed(
        title     = "📊 สถิติการโดเนท",
        color     = COLOR_INFO,
        timestamp = datetime.datetime.utcnow(),
    )
    embed.add_field(name="💰 ยอดรวมทั้งหมด", value=f"`{total:,.2f}` บาท", inline=True)
    embed.add_field(name="📝 จำนวนครั้ง",     value=f"`{count}` ครั้ง",   inline=True)
    embed.add_field(name="📈 เฉลี่ยต่อครั้ง", value=f"`{avg:,.2f}` บาท",  inline=True)

    if by_method:
        method_lines = "\n".join(
            f"{'💳' if m == 'PromptPay' else '🧡'} **{m}:** `{v:,.2f}` บาท"
            for m, v in by_method.items()
        )
        embed.add_field(name="🗂️ แยกตามช่องทาง", value=method_lines, inline=False)

    await interaction.response.send_message(embed=embed)


# ── /resetdonations ───────────────────────────────────

@tree.command(name="resetdonations", description="[Admin] รีเซ็ตข้อมูลโดเนททั้งหมด")
async def resetdonations(interaction: discord.Interaction):
    is_owner = interaction.user.id == OWNER_ID
    is_admin = (
        interaction.guild is not None
        and interaction.user.guild_permissions.administrator
    )
    if not (is_owner or is_admin):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        return
    save_donations({"donations": [], "total": 0})
    await interaction.response.send_message("✅ รีเซ็ตข้อมูลโดเนทเรียบร้อยแล้ว", ephemeral=True)


# ── Run ───────────────────────────────────────────────

if __name__ == "__main__":
    bot.run(TOKEN)
