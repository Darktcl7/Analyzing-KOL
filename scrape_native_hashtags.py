from apify_client import ApifyClient
import json, re, os
from datetime import datetime, timedelta

APIFY_API_TOKEN = 'apify_api_KbFQZx7xrhTp1DQM2IcfdrUPTbvqvt41Tyeu'
client = ApifyClient(APIFY_API_TOKEN)

hashtags = ['kulinermalang']

def check_malang(influencer):
    name = influencer.get('fullName', '').lower()
    username = influencer.get('username', '').lower()
    bio = influencer.get('biography', '').lower()
    
    # native scraper returns location in different ways depending on resultsType
    location = '' # posts results usually don't have deep profile location without detail scrape
    # but we can check what's available
    
    allowed_locations = ['malang', 'batu', 'kepanjen', 'pejanten']
    location_str = f"{location} {bio} {name}".lower()
    
    return any(re.search(r'\b' + loc + r'\b', location_str) for loc in allowed_locations)

print("Starting Native Hashtag Scrape...")
all_items = []

for tag in hashtags:
    print(f"Scraping #{tag}...")
    run_input = {
        "hashtags": [tag],
        "resultsType": "posts",
        "resultsLimit": 150 # limit to 150 posts per hashtag for speed
    }
    try:
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        all_items.extend(items)
    except Exception as e:
        print(f"Error on {tag}: {e}")

print(f"Found {len(all_items)} raw posts.")

unique_usernames = set()
recent_influencers = []

one_year_ago = datetime.now() - timedelta(days=365)

for item in all_items:
    username = item.get('ownerUsername')
    if not username or username in unique_usernames:
        continue
        
    timestamp = item.get('timestamp')
    if timestamp:
        try:
            post_date = datetime.strptime(timestamp.split('T')[0], '%Y-%m-%d')
            if post_date < one_year_ago:
                continue # Skip old posts
        except:
            pass
            
    unique_usernames.add(username)
    recent_influencers.append(username)

print(f"Identified {len(recent_influencers)} unique active users within 1 year.")

# Now we need to scrape their profiles to get full bio/followers
print("Scraping details for these profiles...")
profile_run_input = {
    "usernames": recent_influencers[:100], # Process up to 100 to avoid long waits
    "resultsType": "details"
}
try:
    run = client.actor("apify/instagram-scraper").call(run_input=profile_run_input)
    profiles = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    
    with open('influencers.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    added = 0
    for p in profiles:
        # Check strict Malang rule
        if not check_malang(p):
            continue
            
        followers = p.get('followersCount', 0)
        # We don't strictly filter followers here yet because user said "nano influencer 1000 followers" is handled by the UI filter
        # But we can just store them.
        
        # Format for our DB
        formatted = {
            "username": p.get('username'),
            "name": p.get('fullName', ''),
            "bio": p.get('biography', ''),
            "followers": followers,
            "followers_int": followers,
            "account_type": "Creator" if p.get('isBusinessAccount') or p.get('isProfessionalAccount') else "Personal",
            "is_verified": p.get('isVerified', False),
            "profile_pic": p.get('profilePicUrlHD', p.get('profilePicUrl')),
            "location": "Malang", # since they passed check_malang
            "scraped_at": datetime.now().strftime('%Y-%m-%d'),
            "posts_count": p.get('postsCount', 0),
            "platform": "instagram"
        }
        
        # update DB
        data = [d for d in data if d.get('username') != formatted['username']]
        data.append(formatted)
        added += 1
        
    with open('influencers.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully added/updated {added} influencers strictly from Malang.")
    
except Exception as e:
    print(f"Error scraping profiles: {e}")

