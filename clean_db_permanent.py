import json, re

def check_malang(influencer):
    name = influencer.get('name', '').lower()
    username = influencer.get('username', '').lower()
    bio = influencer.get('bio', '').lower()
    location = influencer.get('location', '').lower()
    province = (influencer.get('location_province') or '').lower().strip()
    detected = [d.lower() for d in influencer.get('detected_locations', [])]

    allowed_locations = ['malang', 'batu', 'kepanjen', 'pejanten']
    location_str = f"{location} {province} {' '.join(detected)} {bio} {name}".lower()
    
    has_malang_location = any(re.search(r'\b' + loc + r'\b', location_str) for loc in allowed_locations)
    return has_malang_location

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

new_data = [item for item in data if check_malang(item)]
removed = len(data) - len(new_data)

with open('influencers.json', 'w', encoding='utf-8') as f:
    json.dump(new_data, f, indent=4, ensure_ascii=False)

print(f"Removed {removed} accounts permanently from database.")
