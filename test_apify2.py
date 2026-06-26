from apify_client import ApifyClient
import json

APIFY_API_TOKEN = 'apify_api_KbFQZx7xrhTp1DQM2IcfdrUPTbvqvt41Tyeu'
client = ApifyClient(APIFY_API_TOKEN)

run_input = {
    "directUrls": ["https://www.instagram.com/explore/tags/influencermalang/"],
    "resultsType": "posts",
    "resultsLimit": 30
}

print("Testing Apify hashtag directUrl...")
run = client.actor("apify/instagram-scraper").call(run_input=run_input)
items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"Found {len(items)} items")
if items:
    print("Example username:", items[0].get('ownerUsername'))
