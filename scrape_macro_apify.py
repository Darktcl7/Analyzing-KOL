import json
import re
import sys
from apify_client import ApifyClient
from config import APIFY_API_TOKEN
from apify_scraper import ApifyInstagramScraper

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("Mencari Selebgram/Artis/Influencer Besar Malang melalui Google Search...")
    client = ApifyClient(APIFY_API_TOKEN)
    
    queries = [
        'site:instagram.com "selebgram malang"',
        'site:instagram.com "artis malang"',
        'site:instagram.com "influencer malang" "k followers" OR "m followers"',
        'site:instagram.com "public figure" "malang"',
        'site:instagram.com "content creator malang" "k followers"'
    ]
    
    run_input = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": 2,
        "resultsPerPage": 100,
    }
    
    print("Menjalankan Google Search Scraper...")
    try:
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print("Error Google Search:", e)
        return
        
    usernames = set()
    for item in items:
        for res in item.get('organicResults', []):
            url = res.get('url', '')
            title = res.get('title', '')
            
            # 1. Coba ambil dari URL jika berupa profil
            match_url = re.search(r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?(?:\?|$)', url)
            if match_url:
                username = match_url.group(1)
                if username not in ['p', 'explore', 'tags', 'reel', 'reels', 'stories', 'tv', 'channel']:
                    usernames.add(username)
            
            # 2. Coba ambil dari Title
            match_title = re.search(r'@([a-zA-Z0-9_.]+)', title)
            if match_title:
                usernames.add(match_title.group(1).lower())
                    
    print(f"Ditemukan {len(usernames)} username potensial dari Google.")
    
    if usernames:
        print("Memulai scraping profil (mencari follower besar)...")
        scraper = ApifyInstagramScraper()
        
        # Filter existing
        existing = []
        try:
            with open('influencers.json', 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except: pass
        existing_usernames = {inf.get('username') for inf in existing}
        
        new_usernames = [u for u in usernames if u not in existing_usernames]
        print(f"Ada {len(new_usernames)} profil yang benar-benar baru.")
        
        if new_usernames:
            new_usernames = new_usernames[:70]  # Batasi agar tidak terlalu lama
            results = scraper.scrape_profiles_parallel(new_usernames)
            if results:
                print(f"Berhasil menambahkan {len(results)} profil artis/selebgram baru ke database!")
            else:
                print("Tidak ada profil baru yang berhasil didapat (mungkin karena filter area Malang atau hal lain).")
        else:
            print("Semua profil artis tersebut sudah ada di database.")

if __name__ == "__main__":
    main()
