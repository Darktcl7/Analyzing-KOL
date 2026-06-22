"""
SCRAPER MALANG - FOKUS DETAIL 1 KOTA
====================================
Script ini dirancang untuk menyedot data KOL secara spesifik dan detail 
hanya untuk wilayah Malang dan sekitarnya (Batu, Kabupaten Malang).

Target Niche: Kuliner, Pariwisata, Mahasiswa, Beauty, dan Lifestyle.
"""

import time
from apify_scraper import ApifyInstagramScraper

def scrape_malang_detail():
    print("="*60)
    print(" MEMULAI SCRAPING MASSAL: FOKUS KOTA MALANG & BATU (TARGET 10K) ")
    print("="*60)
    
    # Inisialisasi scraper
    scraper = ApifyInstagramScraper()
    
    # Kumpulan hashtag SUPER DETAIL khusus Malang & Batu
    malang_hashtags = [
        # Niche Kuliner / F&B Malang
        "kulinermalang", "malangfoodies", "cafemalang", "malangculinary", "malanghits",
        
        # Niche Kuliner / F&B Batu & Sekitar
        "kulinerbatu", "explorebatu", "cafebatu", "batuculinary", "batufoodies",
        
        # Niche Pariwisata & Alam Malang, Batu, Bromo
        "exploremalang", "yoikimalang", "amazingmalang", "wisatamalang", "wisatabatu", "kotawisatabatu", "batuhits",
        "explorebromo", "wisatabromo", "bromotrip",
        
        # Niche Mahasiswa & Anak Muda Malang
        "mahasiswamalang", "kampusmalang", "infomalang", "mahasiswaub", "mahasiswaum", "mahasiswaumm", "mabaub", "mabaumm",
        
        # Niche Pendidikan, Buku, & Alat Tulis Malang
        "pendidikanmalang", "bukumalang", "alattulismalang", "tokobukumalang", "pelajarmalang", "sekolahmalang", "perpustakaanmalang", "stationerymalang",
        
        # Niche Teknologi & IT Malang
        "teknologimalang", "gadgetmalang", "komputermalang", "servicelaptopmalang", "servishpmalang", "iphonemalang", "codingmalang", "itmalang",
        
        # Niche Bisnis & Pemasaran Malang
        "bisnismalang", "umkmmalang", "pengusahamalang", "marketingmalang",
        
        # Niche Kesehatan Malang
        "kesehatanmalang", "doktermalang", "klinikmalang",
        
        # Niche Seni, Musik, & Fotografi Malang
        "senimalang", "musikmalang", "bandmalang", "fotografimalang", "jasafotomalang", "preweddingmalang",
        
        # Niche Otomotif Malang
        "otomotifmalang", "mobilmalang", "motormalang",
        
        # Niche Beauty & Fashion Malang & Batu
        "muamalang", "malangbeauty", "ootdmalang", "muabatu",
        
        # Niche Event & Lifestyle Malang, Batu, Kepanjen
        "eventmalang", "malangapik", "infobatu", "kepanjen", "explorekepanjen", "kepanjenhits", "kulinerkepanjen"
    ]
    
    # Konfigurasi Skala Besar
    LIMIT_POSTS = 150 
    MAX_PROFILES = 10000 
    
    print(f"\n[INFO] Target Hashtag: {len(malang_hashtags)} hashtags spesifik Malang & Batu")
    print(f"[INFO] Limit Post per hashtag: {LIMIT_POSTS}")
    print(f"[INFO] Maksimal Profil yg dicek detail: {MAX_PROFILES}\n")
    
    scraper.update_scrape_status("Menghubungkan ke Cloud Apify untuk menarik postingan dari hashtag...", True)
    
    try:
        # Menjalankan scrape secara batch (paralel)
        kols = scraper.scrape_hashtags_batch(
            malang_hashtags, 
            limit_per_tag=LIMIT_POSTS,
            max_profiles=MAX_PROFILES,
            skip_existing=True # Melewati yang sudah ada di database
        )
        
        if kols:
            scraper.update_scrape_status("Menyimpan hasil ke database lokal...", True)
            # Simpan hasil ke influencers.json
            scraper.save_results(kols)
            msg = f"[BERHASIL] {len(kols)} KOL baru berhasil ditambahkan ke database dengan detail ER & Followers."
            print(f"\n{msg}")
            scraper.update_scrape_status(msg, False)
            
            # Tampilkan sekilas hasilnya
            print("\nCuplikan Data Malang & Batu yang Didapat:")
            for kol in kols[:5]:
                print(f" - @{kol['username']} | Followers: {kol['followers']} | ER: {kol['er']} | Niche: {', '.join(kol['tags'])}")
        else:
            msg = "[PERINGATAN] Tidak ada KOL baru yang didapatkan. Mungkin karena batasan limit atau sudah ada di database."
            print(f"\n{msg}")
            scraper.update_scrape_status(msg, False)
            
    except Exception as e:
        msg = f"[ERROR] Terjadi Error saat scraping: {str(e)}"
        print(f"\n{msg}")
        print("Pastikan Token Apify Anda sudah dimasukkan dengan benar.")
        scraper.update_scrape_status(msg, False)
 
if __name__ == "__main__":
    scrape_malang_detail()
