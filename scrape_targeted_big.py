"""
Scraping TARGETED: langsung scrape profil KOL besar kuliner Malang
Bypass hashtag limitation - langsung target username yang diketahui
"""
from apify_client import ApifyClient
from location_service import LocationService
import json, os, re, requests
from datetime import datetime
from config import APIFY_API_TOKEN

client = ApifyClient(APIFY_API_TOKEN)
location_service = LocationService()
OUTPUT_FILE = 'influencers.json'

# DAFTAR AKUN BESAR KULINER MALANG (dari riset web + akun komunitas)
TARGET_USERNAMES = [
    # === AKUN KOMUNITAS KULINER MALANG (100K-300K+ followers) ===
    "malangfoodies",
    "kulinermalang",
    "malangkuliner", 
    "jajanmalang",
    "malanghits",
    "exploremalang",
    "infomalang",
    "infomalangraya",
    "malangeatery",
    "malang_culinary",
    "kulinerbatu",
    "wisatamalang",
    "malangkota",
    "malangtimes",
    "ngalamfoodies",
    
    # === FOOD BLOGGER / KOL BESAR MALANG ===
    "ammamamo",           # Food blogger senior Malang sejak 2013
    "yuwonooktav",        # Foodinhand Malang, visual estetik
    "gerrhasan",          # Gerry Rinaldi, 650K+ followers
    "ari.wibxwx",         # Ari Wibowo, 370K+ followers
    "cahluwe",            # Andre & Angga, food battle
    "malangkuyliner",     # Sudah ada tapi perlu update
    
    # === BRAND / RESTORAN BESAR DI MALANG ===
    "bakaborescafe",
    "ongtjokimie",
    "rumahmakanindagiri",
    "warunglegoh",
    "kampungkuekue",
    "baksolawang",
    "oenmalang",
    "pangsitmiebakso_toljan",
    "toko.oen",
    "breadtalk_malang",
    "rawaonbujari",
    "baksobakar_malang",
    "bakso.president",
    "ayamgorengpresiden",
    
    # === KOL LIFESTYLE MALANG YANG SERING REVIEW KULINER ===
    "aremafcofficial",
    "stfranciscusxaveriusmlg",
    "bimowidyap",         # Ingin Kurus YouTube
    "malangfoodhunter",
    "malangfoodgram",
    "foodmalang",
    "dapurmalang",
    "kulinerjatim",
    "surabayafoodies",    # Sering review Malang juga
    
    # === MICRO/NANO KOL KULINER MALANG YANG AKTIF ===
    "lapergram",
    "makanterus.id",
    "jelajahmalang",
    "wisatabatu",
    "batutourism",
    "malangfoodstory",
    "malangkulinerhits",
    "kulinerhitsmalang",
    "foodiemalang",
    "makananmalang",
    "makandiimalang",
    "kulinermalangbatu",
    "foodhuntermalang",
    "malangfoodguide",
    "reviewkulinermalang",
    "wisatakulinermalang",
    "malang.food",
    "ceritakulinermalang",
    "malangfoodie",
    "jajanmalangbatu",
    # === TAMBAHAN DARI PENCARIAN IG (KULINER MALANG) ===
    "malangsukajajan", "kulinermalang88", "kulinermalangraya", "airayukimom", "mindonimalang",
    "preksumalang", "infokulinermalang", "kulineran_malang_", "kulinermalangcom", "kulinermalang_",
    "rujakhayday", "kulinerenakmalang", "badogersmalang", "kulinermhsmlg", "mamdimalang",
    "kulinermalang.city", "malang.kulinerr", "kulinerhalalmalang", "warunglox", "laper_mager",
    "kopiletek", "kulinermalangg", "infokulinermalangan", "infokulinermlg", "voodiesid",
    "kuliner.malangraya", "kuliner_malang", "duniakulinermalang", "kakilimamalang", "katalogmalang",
    "kulinermalangid", "depotkayutangan"
]

def get_existing_usernames():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return {k.get('username', '').lower() for k in json.load(f)}
        except:
            pass
    return set()

def process_profile(profile, posts_to_scan=30):
    bio = profile.get('biography', '') or ''
    username = profile.get('username', '')
    name = profile.get('fullName', '') or ''
    folls = profile.get('followersCount', 0) or 0
    posts = profile.get('latestPosts', [])
    
    total_likes = 0
    total_comments = 0
    total_views = 0
    video_posts_count = 0
    
    endo_posts = []
    endo_likes = 0
    endo_comments = 0
    endo_views = 0
    endo_video_posts_count = 0
    
    endorsement_keywords = [
        '#ads', '#endorse', '#paidpromote', '#pp', '#sponsor', '#promotion',
        '#kerjasama', '#collab', '#partnership', '#paidpartnership', '#gifted',
        'paid partnership', '#sp', 'sponsored', 'promosi', 'collaboration'
    ]
    
    for p in posts[:posts_to_scan]:
        likes_p = p.get('likesCount') or p.get('likes') or 0
        comms_p = p.get('commentsCount') or p.get('comments') or 0
        views_p = p.get('videoPlayCount') or p.get('videoViewCount') or p.get('playCount') or 0
        is_video = p.get('type') == 'Video' or views_p > 0
        
        total_likes += likes_p
        total_comments += comms_p
        if is_video:
            total_views += views_p
            video_posts_count += 1
            
        caption_p = (p.get('caption') or '').lower()
        is_endo = any(kw in caption_p for kw in endorsement_keywords)
        if is_endo:
            endo_posts.append(p)
            endo_likes += likes_p
            endo_comments += comms_p
            if is_video:
                endo_views += views_p
                endo_video_posts_count += 1
    
    post_count = min(len(posts), posts_to_scan)
    avg_likes = int(total_likes / post_count) if post_count else 0
    avg_comments = int(total_comments / post_count) if post_count else 0
    avg_views = int(total_views / video_posts_count) if video_posts_count else 0
    er = ((total_likes + total_comments) / post_count / folls * 100) if folls and post_count else 0
    
    endo_count = len(endo_posts)
    endo_avg_likes = int(endo_likes / endo_count) if endo_count else 0
    endo_avg_comments = int(endo_comments / endo_count) if endo_count else 0
    endo_avg_views = int(endo_views / endo_video_posts_count) if endo_video_posts_count else 0
    endo_er = ((endo_likes + endo_comments) / endo_count / folls * 100) if folls and endo_count else 0
    
    captions = [p.get('caption', '') or '' for p in posts if p.get('caption')]
    geotags = [p.get('locationName', '') for p in posts if p.get('locationName')]
    loc = location_service.analyze_kol_location(bio, captions[:posts_to_scan], geotags[:posts_to_scan])
    
    latest_post_date = None
    for p in posts:
        t_str = p.get('timestamp') or p.get('pubDate')
        if t_str:
            try:
                clean_str = t_str.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_str)
                if latest_post_date is None or dt > latest_post_date:
                    latest_post_date = dt
            except:
                pass
    
    all_hashtags = set()
    for cap in captions[:posts_to_scan]:
        found = re.findall(r'#(\w+)', cap.lower())
        all_hashtags.update(found)
    
    pic_url = profile.get('profilePicUrlHD') or profile.get('profilePicUrl', '')
    avatar = '/static/default-avatar.png'
    if pic_url:
        save_dir = os.path.join('static', 'profiles')
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{username}.jpg")
        try:
            if os.path.exists(filepath):
                avatar = f"/static/profiles/{username}.jpg"
            else:
                resp = requests.get(pic_url, timeout=10)
                if resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    avatar = f"/static/profiles/{username}.jpg"
        except:
            pass
    
    is_business = profile.get('isBusinessAccount') or profile.get('isProfessionalAccount')
    acc_type = "Creator" if is_business else "Personal"
    category = profile.get('businessCategoryName') or profile.get('categoryName') or ''
    
    return {
        "username": username,
        "name": name,
        "bio": bio,
        "followers": folls,
        "followers_int": folls,
        "following": profile.get('followsCount', 0),
        "account_type": acc_type,
        "category": category,
        "is_verified": profile.get('verified') or profile.get('isVerified') or False,
        "image": avatar,
        "location": loc.get('location', 'Malang'),
        "location_province": loc.get('province', 'Jawa Timur'),
        "detected_locations": loc.get('detected_locations', []),
        "scraped_at": datetime.now().strftime('%Y-%m-%d'),
        "posts_count": profile.get('postsCount', 0),
        "platform": "instagram",
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "avg_views": avg_views,
        "er": f"{er:.1f}%",
        "er_float": round(er, 2),
        "latest_post_date": latest_post_date.strftime('%Y-%m-%d') if latest_post_date else None,
        "endorsement_count": endo_count,
        "endorsement_avg_likes": endo_avg_likes,
        "endorsement_avg_comments": endo_avg_comments,
        "endorsement_avg_views": endo_avg_views,
        "endorsement_er": round(endo_er, 2),
        "caption_hashtags": list(all_hashtags)[:20],
        "external_url": profile.get('externalUrl', ''),
    }


# ============ MAIN ============
print("=" * 60)
print("SCRAPING TARGETED - KOL BESAR KULINER MALANG")
print("=" * 60)

existing = get_existing_usernames()
print(f"Database saat ini: {len(existing)} influencer")

# Filter: hanya scrape yang belum ada
new_targets = [u for u in TARGET_USERNAMES if u.lower() not in existing]
print(f"Target total: {len(TARGET_USERNAMES)} username")
print(f"Sudah ada di DB: {len(TARGET_USERNAMES) - len(new_targets)}")
print(f"Username BARU untuk di-scrape: {len(new_targets)}")

if not new_targets:
    print("\nSemua target sudah ada di database!")
    exit(0)

# Scrape profil langsung menggunakan directUrls
print(f"\nMemulai scraping {len(new_targets)} profil...")
profile_urls = [f"https://www.instagram.com/{u.strip()}/" for u in new_targets]

all_profiles = []
chunk_size = 25
for i in range(0, len(profile_urls), chunk_size):
    chunk = profile_urls[i:i+chunk_size]
    batch_num = i // chunk_size + 1
    total_batches = (len(profile_urls) + chunk_size - 1) // chunk_size
    print(f"\n  Batch {batch_num}/{total_batches}: Scraping {len(chunk)} profil...")
    
    try:
        run = client.actor("apify/instagram-scraper").call(run_input={
            "directUrls": chunk,
            "resultsType": "details"
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        all_profiles.extend(items)
        print(f"  Berhasil! Dapat {len(items)} profil")
    except Exception as e:
        print(f"  Error batch: {e}")

print(f"\nTotal profil berhasil di-scrape: {len(all_profiles)}")

# Process & save
with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
    existing_data = json.load(f)

db = {k.get('username'): k for k in existing_data}
added = 0
skipped = 0

for profile in all_profiles:
    username = profile.get('username')
    if not username:
        continue
    
    try:
        processed = process_profile(profile)
        if processed:
            db[username] = processed
            added += 1
            folls = processed.get('followers', 0)
            verified = "[VERIFIED]" if processed.get('is_verified') else ""
            loc = processed.get('location', '')
            print(f"  + {username} ({folls:,} followers) [{loc}] {verified}")
    except Exception as e:
        print(f"  ! Error processing {username}: {e}")
        skipped += 1

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(list(db.values()), f, indent=4, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"SCRAPING TARGETED SELESAI!")
print(f"  Profil baru ditambahkan: {added}")
print(f"  Profil gagal: {skipped}")
print(f"  Total database sekarang: {len(db)} influencer")
print(f"{'=' * 60}")
