import json

def parse_followers_count(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    val = str(val).upper().replace(',', '.').replace(' ', '')
    try:
        if 'M' in val:
            return int(float(val.replace('M', '')) * 1000000)
        elif 'K' in val:
            return int(float(val.replace('K', '')) * 1000)
        return int(float(val))
    except ValueError:
        return 0

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('username') == 'cheyuanita':
        followers = item.get('followers_int') or parse_followers_count(item.get('followers'))
        loc = item.get('location')
        name = item.get('name') or item.get('fullName')
        bio = item.get('bio', '')
        acct = item.get('account_type')
        print(f"FOUND: username={item['username']}, followers={followers}, location={loc}, name={name}")
        print(f"Bio: {bio}")
        print(f"Account type: {acct}")
        break
else:
    print("NOT FOUND IN DB")
