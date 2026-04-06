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

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# ฟังก์ชันแปลงวินาทีเป็นรูปแบบ HH:MM:SS
def format_time(seconds):
    return str(timedelta(seconds=seconds)).split('.')[0]

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.queue = {} # {guild_id: [songs]}
        self.is_autoplay = {} # {guild_id: bool}
        self.volume = {} # {guild_id: float}

    async def setup_hook(self):
        static_ffmpeg.add_paths()
        await self.tree.sync()
        print(f"🚀 บอทเพลง Full Function (Fancy Embed) ออนไลน์แล้วในชื่อ {self.user}")

bot = MusicBot()

# --- [Helper Functions: Embed Generator] ---

def create_fancy_embed(song, status_text, color, interaction):
    gid = interaction.guild_id
    vol = bot.volume.get(gid, 1.0)
    
    embed = discord.Embed(
        title=f"{status_text} {song['title']}",
        url=f"https://www.youtube.com/watch?v={song['id']}",
        color=color
    )
    
    # จัดวาง Field ตามรูปแบบที่คุณต้องการ
    embed.add_field(name="✨ เจ้าของเพลง", value=f"```fix\n{song['uploader']}```", inline=True)
    embed.add_field(name="⏰ ความยาว", value=f"```yaml\n{format_time(song['duration'])}```", inline=True)
    embed.add_field(name="👤 เพิ่มเพลงโดย", value=f"@{interaction.user.display_name}", inline=True)
    
    # ดึงชื่อห้องเสียงปัจจุบัน
    vc_name = interaction.user.voice.channel.name if interaction.user.voice else "Unknown"
    embed.add_field(name="🔊 ช่องเสียง", value=f"```bash\n# {vc_name}```", inline=True)
    embed.add_field(name="📊 ระดับเสียง", value=f"```python\n{int(vol*100)}%```", inline=True)
    embed.add_field(name="📻 Autoplay", value=f"```fix\n{'เปิด ✅' if bot.is_autoplay.get(gid, True) else 'ปิด ❌'}```", inline=True)

    if song.get('thumbnail'):
        embed.set_image(url=song['thumbnail'])
    
    embed.set_footer(text=f"Requested at {datetime.now().strftime('%H:%M:%S')}", icon_url=interaction.user.display_avatar.url)
    return embed

# --- [Core Logic: คงเดิมจากที่คุณให้มา] ---

async def get_autoplay_video(video_id):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            related = [v for v in info.get('entries', []) if v] or info.get('related_videos', [])
            if related:
                return {
                    'url': f"https://www.youtube.com/watch?v={related[0]['id']}",
                    'title': related[0]['title'],
                    'uploader': related[0].get('uploader', 'Unknown Artist'),
                    'duration': related[0].get('duration', 0),
                    'id': related[0]['id']
                }
        except: pass
    return None

async def play_music(interaction, song):
    guild_id = interaction.guild_id
    vc = interaction.guild.voice_client
    if not vc: return

    def after_playing(error):
        coro = check_queue(interaction, song.get('id'))
        asyncio.run_coroutine_threadsafe(coro, bot.loop)

    # ดึงค่าระดับเสียงจาก Dict
    vol = bot.volume.get(guild_id, 1.0)
    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
    
    # ใช้ PCMVolumeTransformer เพื่อให้ปรับเสียงได้
    transformed_source = discord.PCMVolumeTransformer(source, volume=vol)
    vc.play(transformed_source, after=after_playing)
    
    # ส่ง Embed แบบใหม่ที่แต่งแล้ว
    embed = create_fancy_embed(song, "🎶 กำลังเล่นเพลง", 0x2ecc71, interaction)
    await interaction.channel.send(embed=embed)

async def check_queue(interaction, last_video_id):
    guild_id = interaction.guild_id
    vc = interaction.guild.voice_client
    if not vc: return

    if guild_id in bot.queue and bot.queue[guild_id]:
        next_song = bot.queue[guild_id].pop(0)
        await play_music(interaction, next_song)
    elif bot.is_autoplay.get(guild_id, True) and last_video_id:
        await interaction.channel.send("🔄 *คิวหมดแล้ว กำลังค้นหาเพลงที่เกี่ยวข้อง (Autoplay)...*")
        next_song = await get_autoplay_video(last_video_id)
        if next_song:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(next_song['url'], download=False)
                next_song['url'] = info['url']
                next_song['thumbnail'] = info.get('thumbnail')
            await play_music(interaction, next_song)

# --- [Slash Commands] ---

@bot.tree.command(name="play", description="เล่นเพลงจาก YouTube พร้อมระบบ Autoplay และ Embed สวยงาม")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("❌ คุณต้องอยู่ในห้องเสียงก่อน!")

    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect(self_deaf=True)

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info: info = info['entries'][0]
            song = {
                'url': info['url'],
                'title': info['title'],
                'uploader': info.get('uploader', 'ไม่ระบุ'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'id': info.get('id')
            }
        except Exception as e:
            return await interaction.followup.send(f"❌ หาเพลงไม่เจอ: {e}")

    if vc.is_playing() or vc.is_paused():
        bot.queue.setdefault(interaction.guild_id, []).append(song)
        # ใช้ Embed แบบสวยตอนเพิ่มคิวด้วย
        embed = create_fancy_embed(song, "✅ เพิ่มเข้าคิวแล้ว", 0x3498db, interaction)
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("🔎 กำลังเตรียมการเล่น...", ephemeral=True)
        await play_music(interaction, song)

@bot.tree.command(name="volume", description="ปรับระดับเสียง (0-100)")
async def volume(interaction: discord.Interaction, level: int):
    if not 0 <= level <= 100:
        return await interaction.response.send_message("❌ กรุณาใส่ตัวเลข 0-100!")
    
    gid = interaction.guild_id
    bot.volume[gid] = level / 100
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = level / 100 # ปรับความดังทันที
    
    embed = discord.Embed(description=f"🔊 **ปรับระดับเสียงเป็น {level}% เรียบร้อย!**", color=0x9b59b6)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="queue", description="ดูรายการเพลงในคิวปัจจุบัน")
async def queue(interaction: discord.Interaction):
    q = bot.queue.get(interaction.guild_id, [])
    if not q:
        return await interaction.response.send_message("❌ ตอนนี้ยังไม่มีเพลงในคิวครับ")
    
    embed = discord.Embed(title="📋 รายการเพลงในคิว", color=0xf1c40f)
    desc = ""
    for i, song in enumerate(q[:10], 1):
        desc += f"**{i}.** `{song['title']}` | {song['uploader']}\n"
    embed.description = desc
    if len(q) > 10:
        embed.set_footer(text=f"และยังมีอีก {len(q)-10} เพลงในคิว")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="skip", description="ข้ามเพลงปัจจุบัน")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message(embed=discord.Embed(description="⏭️ **ข้ามเพลงเรียบร้อย!**", color=0xe67e22))
    else:
        await interaction.response.send_message("❌ ไม่มีเพลงเล่นอยู่")

@bot.tree.command(name="autoplay", description="เปิด/ปิด ระบบเล่นเพลงต่ออัตโนมัติ")
async def autoplay(interaction: discord.Interaction):
    gid = interaction.guild_id
    current = bot.is_autoplay.get(gid, True)
    bot.is_autoplay[gid] = not current
    status = "เปิด ✅" if bot.is_autoplay[gid] else "ปิด ❌"
    await interaction.response.send_message(embed=discord.Embed(description=f"📻 **ระบบ Autoplay ตอนนี้: {status}**", color=0x1abc9c))

@bot.tree.command(name="stop", description="หยุดและออกจากห้องเสียง")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queue[interaction.guild_id] = []
        await vc.disconnect()
        await interaction.response.send_message(embed=discord.Embed(description="⏹️ **หยุดเล่นและออกจากห้องแล้ว!**", color=0xe74c3c))
    else:
        await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องเสียง")

bot.run(TOKEN)
