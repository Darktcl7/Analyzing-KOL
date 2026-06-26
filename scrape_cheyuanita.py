from apify_client import ApifyClient
import json, os

APIFY_API_TOKEN = 'apify_api_KbFQZx7xrhTp1DQM2IcfdrUPTbvqvt41Tyeu'
client = ApifyClient(APIFY_API_TOKEN)

run_input = {
    "directUrls": ["https://www.instagram.com/cheyuanita/"],
    "resultsType": "details"
}

print("Scraping cheyuanita...")
run = client.actor("apify/instagram-scraper").call(run_input=run_input)
dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in dataset_items:
    item['scraped_at'] = '2026-06-25'
    item['location'] = 'Malang'
    item['detected_locations'] = ['Malang']
    item['followers_int'] = item.get('followersCount', 0)
    
    data = [d for d in data if d.get('username') != item.get('username')]
    data.append(item)

with open('influencers.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"Added cheyuanita. Total: {len(data)}")
