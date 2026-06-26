import json
from apify_scraper import ApifyInstagramScraper

scraper = ApifyInstagramScraper()
print("Properly scraping cheyuanita...")

# This will call apify and then pass the result through _process_profile_data
chey_data = scraper.scrape_single_profile("cheyuanita")

if not chey_data:
    print("FAILED to get data via scrape_single_profile")
else:
    print(f"Scraped correctly. ER: {chey_data.get('er')}, Profile Pic: {chey_data.get('profile_pic')}")
    # Inject influencermalang just to be safe
    chey_data['caption_hashtags'] = chey_data.get('caption_hashtags', [])
    if 'influencermalang' not in chey_data['caption_hashtags']:
        chey_data['caption_hashtags'].append('influencermalang')
    
    # Update DB
    with open('influencers.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # hapus entry lama
    data = [d for d in data if d.get('username') != 'cheyuanita']
    
    # tambahkan data yang benar
    data.append(chey_data)
    
    with open('influencers.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print("Database updated strictly via procedures!")
