import json

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('username') == 'cheyuanita':
        item['caption_hashtags'] = item.get('caption_hashtags', [])
        if 'influencermalang' not in item['caption_hashtags']:
            item['caption_hashtags'].append('influencermalang')
        # pastikan bio dan lain-lain valid
        item['account_type'] = 'Creator'
        print("Updated cheyuanita!")
        break

with open('influencers.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
