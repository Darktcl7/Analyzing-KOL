"""
Scraping agresif untuk hashtag #kulinermalang
Menggunakan directUrls (metode yang benar untuk Apify Instagram Scraper)
Target: KOL besar, verified, dan nano influencer yang belum terdaftar
"""
from apify_client import ApifyClient
from location_service import LocationService
import json, os, re
from datetime import datetime, timedelta
from config import APIFY_API_TOKEN

client = ApifyClient(APIFY_API_TOKEN)
location_service = LocationService()
OUTPUT_FILE = 'influencers.json'

# Hashtags yang mau di-scrape
HASHTAGS = ['kulinermalang', 'kulinemalang', 'kulinermalangkota', 'jajanmalang', 'makanmalang']
POSTS_LIMIT = 300  # Ambil lebih banyak post
MAX_NEW_PROFILES = 200  # Scrape hingga 200 profil baru

def get_existing_usernames():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return {k.get('username', '').lower() for k in json.load(f)}
        except:
            pass
    return set()

def process_profile(profile, posts_to_scan=30):
    """Process a single profile into our standard KOL format"""
    bio = profile.get('biography', '') or ''
    username = profile.get('username', '')
    name = profile.get('fullName', '') or ''
    folls = profile.get('followersCount', 0) or 0
    
    # Get posts for engagement calculation
    posts = profile.get('latestPosts', [])
    
    # Calculate engagement
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
    
    # Location detection
    captions = [p.get('caption', '') or '' for p in posts if p.get('caption')]
    geotags = [p.get('locationName', '') for p in posts if p.get('locationName')]
    loc = location_service.analyze_kol_location(bio, captions[:posts_to_scan], geotags[:posts_to_scan])
    
    # Latest post date
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
    
    # Extract hashtags from captions
    all_hashtags = set()
    for cap in captions[:posts_to_scan]:
        found = re.findall(r'#(\w+)', cap.lower())
        all_hashtags.update(found)
    
    # Download avatar
    pic_url = profile.get('profilePicUrlHD') or profile.get('profilePicUrl', '')
    avatar = '/static/default-avatar.png'
    if pic_url:
        import requests
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
    
    # Determine account type
    is_business = profile.get('isBusinessAccount') or profile.get('isProfessionalAccount')
    acc_type = "Creator" if is_business else "Personal"
    
    # Category from business
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
        "is_verified": profile.get('isVerified', False),
        "profile_pic": avatar,
        "location": loc.get('location', 'Malang'),
        "location_province": loc.get('province', 'Jawa Timur'),
        "detected_locations": loc.get('detected_locations', []),
        "scraped_at": datetime.now().strftime('%Y-%m-%d'),
        "posts_count": profile.get('postsCount', 0),
        "platform": "instagram",
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "avg_views": avg_views,
        "engagement_rate": round(er, 2),
        "latest_post_date": latest_post_date.strftime('%Y-%m-%d') if latest_post_date else None,
        "endorsement_count": endo_count,
        "endorsement_avg_likes": endo_avg_likes,
        "endorsement_avg_comments": endo_avg_comments,
        "endorsement_avg_views": endo_avg_views,
        "endorsement_er": round(endo_er, 2),
        "niche_tags": list(all_hashtags)[:20],
        "external_url": profile.get('externalUrl', ''),
    }

# ============ MAIN SCRAPING LOGIC ============
print("=" * 60)
print("🔍 SCRAPING AGRESIF #kulinermalang")
print("=" * 60)

existing_usernames = get_existing_usernames()
print(f"Database saat ini: {len(existing_usernames)} influencer")

# STEP 1: Scrape posts dari hashtag menggunakan directUrls
print(f"\n📥 Step 1: Mengambil post dari hashtag...")
urls = [f"https://www.instagram.com/explore/tags/{h.strip()}/" for h in HASHTAGS]
print(f"   Target hashtags: {HASHTAGS}")
print(f"   Target URL: {urls}")

run_input = {
    "directUrls": urls,
    "resultsType": "posts",
    "resultsLimit": POSTS_LIMIT,
    "searchType": "hashtag"
}

all_items = []
try:
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    all_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"   ✅ Berhasil mengambil {len(all_items)} post!")
except Exception as e:
    print(f"   ❌ Error: {e}")

if not all_items:
    print("\n⚠️ Tidak ada post yang berhasil diambil. Mencoba metode alternatif...")
    # Fallback: coba satu per satu
    for h in HASHTAGS:
        url = f"https://www.instagram.com/explore/tags/{h.strip()}/"
        print(f"   Mencoba {url}...")
        try:
            run = client.actor("apify/instagram-scraper").call(run_input={
                "directUrls": [url],
                "resultsType": "posts",
                "resultsLimit": 100,
                "searchType": "hashtag"
            })
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            all_items.extend(items)
            print(f"   ✅ Dapat {len(items)} post dari #{h}")
        except Exception as e:
            print(f"   ❌ Error pada #{h}: {e}")

if not all_items:
    print("\n❌ Gagal total. Kemungkinan limit API Apify habis atau perlu login cookie.")
    print("   Solusi: Tambahkan Instagram session cookie ke Apify actor settings.")
    exit(1)

# STEP 2: Extract unique usernames yang belum ada di database
print(f"\n👥 Step 2: Mengidentifikasi username unik...")
unique_usernames = list({i.get('ownerUsername') for i in all_items if i.get('ownerUsername')})
print(f"   Total username unik dari post: {len(unique_usernames)}")

new_usernames = [u for u in unique_usernames if u.lower() not in existing_usernames]
print(f"   Username BARU (belum ada di database): {len(new_usernames)}")

# Prioritize: take up to MAX_NEW_PROFILES
selected = new_usernames[:MAX_NEW_PROFILES]
print(f"   Akan di-scrape: {len(selected)} profil")

if not selected:
    print("\n✅ Semua username sudah ada di database. Tidak ada profil baru untuk di-scrape.")
    exit(0)

# STEP 3: Scrape detail profil
print(f"\n📊 Step 3: Scraping detail {len(selected)} profil...")
profile_urls = [f"https://www.instagram.com/{u.strip()}/" for u in selected]

all_profiles = []
chunk_size = 30  # Process 30 profiles at a time
for i in range(0, len(profile_urls), chunk_size):
    chunk = profile_urls[i:i+chunk_size]
    chunk_names = selected[i:i+chunk_size]
    print(f"   Batch {i//chunk_size + 1}: Scraping {len(chunk)} profil ({i+1}-{min(i+len(chunk), len(selected))})...")
    
    try:
        run = client.actor("apify/instagram-scraper").call(run_input={
            "directUrls": chunk,
            "resultsType": "details"
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        all_profiles.extend(items)
        print(f"   ✅ Batch berhasil! Dapat {len(items)} profil")
    except Exception as e:
        print(f"   ❌ Error batch: {e}")

print(f"\n   Total profil berhasil di-scrape: {len(all_profiles)}")

# STEP 4: Process & save (FILTER KETAT: hanya Malang, Batu, Kepanjen/Pejanten)
print(f"\n>> Step 4: Memproses dan menyimpan data...")
print(f"   FILTER AKTIF: Hanya KOL dari Malang, Batu, Kepanjen/Pejanten")

ALLOWED_LOCATIONS = ['malang', 'batu', 'kepanjen', 'pejanten']
MALANG_KEYWORDS = [
    'malang', 'batu', 'kepanjen', 'pejanten', 'singosari', 'turen', 'gondanglegi',
    'pakisaji', 'dampit', 'lawang', 'tumpang', 'pujon', 'ngantang',
    'karangploso', 'dau', 'jabung', 'pakis', 'lowokwaru', 'klojen',
    'blimbing', 'kedungkandang', 'sukun', 'junrejo', 'bumiaji',
    'malkot', 'kota malang', 'kabupaten malang', 'kota batu'
]

def is_malang_area(kol_data):
    """Filter ketat: cek apakah KOL berada di area Malang/Batu/Kepanjen"""
    location = (kol_data.get('location') or '').lower().strip()
    province = (kol_data.get('location_province') or '').lower().strip()
    detected = [d.lower().strip() for d in kol_data.get('detected_locations', [])]
    bio = (kol_data.get('bio') or '').lower()
    name = (kol_data.get('name') or '').lower()
    username = (kol_data.get('username') or '').lower()
    
    # Clean location
    clean_loc = location.replace('kabupaten ', '').replace('kota ', '').strip()
    
    # Check 1: Location field matches
    if clean_loc in ALLOWED_LOCATIONS:
        return True
    if any(kw in location for kw in MALANG_KEYWORDS):
        return True
    
    # Check 2: Detected locations match
    for det in detected:
        clean_det = det.replace('kabupaten ', '').replace('kota ', '').strip()
        if clean_det in ALLOWED_LOCATIONS or any(kw in det for kw in MALANG_KEYWORDS):
            return True
    
    # Check 3: Bio mentions Malang/Batu area
    all_text = f"{bio} {name} {username}"
    for kw in MALANG_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', all_text):
            return True
    
    # Check 4: Province is Jawa Timur AND location has some Malang reference
    if 'jawa timur' in province and any(kw in all_text for kw in MALANG_KEYWORDS):
        return True
    
    return False

with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
    existing_data = json.load(f)

db = {k.get('username'): k for k in existing_data}
added = 0
skipped = 0
filtered_out = 0

for profile in all_profiles:
    username = profile.get('username')
    if not username:
        continue
    
    try:
        processed = process_profile(profile)
        if processed:
            # FILTER LOKASI KETAT
            if not is_malang_area(processed):
                filtered_out += 1
                loc = processed.get('location', 'Unknown')
                print(f"   SKIP {username} (lokasi: {loc}) - bukan area Malang/Batu/Kepanjen")
                continue
            
            db[username] = processed
            added += 1
            folls = processed.get('followers', 0)
            verified = "[VERIFIED]" if processed.get('is_verified') else ""
            loc = processed.get('location', '')
            print(f"   + {username} ({folls:,} followers) [{loc}] {verified}")
    except Exception as e:
        print(f"   ! Error processing {username}: {e}")
        skipped += 1

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(list(db.values()), f, indent=4, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"SCRAPING SELESAI!")
print(f"   Profil baru ditambahkan (Malang/Batu/Kepanjen): {added}")
print(f"   Profil difilter (bukan area target): {filtered_out}")
print(f"   Profil gagal diproses: {skipped}")
print(f"   Total database sekarang: {len(db)} influencer")
print(f"{'=' * 60}")

