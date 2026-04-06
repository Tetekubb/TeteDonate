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
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

def format_time(seconds):
    return str(timedelta(seconds=seconds)).split('.')[0]

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.queue = {} # {guild_id: [songs]}
        self.autoplay = {} # {guild_id: bool}
        self.current_song = {} # {guild_id: song_info}
        self.volume = {} # {guild_id: float}

    async def setup_hook(self):
        static_ffmpeg.add_paths()
        await self.tree.sync()
        print(f"✅ บอทเพลงระบบเต็มรูปแบบออนไลน์แล้ว: {self.user}")

bot = MusicBot()

# --- [Helper: สร้าง Embed สุดเริ่ด] ---
def create_embed(song, status_text, color, interaction, volume=1.0):
    embed = discord.Embed(
        title=f"{status_text} {song['title']}",
        url=song['original_url'],
        color=color
    )
    # ดีไซน์ตามรูปตัวอย่างเป๊ะๆ
    embed.add_field(name="✨ เจ้าของเพลง", value=f"```fix\n{song['uploader']}```", inline=True)
    embed.add_field(name="⏰ ความยาว", value=f"```yaml\n{format_time(song['duration'])}```", inline=True)
    embed.add_field(name="👤 เพิ่มเพลงโดย", value=f"@{interaction.user.display_name}", inline=True)
    
    vc_name = interaction.user.voice.channel.name if interaction.user.voice else "Unknown"
    embed.add_field(name="🔊 ช่องเสียง", value=f"```bash\n# {vc_name}```", inline=True)
    embed.add_field(name="📊 ระดับเสียง", value=f"```python\n{int(volume*100)}%```", inline=True)
    embed.add_field(name="📻 Autoplay", value=f"```fix\n{'เปิด' if bot.autoplay.get(interaction.guild_id, True) else 'ปิด'}```", inline=True)

    if song.get('thumbnail'):
        embed.set_image(url=song['thumbnail'])
    
    embed.set_footer(text=f"Requested at {datetime.now().strftime('%H:%M:%S')}")
    return embed

# --- [Core Music Logic] ---
async def play_next(interaction):
    gid = interaction.guild_id
    vc = interaction.guild.voice_client
    if not vc: return

    if gid in bot.queue and bot.queue[gid]:
        song = bot.queue[gid].pop(0)
        bot.current_song[gid] = song
        
        source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
        # ปรับ Volume
        vol = bot.volume.get(gid, 1.0)
        vc.play(discord.PCMVolumeTransformer(source, volume=vol), 
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop))
        
        embed = create_embed(song, "🎶 กำลังเล่นเพลง", 0x2ecc71, interaction, volume=vol)
        await interaction.channel.send(embed=embed)

    elif bot.autoplay.get(gid, True) and gid in bot.current_song:
        # ระบบ Autoplay ค้นหาเพลงที่เกี่ยวข้อง
        last_song = bot.current_song[gid]
        await interaction.channel.send("🔄 *คิวหมดแล้ว กำลังหาเพลงที่คล้ายกันมาเล่นต่อ (Autoplay)...*")
        
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={last_song['id']}", download=False)
            related = info.get('related_videos', [])
            if related:
                next_url = f"https://www.youtube.com/watch?v={related[0]['id']}"
                # เรียกฟังก์ชันเล่นเพลงใหม่
                await play_logic(interaction, next_url, is_autoplay=True)

async def play_logic(interaction, search, is_autoplay=False):
    gid = interaction.guild_id
    vc = interaction.guild.voice_client

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info: info = info['entries'][0]
            song = {
                'url': info['url'], 'original_url': info.get('webpage_url'),
                'title': info['title'], 'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0), 'thumbnail': info.get('thumbnail'),
                'id': info.get('id')
            }
        except:
            return await interaction.channel.send("❌ ไม่พบเพลงที่ต้องการ!")

    if vc.is_playing() or vc.is_paused():
        if not is_autoplay:
            bot.queue.setdefault(gid, []).append(song)
            embed = create_embed(song, "✅ เพิ่มเข้าคิวแล้ว", 0x3498db, interaction, volume=bot.volume.get(gid, 1.0))
            await interaction.channel.send(embed=embed)
    else:
        bot.current_song[gid] = song
        vol = bot.volume.get(gid, 1.0)
        source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
        vc.play(discord.PCMVolumeTransformer(source, volume=vol), 
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop))
        
        embed = create_embed(song, "🎶 กำลังเล่นเพลง", 0x2ecc71, interaction, volume=vol)
        await interaction.channel.send(embed=embed)

# --- [Slash Commands] ---

@bot.tree.command(name="play", description="เล่นเพลง/เพิ่มคิว (Embed เริ่ดๆ)")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("❌ เข้าห้องเสียงก่อนดิ้!")
    
    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect(self_deaf=True)
    
    await play_logic(interaction, search)
    await interaction.followup.send("🔎 ดำเนินการเรียบร้อย!", ephemeral=True)

@bot.tree.command(name="skip", description="ข้ามเพลงปัจจุบัน")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        embed = discord.Embed(description="⏭️ **ข้ามเพลงเรียบร้อย!**", color=0xf39c12)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ ไม่มีเพลงเล่นอยู่!")

@bot.tree.command(name="stop", description="หยุดและล้างคิวทั้งหมด")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queue[interaction.guild_id] = []
        await vc.disconnect()
        embed = discord.Embed(description="⏹️ **หยุดเล่นและออกจากห้องแล้ว!**", color=0xe74c3c)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องเสียง!")

@bot.tree.command(name="volume", description="ปรับระดับเสียง (0-100)")
async def volume(interaction: discord.Interaction, level: int):
    if not 0 <= level <= 100:
        return await interaction.response.send_message("❌ ใส่ตัวเลข 0-100 ดิ้!")
    
    gid = interaction.guild_id
    bot.volume[gid] = level / 100
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = level / 100
    
    embed = discord.Embed(description=f"🔊 **ปรับระดับเสียงเป็น {level}% เรียบร้อย!**", color=0x9b59b6)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="queue", description="ดูรายการเพลงในคิว")
async def queue(interaction: discord.Interaction):
    q = bot.queue.get(interaction.guild_id, [])
    if not q:
        return await interaction.response.send_message("❌ คิวว่างเปล่า!")
    
    embed = discord.Embed(title="📋 รายการคิวเพลง", color=0xf1c40f)
    desc = ""
    for i, s in enumerate(q[:10], 1):
        desc += f"**{i}.** `{s['title']}` | {s['uploader']}\n"
    embed.description = desc
    if len(q) > 10:
        embed.set_footer(text=f"และอีก {len(q)-10} เพลงในคิว...")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="autoplay", description="เปิด/ปิด การเล่นอัตโนมัติ")
async def toggle_autoplay(interaction: discord.Interaction):
    gid = interaction.guild_id
    current = bot.autoplay.get(gid, True)
    bot.autoplay[gid] = not current
    status = "เปิด ✅" if not current else "ปิด ❌"
    embed = discord.Embed(description=f"📻 **Autoplay ตอนนี้: {status}**", color=0x1abc9c)
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
