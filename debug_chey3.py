import json

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('username') == 'cheyuanita':
        print(json.dumps(item, indent=2))
        break
