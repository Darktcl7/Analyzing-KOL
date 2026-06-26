import json, re, sys

def check_malang(influencer):
    name = influencer.get('name', '').lower()
    username = influencer.get('username', '').lower()
    bio = influencer.get('bio', '').lower()
    tags = [t.lower() for t in influencer.get('tags', [])]
    location = influencer.get('location', '').lower()
    province = (influencer.get('location_province') or '').lower().strip()
    detected = [d.lower() for d in influencer.get('detected_locations', [])]

    allowed_locations = ['malang', 'batu', 'kepanjen', 'pejanten']
    location_str = f"{location} {province} {' '.join(detected)} {bio} {name}".lower()
    
    has_malang_location = any(re.search(r'\b' + loc + r'\b', location_str) for loc in allowed_locations)
    return has_malang_location, location_str.encode('ascii', 'ignore').decode()

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('username') in ['suchandra_saru', 'raimlaode', 'osheeranand_']:
        res, loc_str = check_malang(item)
        print(f"{item.get('username')}: {res}")
        print(f"loc_str: {loc_str}")
        print("---")
