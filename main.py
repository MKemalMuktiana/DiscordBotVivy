# ============================================================
# Vivy Remainder - Bot Pengingat Sesi TTRPG
# ------------------------------------------------------------
# Fungsi : Mengirim reminder otomatis ke channel Discord
#          sesuai jadwal mingguan (lihat config.py).
# Mode   : Fase LOKAL (belum ada web server untuk Render).
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

# ------------------------------------------------------------
# 2. Setup logging sederhana
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vivy")

# ------------------------------------------------------------
# 3. Buat Discord client
# ------------------------------------------------------------
# Intents.default() cukup, karena bot hanya kirim pesan (bukan baca chat).
intents = discord.Intents.default()
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


# ------------------------------------------------------------
# 5. Scheduler: dicek setiap 60 detik
# ------------------------------------------------------------
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
                await channel.send(pesan)
                sudah_terkirim.add(kunci)
                logger.info(f"Terkirim: {pesan}")
            except Exception as e:
                # Jika gagal (mis. channel tak ditemukan), catat errornya.
                logger.error(f"Gagal kirim: {e}")


# ------------------------------------------------------------
# 6. Web server sederhana untuk Render (opsional)
# ------------------------------------------------------------
async def handle_root(request):
    return web.Response(text="Vivy Remainder Bot is running!")

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
# 7. Root handler untuk web server (opsional, bisa diakses via browser)
#------------------------------------------------------------

async def utama():
    await asyncio.gather(
        jalankan_bot(),
        client.start(TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(utama())