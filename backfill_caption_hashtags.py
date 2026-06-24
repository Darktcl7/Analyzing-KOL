"""
Script migrasi untuk backfill caption_hashtags pada data influencer yang sudah ada.
Menggunakan Apify untuk re-scrape postingan terbaru dan mengekstrak hashtag dari caption.

Cara pakai: python backfill_caption_hashtags.py
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

def extract_bio_hashtags(bio):
    """Ekstrak hashtag dari bio saja (tanpa perlu API call)"""
    return sorted(set(re.findall(r'#(\w+)', bio.lower())))

def backfill_from_bio():
    """
    Fase 1: Backfill caption_hashtags dari bio yang sudah ada.
    Ini gratis (tidak pakai API) dan bisa langsung jalan.
    """
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated = 0
    for inf in data:
        if 'caption_hashtags' not in inf or not inf['caption_hashtags']:
            bio = inf.get('bio', '')
            hashtags = extract_bio_hashtags(bio)
            inf['caption_hashtags'] = hashtags
            updated += 1
            if hashtags:
                print(f"  @{inf.get('username', '?')}: {hashtags[:10]}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Selesai! {updated} influencer di-update dengan hashtag dari bio.")
    return data

def backfill_from_apify(batch_size=50, max_profiles=None):
    """
    Fase 2: Re-scrape postingan terbaru dari Apify untuk mendapat caption hashtags.
    Ini MEMBUTUHKAN Apify API credit.
    """
    try:
        from apify_client import ApifyClient
        from config import APIFY_API_TOKEN
    except ImportError:
        print("❌ apify_client belum terinstall. Jalankan: pip install apify-client")
        return
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Filter influencer yang belum punya caption_hashtags atau yang hashtag-nya kosong
    need_update = [inf for inf in data if not inf.get('caption_hashtags')]
    
    if max_profiles:
        need_update = need_update[:max_profiles]
    
    if not need_update:
        print("✅ Semua influencer sudah punya caption_hashtags!")
        return
    
    print(f"📋 {len(need_update)} influencer perlu di-update via Apify")
    
    client = ApifyClient(APIFY_API_TOKEN)
    total_updated = 0
    
    # Proses dalam batch
    for i in range(0, len(need_update), batch_size):
        batch = need_update[i:i+batch_size]
        usernames = [inf.get('username', '') for inf in batch]
        urls = [f"https://www.instagram.com/{u}/" for u in usernames if u]
        
        print(f"\n🔄 Batch {i//batch_size + 1}: Scraping {len(urls)} profil...")
        
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
            
            # Ekstrak caption hashtags untuk setiap profil
            for inf in batch:
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
                    
                    if caption_hashtags:
                        print(f"  ✅ @{inf.get('username', '?')}: {sorted(caption_hashtags)[:8]}...")
                    else:
                        print(f"  ⚪ @{inf.get('username', '?')}: tidak ada hashtag")
                        
        except Exception as e:
            print(f"  ❌ Error batch: {e}")
        
        # Simpan progress setiap batch
        # Update data utama
        username_map = {inf.get('username', ''): inf for inf in batch}
        for idx, d in enumerate(data):
            u = d.get('username', '')
            if u in username_map:
                data[idx] = username_map[u]
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  💾 Progress disimpan ({total_updated} ter-update)")
        time.sleep(2)  # Rate limiting
    
    print(f"\n✅ Selesai! {total_updated} influencer di-update dengan caption hashtags dari Apify.")


if __name__ == '__main__':
    print("=" * 60)
    print("BACKFILL CAPTION HASHTAGS")
    print("=" * 60)
    
    # Fase 1: Gratis - ekstrak hashtag dari bio
    print("\n📌 Fase 1: Backfill dari Bio (gratis, tanpa API)...")
    backfill_from_bio()
    
    # Fase 2: Apify re-scrape (opsional)
    if '--apify' in sys.argv:
        print("\n📌 Fase 2: Re-scrape dari Apify (butuh API credit)...")
        max_p = None
        for arg in sys.argv:
            if arg.startswith('--max='):
                max_p = int(arg.split('=')[1])
        backfill_from_apify(max_profiles=max_p)
    else:
        print("\n💡 Untuk re-scrape caption dari Apify, jalankan:")
        print("   python backfill_caption_hashtags.py --apify")
        print("   python backfill_caption_hashtags.py --apify --max=50  (limit 50 profil)")
