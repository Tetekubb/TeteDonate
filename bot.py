import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")
PREFIX = os.environ.get("PREFIX", "!")

# ─── YTDLP OPTIONS ────────────────────────────────────────────────────────────
YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "opus",
    }],
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -filter:a 'volume=0.5'",
}

# ─── INTENTS ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ─── GUILD STATE ──────────────────────────────────────────────────────────────
# guild_id -> { queue, loop, loop_queue, current, volume, text_channel }
guild_states: dict = {}

def get_state(guild_id):
    if guild_id not in guild_states:
        guild_states[guild_id] = {
            "queue": deque(),
            "loop": False,
            "loop_queue": False,
            "current": None,
            "volume": 0.5,
            "text_channel": None,
        }
    return guild_states[guild_id]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
async def fetch_info(query: str) -> list[dict]:
    """ดึงข้อมูลเพลงจาก YouTube"""
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
        if "youtube.com" in query or "youtu.be" in query or "soundcloud.com" in query:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        else:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch5:{query}", download=False))

    tracks = []

    if "entries" in info:
        for entry in info["entries"]:
            if entry:
                tracks.append({
                    "title": entry.get("title", "Unknown"),
                    "url": entry.get("url") or entry.get("webpage_url"),
                    "webpage_url": entry.get("webpage_url", ""),
                    "duration": entry.get("duration", 0),
                    "thumbnail": entry.get("thumbnail", ""),
                    "uploader": entry.get("uploader", "Unknown"),
                })
    else:
        tracks.append({
            "title": info.get("title", "Unknown"),
            "url": info.get("url") or info.get("webpage_url"),
            "webpage_url": info.get("webpage_url", ""),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
            "uploader": info.get("uploader", "Unknown"),
        })

    return tracks

def format_duration(seconds: int) -> str:
    if not seconds:
        return "🔴 Live"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

def play_next(guild_id, voice_client):
    """เล่นเพลงถัดไปใน queue"""
    state = get_state(guild_id)

    if state["loop"] and state["current"]:
        track = state["current"]
    elif state["loop_queue"] and state["current"]:
        state["queue"].append(state["current"])
        track = state["queue"].popleft() if state["queue"] else None
    elif state["queue"]:
        track = state["queue"].popleft()
    else:
        state["current"] = None
        # อยู่ในห้องต่อ ไม่ disconnect
        asyncio.run_coroutine_threadsafe(
            send_idle(guild_id), bot.loop
        )
        return

    state["current"] = track

    try:
        source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=state["volume"])
        voice_client.play(
            source,
            after=lambda e: play_next(guild_id, voice_client) if not e else print(f"Error: {e}")
        )
        asyncio.run_coroutine_threadsafe(
            send_now_playing(guild_id, track), bot.loop
        )
    except Exception as ex:
        print(f"[play_next] Error: {ex}")
        asyncio.run_coroutine_threadsafe(
            send_error(guild_id, str(ex)), bot.loop
        )

async def send_now_playing(guild_id, track):
    state = get_state(guild_id)
    ch = state.get("text_channel")
    if not ch:
        return
    em = discord.Embed(
        title="🎵 กำลังเล่น",
        description=f"**[{track['title']}]({track['webpage_url']})**",
        color=0x1DB954,
    )
    em.add_field(name="⏱ ความยาว", value=format_duration(track["duration"]))
    em.add_field(name="👤 ช่อง", value=track["uploader"])
    if track.get("thumbnail"):
        em.set_thumbnail(url=track["thumbnail"])
    loop_status = "🔂 Loop เพลง" if state["loop"] else ("🔁 Loop Queue" if state["loop_queue"] else "▶️ ปกติ")
    em.set_footer(text=f"โหมด: {loop_status}")
    await ch.send(embed=em)

async def send_idle(guild_id):
    state = get_state(guild_id)
    ch = state.get("text_channel")
    if ch:
        em = discord.Embed(
            description="✅ **Queue หมดแล้ว** · บอทยังอยู่ในห้อง พร้อมเล่นเพลงใหม่ได้เลย!",
            color=0xFFA500,
        )
        await ch.send(embed=em)

async def send_error(guild_id, msg):
    state = get_state(guild_id)
    ch = state.get("text_channel")
    if ch:
        await ch.send(f"❌ เกิดข้อผิดพลาด: `{msg}`")

# ─── EVENTS ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} พร้อมแล้ว!")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name=f"{PREFIX}play | Music Bot")
    )

# ─── COMMANDS ─────────────────────────────────────────────────────────────────

@bot.command(name="play", aliases=["p"])
async def play(ctx, *, query: str):
    """เล่นเพลงหรือเพิ่มใน queue"""
    state = get_state(ctx.guild.id)
    state["text_channel"] = ctx.channel

    # Join voice channel
    if not ctx.author.voice:
        return await ctx.send("❌ คุณต้องอยู่ใน voice channel ก่อน!")

    vc = ctx.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()
    elif vc.channel != ctx.author.voice.channel:
        await vc.move_to(ctx.author.voice.channel)

    async with ctx.typing():
        try:
            tracks = await fetch_info(query)
        except Exception as e:
            return await ctx.send(f"❌ ไม่สามารถค้นหาเพลงได้: `{e}`")

    if not tracks:
        return await ctx.send("❌ ไม่พบเพลง")

    for track in tracks:
        state["queue"].append(track)

    if len(tracks) > 1:
        em = discord.Embed(
            title="📋 เพิ่ม Playlist แล้ว",
            description=f"เพิ่ม **{len(tracks)} เพลง** ลงใน queue",
            color=0x5865F2,
        )
        await ctx.send(embed=em)
    else:
        track = tracks[0]
        if vc.is_playing() or vc.is_paused():
            em = discord.Embed(
                description=f"✅ เพิ่ม **[{track['title']}]({track['webpage_url']})** ลงใน queue (ตำแหน่ง #{len(state['queue'])})",
                color=0x5865F2,
            )
            await ctx.send(embed=em)

    if not vc.is_playing() and not vc.is_paused():
        play_next(ctx.guild.id, vc)


@bot.command(name="skip", aliases=["s"])
async def skip(ctx):
    """ข้ามเพลงปัจจุบัน"""
    vc = ctx.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await ctx.message.add_reaction("⏭️")
    else:
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่นอยู่")


@bot.command(name="pause")
async def pause(ctx):
    """หยุดเพลงชั่วคราว"""
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.message.add_reaction("⏸️")
    else:
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่นอยู่")


@bot.command(name="resume", aliases=["r"])
async def resume(ctx):
    """เล่นเพลงต่อ"""
    vc = ctx.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.message.add_reaction("▶️")
    else:
        await ctx.send("❌ ไม่มีเพลงที่ถูก pause อยู่")


@bot.command(name="stop")
async def stop(ctx):
    """หยุดเพลงและล้าง queue"""
    state = get_state(ctx.guild.id)
    state["queue"].clear()
    state["current"] = None
    state["loop"] = False
    state["loop_queue"] = False

    vc = ctx.voice_client
    if vc:
        vc.stop()
    await ctx.send("⏹️ หยุดเพลงและล้าง queue แล้ว (บอทยังอยู่ในห้องนะ)")


@bot.command(name="queue", aliases=["q"])
async def queue(ctx):
    """ดู queue ปัจจุบัน"""
    state = get_state(ctx.guild.id)
    em = discord.Embed(title="📋 Queue", color=0x5865F2)

    if state["current"]:
        em.add_field(
            name="🎵 กำลังเล่น",
            value=f"**{state['current']['title']}** `{format_duration(state['current']['duration'])}`",
            inline=False,
        )

    if state["queue"]:
        lines = []
        for i, t in enumerate(list(state["queue"])[:15], 1):
            lines.append(f"`{i}.` {t['title']} `{format_duration(t['duration'])}`")
        if len(state["queue"]) > 15:
            lines.append(f"... และอีก {len(state['queue']) - 15} เพลง")
        em.add_field(name="⏭️ ถัดไป", value="\n".join(lines), inline=False)
    else:
        em.add_field(name="⏭️ ถัดไป", value="Queue ว่างเปล่า", inline=False)

    loop_status = "🔂 Loop เพลง" if state["loop"] else ("🔁 Loop Queue" if state["loop_queue"] else "▶️ ปกติ")
    em.set_footer(text=f"โหมด: {loop_status} · รวม {len(state['queue'])} เพลงใน queue")
    await ctx.send(embed=em)


@bot.command(name="loop", aliases=["l"])
async def loop_cmd(ctx, mode: str = None):
    """loop [off/song/queue] - ตั้งค่า loop"""
    state = get_state(ctx.guild.id)

    if mode is None:
        # Toggle
        if not state["loop"] and not state["loop_queue"]:
            state["loop"] = True
            await ctx.send("🔂 Loop เพลง: **เปิด**")
        elif state["loop"]:
            state["loop"] = False
            state["loop_queue"] = True
            await ctx.send("🔁 Loop Queue: **เปิด**")
        else:
            state["loop"] = False
            state["loop_queue"] = False
            await ctx.send("▶️ Loop: **ปิด**")
    elif mode.lower() in ("song", "เพลง", "1"):
        state["loop"] = True
        state["loop_queue"] = False
        await ctx.send("🔂 Loop เพลง: **เปิด**")
    elif mode.lower() in ("queue", "q", "2"):
        state["loop"] = False
        state["loop_queue"] = True
        await ctx.send("🔁 Loop Queue: **เปิด**")
    else:
        state["loop"] = False
        state["loop_queue"] = False
        await ctx.send("▶️ Loop: **ปิด**")


@bot.command(name="volume", aliases=["vol", "v"])
async def volume(ctx, vol: int = None):
    """ปรับระดับเสียง 0-200"""
    state = get_state(ctx.guild.id)
    vc = ctx.voice_client

    if vol is None:
        return await ctx.send(f"🔊 เสียงปัจจุบัน: **{int(state['volume'] * 100)}%**")

    vol = max(0, min(200, vol))
    state["volume"] = vol / 100

    if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = state["volume"]

    await ctx.send(f"🔊 ปรับเสียงเป็น **{vol}%**")


@bot.command(name="nowplaying", aliases=["np"])
async def nowplaying(ctx):
    """ดูเพลงที่กำลังเล่น"""
    state = get_state(ctx.guild.id)
    if not state["current"]:
        return await ctx.send("❌ ไม่มีเพลงที่กำลังเล่นอยู่")
    await send_now_playing(ctx.guild.id, state["current"])


@bot.command(name="shuffle")
async def shuffle(ctx):
    """สับ queue"""
    import random
    state = get_state(ctx.guild.id)
    if not state["queue"]:
        return await ctx.send("❌ Queue ว่างเปล่า")
    lst = list(state["queue"])
    random.shuffle(lst)
    state["queue"] = deque(lst)
    await ctx.send(f"🔀 สับ queue แล้ว ({len(lst)} เพลง)")


@bot.command(name="remove", aliases=["rm"])
async def remove(ctx, index: int):
    """ลบเพลงออกจาก queue ตามตำแหน่ง"""
    state = get_state(ctx.guild.id)
    if index < 1 or index > len(state["queue"]):
        return await ctx.send("❌ ตำแหน่งไม่ถูกต้อง")
    lst = list(state["queue"])
    removed = lst.pop(index - 1)
    state["queue"] = deque(lst)
    await ctx.send(f"🗑️ ลบ **{removed['title']}** ออกจาก queue แล้ว")


@bot.command(name="clear", aliases=["cl"])
async def clear_queue(ctx):
    """ล้าง queue"""
    state = get_state(ctx.guild.id)
    count = len(state["queue"])
    state["queue"].clear()
    await ctx.send(f"🗑️ ล้าง queue แล้ว ({count} เพลง)")


@bot.command(name="join", aliases=["j"])
async def join(ctx):
    """เรียกบอทเข้าห้อง"""
    if not ctx.author.voice:
        return await ctx.send("❌ คุณต้องอยู่ใน voice channel ก่อน!")
    vc = ctx.voice_client
    if vc:
        await vc.move_to(ctx.author.voice.channel)
    else:
        await ctx.author.voice.channel.connect()
    get_state(ctx.guild.id)["text_channel"] = ctx.channel
    await ctx.message.add_reaction("✅")


@bot.command(name="leave", aliases=["dc", "disconnect"])
async def leave(ctx):
    """ให้บอทออกจากห้อง"""
    state = get_state(ctx.guild.id)
    state["queue"].clear()
    state["current"] = None
    vc = ctx.voice_client
    if vc:
        await vc.disconnect()
        await ctx.message.add_reaction("👋")
    else:
        await ctx.send("❌ บอทไม่ได้อยู่ใน voice channel")


@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx):
    """แสดงคำสั่งทั้งหมด"""
    em = discord.Embed(title="🎵 Music Bot Commands", color=0x1DB954)
    em.add_field(name=f"`{PREFIX}play <ชื่อ/URL>`", value="เล่นเพลงหรือเพิ่มใน queue (YouTube / Playlist)", inline=False)
    em.add_field(name=f"`{PREFIX}skip`", value="ข้ามเพลงปัจจุบัน", inline=True)
    em.add_field(name=f"`{PREFIX}pause` / `resume`", value="หยุด / เล่นต่อ", inline=True)
    em.add_field(name=f"`{PREFIX}stop`", value="หยุดและล้าง queue", inline=True)
    em.add_field(name=f"`{PREFIX}queue`", value="ดู queue", inline=True)
    em.add_field(name=f"`{PREFIX}nowplaying`", value="เพลงที่กำลังเล่น", inline=True)
    em.add_field(name=f"`{PREFIX}loop [off/song/queue]`", value="ตั้งค่า loop", inline=True)
    em.add_field(name=f"`{PREFIX}volume <0-200>`", value="ปรับเสียง", inline=True)
    em.add_field(name=f"`{PREFIX}shuffle`", value="สับ queue", inline=True)
    em.add_field(name=f"`{PREFIX}remove <เลข>`", value="ลบเพลงใน queue", inline=True)
    em.add_field(name=f"`{PREFIX}clear`", value="ล้าง queue", inline=True)
    em.add_field(name=f"`{PREFIX}join` / `leave`", value="เรียก / ไล่บอทออกห้อง", inline=True)
    em.set_footer(text="บอทจะอยู่ในห้องตลอดแม้เพลงจบ ✅")
    await ctx.send(embed=em)


# ─── ERROR HANDLER ────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ ใส่ argument ไม่ครบ ลองใช้ `{PREFIX}help`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`")
        print(f"[Error] {error}")


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("❌ ตั้งค่า DISCORD_TOKEN environment variable ก่อน!")
    bot.run(TOKEN)
