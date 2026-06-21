"""
MASS SCRAPER - Scrape KOL dari semua Provinsi/Kota Indonesia
=============================================================
Script ini akan scrape KOL dari berbagai daerah Indonesia secara masif.
WARNING: Akan menghabiskan kredit Apify!
"""

import json
import time
from apify_scraper import ApifyInstagramScraper

# Daerah prioritas untuk scraping
PRIORITY_REGIONS = [
    # Format: (nama_lokasi, hashtag_variations)
    ("Bali", ["bali", "explorebali", "balidaily"]),
    ("Denpasar", ["denpasar", "exploredenpasar", "denpasarbali"]),
    ("Ubud", ["ubud", "explorubud", "ubudbali"]),
    ("Surabaya", ["surabaya", "exploresurabaya", "surabayahits"]),
    ("Jakarta", ["jakarta", "explorejakarta", "jakartahits"]),
    ("Bandung", ["bandung", "explorebandung", "bandunghits"]),
    ("Yogyakarta", ["jogja", "explorejogja", "jogjakarta"]),
    ("Semarang", ["semarang", "exploresemarang", "semaranghits"]),
    ("Malang", ["malang", "exploremalang", "malanghits"]),
    ("Medan", ["medan", "exploremedanhits", "medankota"]),
    ("Makassar", ["makassar", "exploremakassar"]),
    ("Palembang", ["palembang", "explorepalembang"]),
    ("Lombok", ["lombok", "explorelombok"]),
]

def run_mass_scrape(max_regions=5, limit_per_hashtag=50):
    """
    Run mass scraping untuk beberapa region.
    
    Args:
        max_regions: Jumlah region yang akan di-scrape
        limit_per_hashtag: Limit posts per hashtag
    """
    print("="*60)
    print("MASS SCRAPER - KOL Indonesia")
    print("="*60)
    
    scraper = ApifyInstagramScraper()
    all_kols = []
    
    for i, (location, hashtags) in enumerate(PRIORITY_REGIONS[:max_regions]):
        print(f"\n[{i+1}/{max_regions}] Scraping: {location}")
        print("-"*40)
        
        # 1. Scrape by hashtags
        print(f"  Hashtags: {hashtags}")
        try:
            kols = scraper.scrape_hashtags_batch(hashtags, limit_per_tag=limit_per_hashtag)
            if kols:
                all_kols.extend(kols)
                print(f"  [OK] Got {len(kols)} KOLs from hashtags")
        except Exception as e:
            print(f"  [ERROR] Hashtag scrape failed: {e}")
        
        # 2. Scrape by location
        print(f"  Location search: {location}")
        try:
            loc_kols = scraper.scrape_location(location, limit=30)
            if loc_kols:
                all_kols.extend(loc_kols)
                print(f"  [OK] Got {len(loc_kols)} KOLs from location")
        except Exception as e:
            print(f"  [ERROR] Location scrape failed: {e}")
        
        # Pause between regions to avoid rate limiting
        if i < max_regions - 1:
            print("  Waiting 5 seconds before next region...")
            time.sleep(5)
    
    # Deduplicate and save
    print("\n" + "="*60)
    print("SAVING RESULTS")
    print("="*60)
    
    if all_kols:
        # Dedupe
        seen = set()
        unique = []
        for k in all_kols:
            if k['username'] not in seen:
                unique.append(k)
                seen.add(k['username'])
        
        scraper.save_results(unique)
        print(f"\n[DONE] Total {len(unique)} unique KOLs scraped and saved!")
    else:
        print("\n[WARN] No KOLs found")
    
    return all_kols


if __name__ == "__main__":
    import sys
    
    # Default: scrape 3 regions, 30 posts per hashtag
    max_regions = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print(f"Config: {max_regions} regions, {limit} posts per hashtag")
    print("This will use Apify credits. Press Ctrl+C to cancel.\n")
    
    run_mass_scrape(max_regions=max_regions, limit_per_hashtag=limit)
