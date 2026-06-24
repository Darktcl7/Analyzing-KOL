import os
import sys
from apify_scraper import ApifyInstagramScraper

def main():
    print("="*60)
    print(" MEMULAI SCRAPING HASHTAG KUSTOM ")
    print(" Hashtags: #kulinermalang, #influencermalang, #standupcomedymalang, #malangcontentcreator ")
    print(" Target Lokasi: Malang, Batu, Kepanjen ")
    print("="*60)

    # Inisialisasi scraper
    scraper = ApifyInstagramScraper()
    
    # Custom hashtags
    hashtags = [
        "kulinermalang", 
        "influencermalang", 
        "standupcomedymalang", 
        "malangcontentcreator"
    ]
    
    limit_per_tag = 120
    max_profiles = 100
    
    scraper.update_scrape_status("Menghubungkan ke Apify untuk menarik postingan hashtag kustom...", True)
    
    try:
        kols = scraper.scrape_hashtags_batch(
            hashtags,
            limit_per_tag=limit_per_tag,
            max_profiles=max_profiles,
            skip_existing=True
        )
        
        if kols:
            scraper.save_results(kols)
            msg = f"[BERHASIL] {len(kols)} KOL baru dari hashtag kustom berhasil dianalisis & disimpan."
            print(f"\n{msg}")
            scraper.update_scrape_status(msg, False)
            
            print("\nKOL Baru yang Ditemukan:")
            for kol in kols:
                print(f" - @{kol['username']} | Followers: {kol['followers']} | ER: {kol['er']} | Lokasi: {kol['location']}")
        else:
            msg = "[INFO] Tidak ada KOL baru yang didapatkan. Mungkin karena sudah terdaftar di database atau disaring karena lokasi."
            print(f"\n{msg}")
            scraper.update_scrape_status(msg, False)
            
    except Exception as e:
        msg = f"[ERROR] Terjadi kesalahan saat scraping: {str(e)}"
        print(f"\n{msg}")
        scraper.update_scrape_status(msg, False)

if __name__ == "__main__":
    main()
