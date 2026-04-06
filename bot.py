import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import static_ffmpeg
import os
from datetime import datetime, timedelta

# --- [Configuration] ---
TOKEN = os.getenv('TOKEN')

# ตั้งค่า yt-dlp ให้ฉลาดขึ้นเพื่อป้องกันการหาเพลงไม่เจอ
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'force_generic_extractor': False,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

def format_time(seconds):
    if not seconds: return "00:00"
    return str(timedelta(seconds=seconds)).split('.')[0]

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.queue = {}
        self.autoplay = {}
        self.current_song = {}
        self.volume = {}

    async def setup_hook(self):
        static_ffmpeg.add_paths()
        await self.tree.sync()
        print(f"✅ บอทเพลงระบบเต็ม (Fixed) ออนไลน์แล้ว: {self.user}")

bot = MusicBot()

# --- [Embed ดีไซน์เริ่ดๆ ตามรูป] ---
def create_music_embed(song, status_text, color, interaction):
    gid = interaction.guild_id
    vol = bot.volume.get(gid, 1.0)
    ap_status = "เปิด ✅" if bot.autoplay.get(gid, True) else "ปิด ❌"
    
    embed = discord.Embed(
        title=f"{status_text} {song['title']}",
        url=song['original_url'],
        color=color
    )
    
    # การจัดวาง Field ตามรูปตัวอย่าง
    embed.add_field(name="✨ เจ้าของเพลง", value=f"```fix\n{song['uploader']}```", inline=True)
    embed.add_field(name="⏰ ความยาว", value=f"```yaml\n{format_time(song['duration'])}```", inline=True)
    embed.add_field(name="👤 เพิ่มเพลงโดย", value=f"@{interaction.user.display_name}", inline=True)
    
    vc_name = interaction.user.voice.channel.name if interaction.user.voice else "Unknown"
    embed.add_field(name="🔊 ช่องเสียง", value=f"```bash\n# {vc_name}```", inline=True)
    embed.add_field(name="📊 ระดับเสียง", value=f"```python\n{int(vol*100)}%```", inline=True)
    embed.add_field(name="📻 Autoplay", value=f"```fix\n{ap_status}```", inline=True)

    if song.get('thumbnail'):
        embed.set_image(url=song['thumbnail'])
    
    embed.set_footer(text=f"ระบบเพลงสมบูรณ์แบบ • {datetime.now().strftime('%H:%M:%S')}")
    return embed

# --- [Core Logic] ---
async def play_next(interaction):
    gid = interaction.guild_id
    vc = interaction.guild.voice_client
    if not vc: return

    if gid in bot.queue and bot.queue[gid]:
        song = bot.queue[gid].pop(0)
        await start_playing(interaction, song)
    elif bot.autoplay.get(gid, True) and gid in bot.current_song:
        # ระบบ Autoplay
        last_song_id = bot.current_song[gid]['id']
        await interaction.channel.send("🔄 *คิวหมด... กำลังหาเพลงที่คล้ายกันมาเล่นต่อ (Autoplay)*")
        
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={last_song_id}", download=False)
                related = info.get('related_videos', [])
                if related:
                    next_url = f"https://www.youtube.com/watch?v={related[0]['id']}"
                    await play_logic(interaction, next_url, is_autoplay=True)
            except: pass

async def start_playing(interaction, song):
    gid = interaction.guild_id
    vc = interaction.guild.voice_client
    bot.current_song[gid] = song
    vol = bot.volume.get(gid, 1.0)
    
    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
    transformed = discord.PCMVolumeTransformer(source, volume=vol)
    
    vc.play(transformed, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop))
    
    embed = create_music_embed(song, "🎶 กำลังเล่นเพลง", 0x2ecc71, interaction)
    await interaction.channel.send(embed=embed)

async def play_logic(interaction, search, is_autoplay=False):
    gid = interaction.guild_id
    vc = interaction.guild.voice_client

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info: info = info['entries'][0]
            song = {
                'url': info['url'], 'original_url': info.get('webpage_url'),
                'title': info['title'], 'uploader': info.get('uploader', 'ไม่ระบุ'),
                'duration': info.get('duration', 0), 'thumbnail': info.get('thumbnail'),
                'id': info.get('id')
            }
        except Exception as e:
            print(f"Error: {e}")
            return await interaction.channel.send("❌ หาเพลงไม่เจอ ลองใช้ชื่ออื่นหรือลิงก์ตรงดูครับ")

    if vc.is_playing() or vc.is_paused():
        if not is_autoplay:
            bot.queue.setdefault(gid, []).append(song)
            embed = create_music_embed(song, "✅ เพิ่มเพลงเข้าคิว", 0x3498db, interaction)
            await interaction.channel.send(embed=embed)
    else:
        await start_playing(interaction, song)

# --- [Commands] ---

@bot.tree.command(name="play", description="เล่นเพลง/เพิ่มเข้าคิว (เริ่ดๆ)")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("❌ เข้าห้องเสียงก่อนนะ!")
    
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect(self_deaf=True)
    
    await play_logic(interaction, search)
    await interaction.followup.send("🔎 ดำเนินการค้นหาเรียบร้อย!", ephemeral=True)

@bot.tree.command(name="skip", description="ข้ามเพลง")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message(embed=discord.Embed(description="⏭️ **ข้ามเพลงแล้ว!**", color=0xf39c12))
    else:
        await interaction.response.send_message("❌ ไม่มีอะไรให้ข้าม!")

@bot.tree.command(name="stop", description="หยุดและล้างคิว")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queue[interaction.guild_id] = []
        await vc.disconnect()
        await interaction.response.send_message(embed=discord.Embed(description="⏹️ **หยุดและล้างคิวเรียบร้อย**", color=0xe74c3c))
    else:
        await interaction.response.send_message("❌ ไม่ได้อยู่ในห้องเสียง")

@bot.tree.command(name="volume", description="ปรับระดับเสียง 0-100")
async def volume(interaction: discord.Interaction, level: int):
    if not 0 <= level <= 100:
        return await interaction.response.send_message("❌ ใส่เลข 0 ถึง 100!")
    
    bot.volume[interaction.guild_id] = level / 100
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = level / 100
    await interaction.response.send_message(embed=discord.Embed(description=f"🔊 **ปรับเสียงเป็น {level}%**", color=0x9b59b6))

@bot.tree.command(name="queue", description="ดูรายการคิวเพลง")
async def queue(interaction: discord.Interaction):
    q = bot.queue.get(interaction.guild_id, [])
    if not q: return await interaction.response.send_message("❌ คิวว่าง!")
    
    embed = discord.Embed(title="📋 รายการคิว", color=0xf1c40f)
    embed.description = "\n".join([f"**{i+1}.** `{s['title']}`" for i, s in enumerate(q[:10])])
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="autoplay", description="เปิด/ปิด เล่นอัตโนมัติ")
async def toggle_autoplay(interaction: discord.Interaction):
    gid = interaction.guild_id
    current = bot.autoplay.get(gid, True)
    bot.autoplay[gid] = not current
    status = "เปิด ✅" if not current else "ปิด ❌"
    await interaction.response.send_message(embed=discord.Embed(description=f"📻 **Autoplay: {status}**", color=0x1abc9c))

bot.run(TOKEN)
