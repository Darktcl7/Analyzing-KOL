import sys
import json
from apify_scraper import ApifyInstagramScraper

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("Mulai Deep Scrape untuk hashtag spesifik...")
    scraper = ApifyInstagramScraper()
    
    hashtags = [
        "influencermalang",
        "standupcomedymalang",
        "malangcontentcreator"
    ]
    
    # Ambil hingga 150 postingan per hashtag, dan maksimal 50 profil unik baru
    results = scraper.scrape_hashtags_batch(
        hashtags=hashtags, 
        limit_per_tag=150, 
        max_profiles=50, 
        skip_existing=True
    )
    
    if results:
        print(f"Berhasil mengumpulkan {len(results)} profil KOL baru dari hashtag-hashtag tersebut!")
    else:
        print("Tidak ada profil KOL baru (atau semua profil sudah ada di database / difilter karena di luar Malang).")

if __name__ == "__main__":
    main()
