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
        'site:instagram.com "#influencermalang"',
        'site:instagram.com "#malangcontentcreator"',
        'site:instagram.com/explore/tags/ "influencermalang"',
        'site:instagram.com/explore/tags/ "malangcontentcreator"',
        'site:instagram.com "influencer malang" after:2023-01-01',
        'site:instagram.com "content creator malang" after:2023-01-01',
        'site:instagram.com "#selebgrammalang"'
    ]
    
    run_input = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": 5,
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
                # Save to JSON!
                existing.extend(results)
                with open('influencers.json', 'w', encoding='utf-8') as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
                print(f"Berhasil menyimpan {len(results)} profil artis/selebgram baru ke influencers.json!")
            else:
                print("Tidak ada profil baru yang berhasil didapat (mungkin karena filter area Malang atau hal lain).")
        else:
            print("Semua profil artis tersebut sudah ada di database.")

if __name__ == "__main__":
    main()
