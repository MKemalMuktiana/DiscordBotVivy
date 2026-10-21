# ============================================================
# Vivy Remainder - Bot Pengingat Sesi TTRPG
# ------------------------------------------------------------
# Fungsi : Mengirim reminder otomatis ke channel Discord
#          sesuai jadwal mingguan (lihat config.py).
#          Saat ini men-tag role; rencana ke depan men-tag user.
# Mode   : Bot + web server (aiohttp) berjalan bersamaan untuk Render.
# ============================================================

import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import discord
from discord.ext import tasks
from aiohttp import web

# Ambil daftar jadwal & timezone dari config.py
from config import REMINDERS, TIMEZONE

# ------------------------------------------------------------
# 1. Load kredensial dari file .env
# ------------------------------------------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")          # token bot (rahasia)
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))   # ID channel tujuan (dikonversi ke int)
ROLE_ID = int(os.getenv("ROLE_ID"))         # ID role yang ingin disebutkan (dikonversi ke int)
# ------------------------------------------------------------
# 2. Setup logging sederhana
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vivy")


# ------------------------------------------------------------
# 3. Buat Discord client
# ------------------------------------------------------------
# Intents.default() memberi izin dasar; message_content WAJIB dinyalakan
# agar bot bisa membaca isi pesan (mis. pesan daftar ID di channel brankas).
# Ingat: selain di sini, intent ini juga harus di-ON-kan di Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True  # wajib untuk membaca isi pesan (bukan opsional)
client = discord.Client(intents=intents)

# Penanda anti-dobel: menyimpan kunci reminder yang sudah terkirim
# agar tidak dikirim dua kali pada menit yang sama.
sudah_terkirim = set()


# ------------------------------------------------------------
# 4. Event on_ready: dipanggil sekali saat bot berhasil login
# ------------------------------------------------------------
@client.event
async def on_ready():
    logger.info(f"Vivy hidup! Login sebagai {client.user}")
    # Mulai scheduler hanya jika belum berjalan (hindari double-start).
    if not cek_jadwal.is_running():
        cek_jadwal.start()

# @client.event
# async def on_message(message):
#     if message.content.startswith('hello'):
#         await message.channel.send(f'Hello there {message.author}!') # respond with "Hello!" if the message starts with "!hello"

# ------------------------------------------------------------
# 5. Scheduler: dicek setiap 60 detik
# ------------------------------------------------------------

# Membentuk teks mention role dari ID-nya (format Discord: <@&ID>).
def MentionRole(ROLE_ID):
    return f"<@&{ROLE_ID}>"

# Aturan mention: everyone dimatikan (hindari ping massal), role diizinkan.
allowed_mentions = discord.AllowedMentions(everyone=False, roles=True)

# Membentuk embed pesan reminder (judul, warna, gambar, footer, author).
def pesan_embed(pesan):
    embed = discord.Embed(title="Reminder", description=pesan, color=discord.Color.blue())
    embed.set_thumbnail(url="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExdzN3eWE2NHVkczd2ZDZxZzdkYzZzbThkcnQ5d2JmOGozOGZlbGNzMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/RVy3XU9pV1euIO3bsR/giphy.gif")
    embed.set_image(url="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExNXFveXlzc2M4emlva3BsM3YzbG16eWdsZDI1OWkxOWZheDFwcmh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/10y00L5OqWgHD2/giphy.gif")
    embed.set_footer(text="See you!")
    embed.set_author(name=client.user.name, icon_url=client.user.display_avatar.url) #  set bot's as author
    return embed

@tasks.loop(seconds=60)

async def cek_jadwal():
    # Ambil waktu sekarang sesuai timezone WIB (bukan UTC).
    sekarang = datetime.now(ZoneInfo(TIMEZONE))
    logger.info(f"Tick: {sekarang}")

    # Cocokkan waktu sekarang dengan setiap jadwal di config.py
    for hari, jam, menit, pesan in REMINDERS:
        if (
            sekarang.weekday() == hari   # hari cocok (0=Senin ... 6=Minggu)
            and sekarang.hour == jam     # jam cocok
            and sekarang.minute == menit # menit cocok
        ):
            # Kunci unik per reminder per hari (mis. "2025-06-13-21:0")
            kunci = f"{sekarang.strftime('%Y-%m-%d')}-{jam}:{menit}"
            if kunci in sudah_terkirim:
                continue  # sudah terkirim menit ini, lewati

            try:
                # Ambil objek channel lalu kirim pesan reminder.
                channel = await client.fetch_channel(CHANNEL_ID)
                await channel.send(embed=pesan_embed(pesan), content=MentionRole(ROLE_ID), allowed_mentions=allowed_mentions)
                sudah_terkirim.add(kunci)
                logger.info(f"Terkirim: {pesan}")
            except Exception as e:
                # Jika gagal (mis. channel tak ditemukan), catat errornya.
                logger.error(f"Gagal kirim: {e}")


# ------------------------------------------------------------
# 6. Web server sederhana untuk Render (opsional)
# ------------------------------------------------------------
# Handler endpoint GET "/": membalas teks agar service bisa di-ping.
async def handle_root(request):
    return web.Response(text="Vivy Remainder Bot is running!")

# Menjalankan web server aiohttp di port dari env PORT (fallback 8080).
async def jalankan_bot():
    app = web.Application()
    app.router.add_get("/", handle_root)
    
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server berjalan di port {port}")

    while True:
        await asyncio.sleep(3600)  # loop utama, biarkan web server berjalan


#------------------------------------------------------------
# 7. Entry point: jalankan web server & bot Discord bersamaan
#------------------------------------------------------------

# Menjalankan web server (jalankan_bot) dan bot (client.start) dalam satu event loop.
async def utama():
    await asyncio.gather(
        jalankan_bot(),
        client.start(TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(utama())