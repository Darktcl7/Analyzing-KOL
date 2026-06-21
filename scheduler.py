"""
BACKGROUND SCHEDULER - KOL Scouting Project
===========================================
Script ini berfungsi untuk menjalankan proses scraping secara otomatis dan berkala
di latar belakang, sehingga database KOL selalu terupdate tanpa menunggu user.

Cara pakai:
1. Jalankan script ini di terminal terpisah:
   python scheduler.py

2. Biarkan berjalan. Script akan melakukan scraping setiap interval waktu tertentu.
"""

import time
import subprocess
import datetime
import sys
import random

# Konfigurasi
SCRAPE_INTERVAL_HOURS = 6  # Scrape setiap 6 jam
TARGET_REGIONS = [
    # Daerah prioritas tinggi (scrape lebih sering)
    ["Bali", "Denpasar", "Jakarta", "Surabaya"],
    # Daerah prioritas menengah
    ["Bandung", "Yogyakarta", "Semarang", "Malang"],
    # Daerah prioritas rendah
    ["Medan", "Makassar", "Palembang", "Lombok"]
]

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_scrape_job():
    log("🚀 Memulai Scheduled Scraping...")
    
    # Pilih group regio secara bergantian/acak agar tidak terlalu berat
    regions_to_scrape = random.choice(TARGET_REGIONS)
    regions_str = ", ".join(regions_to_scrape)
    
    log(f"📍 Target Daerah: {regions_str}")
    
    try:
        # Jalankan mass_scrape.py sebagai subprocess
        # Menggunakan python executable yang sama dengan script ini
        cmd = [sys.executable, "mass_scrape.py", str(len(regions_to_scrape)), "50"]
        
        # Kita perlu modifikasi mass_scrape.py sedikit agar bisa menerima list regions via argumen 
        # atau kita biarkan mass_scrape.py default (scrape top N regions)
        # Untuk saat ini, kita jalankan mass_scrape default
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Stream output
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   | {output.strip()}")
                
        rc = process.poll()
        if rc == 0:
            log("✅ Scraping selesai sukses!")
        else:
            log(f"⚠️ Scraping selesai dengan exit code: {rc}")
            
    except Exception as e:
        log(f"❌ Error menjalankan scraping: {e}")

def main():
    log("=== KOL SCAROUTING SCHEDULER STARTED ===")
    log(f"Interval: Setiap {SCRAPE_INTERVAL_HOURS} jam")
    
    # Jalankan sekali saat startup
    run_scrape_job()
    
    while True:
        # Hitung waktu tidur
        sleep_seconds = SCRAPE_INTERVAL_HOURS * 3600
        
        next_run = datetime.datetime.now() + datetime.timedelta(seconds=sleep_seconds)
        log(f"💤 Tidur hingga {next_run.strftime('%H:%M:%S')}...")
        
        time.sleep(sleep_seconds)
        run_scrape_job()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 Scheduler dihentikan oleh user.")
