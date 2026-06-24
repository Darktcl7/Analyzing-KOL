"""
Script lengkap untuk:
1. Re-scrape SEMUA akun yang ada untuk ambil caption hashtags dari postingan
2. Scrape influencer baru dari hashtag: #kulinermalang #influencermalang #standupcomedymalang #malangcontentcreator

Cara pakai: python full_rescrape_and_hashtag.py
"""
import json
import re
import os
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_FILE = 'influencers.json'
POSTS_TO_SCAN = 5

# Hashtag target yang diminta user
TARGET_HASHTAGS = ['kulinermalang', 'influencermalang', 'standupcomedymalang', 'malangcontentcreator']

try:
    from apify_client import ApifyClient
    from config import APIFY_API_TOKEN
    client = ApifyClient(APIFY_API_TOKEN)
except Exception as e:
    print(f"❌ Error import: {e}")
    sys.exit(1)

def load_data():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_status(text, is_running=True):
    try:
        with open('scraping_status.json', 'w') as f:
            json.dump({'status': text, 'is_running': is_running, 'updated_at': datetime.now().isoformat()}, f)
    except: pass


# =============================================
# TAHAP 1: Re-scrape semua akun existing
# =============================================
def rescrape_all_existing():
    """Re-scrape semua profil yang sudah ada untuk mendapatkan caption hashtags"""
    data = load_data()
    
    # Filter yang belum punya caption_hashtags dari postingan (yang kosong atau hanya dari bio)
    all_usernames = [inf.get('username', '') for inf in data if inf.get('username')]
    
    print(f"\n{'='*60}")
    print(f"TAHAP 1: RE-SCRAPE {len(all_usernames)} AKUN UNTUK CAPTION HASHTAGS")
    print(f"{'='*60}")
    
    batch_size = 50
    total_updated = 0
    
    for i in range(0, len(all_usernames), batch_size):
        batch_usernames = all_usernames[i:i+batch_size]
        urls = [f"https://www.instagram.com/{u}/" for u in batch_usernames]
        
        batch_num = i // batch_size + 1
        total_batches = (len(all_usernames) + batch_size - 1) // batch_size
        
        status_msg = f"Re-scrape batch {batch_num}/{total_batches} ({i+1}-{min(i+len(batch_usernames), len(all_usernames))}/{len(all_usernames)})"
        print(f"\n🔄 {status_msg}...")
        update_status(status_msg)
        
        run_input = {
            "directUrls": urls,
            "resultsType": "details"
        }
        
        try:
            run = client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            
            # Group items by username
            profile_items = {}
            for item in items:
                username = item.get('username', '').lower()
                if username:
                    if username not in profile_items:
                        profile_items[username] = []
                    profile_items[username].append(item)
            
            # Proses setiap profil
            for inf in data:
                u = inf.get('username', '').lower()
                if u in profile_items:
                    p_items = profile_items[u]
                    
                    # Kumpulkan postingan
                    posts = []
                    for item in p_items:
                        if 'latestPosts' in item:
                            posts.extend(item['latestPosts'])
                        elif item.get('type') in ['Image', 'Video', 'Sidecar'] or item.get('shortCode'):
                            posts.append(item)
                    
                    # Ekstrak hashtag dari caption postingan
                    caption_hashtags = set()
                    for p in posts[:POSTS_TO_SCAN]:
                        caption = (p.get('caption') or '').lower()
                        found = re.findall(r'#(\w+)', caption)
                        caption_hashtags.update(found)
                    
                    # Tambah hashtag dari bio
                    bio = inf.get('bio', '')
                    bio_ht = re.findall(r'#(\w+)', bio.lower())
                    caption_hashtags.update(bio_ht)
                    
                    inf['caption_hashtags'] = sorted(caption_hashtags)
                    total_updated += 1
                    
                    ht_display = sorted(caption_hashtags)[:5]
                    print(f"  ✅ @{inf.get('username', '?')}: {ht_display}{'...' if len(caption_hashtags) > 5 else ''}")
                    
        except Exception as e:
            print(f"  ❌ Error batch {batch_num}: {e}")
        
        # Simpan progress setiap batch
        save_data(data)
        print(f"  💾 Progress disimpan ({total_updated} ter-update)")
        time.sleep(1)
    
    print(f"\n✅ TAHAP 1 SELESAI! {total_updated}/{len(all_usernames)} akun ter-update.")
    return data


# =============================================
# TAHAP 2: Scrape hashtag baru
# =============================================
def scrape_new_hashtags():
    """Scrape influencer baru dari hashtag target"""
    data = load_data()
    existing_usernames = {inf.get('username', '').lower() for inf in data}
    
    print(f"\n{'='*60}")
    print(f"TAHAP 2: SCRAPE HASHTAG BARU")
    print(f"Target: #{', #'.join(TARGET_HASHTAGS)}")
    print(f"{'='*60}")
    
    # Import scraper
    from apify_scraper import ApifyInstagramScraper
    scraper = ApifyInstagramScraper()
    
    total_new = 0
    
    for hashtag in TARGET_HASHTAGS:
        print(f"\n🔍 Scraping #{hashtag}...")
        update_status(f"Scraping hashtag #{hashtag}...")
        
        try:
            new_kols = scraper.scrape_hashtag(
                hashtag, 
                limit=30,           # Ambil 30 postingan per hashtag
                max_profiles=20,    # Maksimal 20 profil baru per hashtag
                skip_existing=True
            )
            
            if new_kols:
                total_new += len(new_kols)
                print(f"  ✅ #{hashtag}: {len(new_kols)} profil baru ditemukan!")
                for kol in new_kols:
                    print(f"    📌 @{kol.get('username', '?')} ({kol.get('followers', '?')} followers)")
                
                # Simpan ke data utama
                scraper.save_results(new_kols)
            else:
                print(f"  ⚪ #{hashtag}: tidak ada profil baru")
                
        except Exception as e:
            print(f"  ❌ Error #{hashtag}: {e}")
        
        time.sleep(2)
    
    print(f"\n✅ TAHAP 2 SELESAI! {total_new} profil baru ditambahkan.")


# =============================================
# MAIN
# =============================================
if __name__ == '__main__':
    print("=" * 60)
    print("FULL RE-SCRAPE & HASHTAG DISCOVERY")
    print(f"Waktu mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    update_status("Memulai full re-scrape dan hashtag discovery...")
    
    # Tahap 1: Re-scrape semua akun existing
    rescrape_all_existing()
    
    # Tahap 2: Scrape hashtag baru
    scrape_new_hashtags()
    
    # Selesai
    update_status("Selesai! Semua akun sudah di-update dan hashtag baru sudah di-scrape.", False)
    
    # Summary
    data = load_data()
    has_ht = sum(1 for d in data if d.get('caption_hashtags'))
    print(f"\n{'='*60}")
    print(f"RINGKASAN")
    print(f"{'='*60}")
    print(f"Total influencer: {len(data)}")
    print(f"Punya caption hashtags: {has_ht}")
    print(f"Waktu selesai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
