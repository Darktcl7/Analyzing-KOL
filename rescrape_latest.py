import json
import sys
from apify_scraper import ApifyInstagramScraper

sys.stdout.reconfigure(encoding='utf-8')

def main():
    try:
        with open('influencers.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print("Error reading db:", e)
        return
        
    # Ambil 15 user terakhir yang baru saja ditambahkan untuk di-rescrape dengan limit POSTS_TO_SCAN=30
    recent_users = [d['username'] for d in data[-15:]]
    print("Merescrape ulang 15 user terakhir untuk mengambil hashtag dari 30 postingan (bukan cuma 5)...")
    print("Usernames:", recent_users)
    
    scraper = ApifyInstagramScraper()
    # Panggil fungsi scrape_profiles_parallel (itu akan otomatis menimpa data yang lama di DB)
    scraper.scrape_profiles_parallel(recent_users)
    print("Selesai rescrape!")

if __name__ == "__main__":
    main()
