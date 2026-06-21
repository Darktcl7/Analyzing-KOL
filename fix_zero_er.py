import json
import os
from apify_scraper import ApifyInstagramScraper

def fix_zero_er():
    print("="*60)
    print(" MEMULAI PERBAIKAN DATA ER 0.0% ")
    print("="*60)
    
    filename = 'influencers.json'
    if not os.path.exists(filename):
        print("Database belum ada.")
        return
        
    with open(filename, 'r', encoding='utf-8') as f:
        kols = json.load(f)
        
    zero_er_usernames = [k['username'] for k in kols if k.get('er') == '0.0%']
    print(f"Ditemukan {len(zero_er_usernames)} data dengan ER 0.0%.")
    
    if not zero_er_usernames:
        print("Semua data ER sudah valid!")
        return
        
    scraper = ApifyInstagramScraper()
    
    # Process in smaller batches to avoid losing too much if it crashes
    batch_size = 50
    for i in range(0, len(zero_er_usernames), batch_size):
        batch = zero_er_usernames[i:i+batch_size]
        print(f"\nMemproses batch {i//batch_size + 1}: {len(batch)} profil...")
        
        try:
            results = scraper.scrape_profiles_parallel(batch)
            if results:
                scraper.save_results(results, filename)
                print(f"Berhasil memperbarui {len(results)} profil.")
        except Exception as e:
            print(f"Error memproses batch: {e}")

if __name__ == "__main__":
    fix_zero_er()
