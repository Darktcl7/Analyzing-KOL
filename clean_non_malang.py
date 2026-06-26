"""Clean database: hapus profil yang bukan area Malang/Batu/Kepanjen"""
import json, re
from location_service import LocationService

ALLOWED = ['malang', 'batu', 'kepanjen', 'pejanten']
KEYWORDS = [
    'malang', 'batu', 'kepanjen', 'pejanten', 'singosari', 'turen', 'gondanglegi',
    'pakisaji', 'dampit', 'lawang', 'tumpang', 'pujon', 'ngantang',
    'karangploso', 'dau', 'jabung', 'pakis', 'lowokwaru', 'klojen',
    'blimbing', 'kedungkandang', 'sukun', 'junrejo', 'bumiaji',
    'malkot', 'kota malang', 'kabupaten malang', 'kota batu'
]

def is_malang(k):
    loc = (k.get('location') or '').lower().strip()
    bio = (k.get('bio') or '').lower()
    name = (k.get('name') or '').lower()
    uname = (k.get('username') or '').lower()
    detected = [d.lower() for d in k.get('detected_locations', [])]
    clean = loc.replace('kabupaten ', '').replace('kota ', '').strip()
    
    if clean in ALLOWED:
        return True
    if any(kw in loc for kw in KEYWORDS):
        return True
    for d in detected:
        cd = d.replace('kabupaten ', '').replace('kota ', '').strip()
        if cd in ALLOWED or any(kw in d for kw in KEYWORDS):
            return True
    all_t = f"{bio} {name} {uname}"
    for kw in KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', all_t):
            return True
    return False

with open('influencers.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total sebelum filter: {len(data)}")
filtered = [k for k in data if is_malang(k)]
removed = [k for k in data if not is_malang(k)]
print(f"Lolos filter Malang/Batu/Kepanjen: {len(filtered)}")
print(f"Dihapus (bukan area target): {len(removed)}")

for r in removed:
    u = r.get('username', '?')
    f_count = r.get('followers', 0)
    loc = r.get('location', '?')
    print(f"  HAPUS: {u} ({f_count} followers) [{loc}]")

with open('influencers.json', 'w', encoding='utf-8') as f:
    json.dump(filtered, f, indent=4, ensure_ascii=False)

print(f"\nDatabase bersih: {len(filtered)} influencer (khusus Malang/Batu/Kepanjen)")
