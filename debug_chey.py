import json

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('username') == 'cheyuanita':
        followers = item.get('followers_int') or item.get('followersCount') or 0
        loc = item.get('location')
        name = item.get('name') or item.get('fullName')
        print(f"FOUND: username={item['username']}, followers={followers}, location={loc}, name={name}")
        break
else:
    print("NOT FOUND IN DB")
