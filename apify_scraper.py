import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Set, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from apify_client import ApifyClient
from location_service import LocationService
from config import APIFY_API_TOKEN

DEFAULT_MAX_PROFILE_SCRAPES = 20
DEFAULT_MAX_PARALLEL_WORKERS = 5
OUTPUT_FILE = 'influencers.json'
POSTS_TO_SCAN = 30

class ApifyInstagramScraper:
    def __init__(self):
        self.client = ApifyClient(APIFY_API_TOKEN)
        self.location_service = LocationService()

    def update_scrape_status(self, text: str, is_running: bool = True):
        try:
            with open('scraping_status.json', 'w') as f:
                json.dump({'status': text, 'is_running': is_running, 'updated_at': datetime.now().isoformat()}, f)
        except: pass

    def scrape_hashtag(self, hashtag: str, limit: int = 30, max_profiles: int = DEFAULT_MAX_PROFILE_SCRAPES, skip_existing: bool = True) -> List[dict]:
        run_input = {
            "hashtags": [hashtag],
            "resultsType": "posts",
            "resultsLimit": limit
        }
        try:
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items: return []
            usernames = self._extract_unique_usernames(items)
            selected = self._prepare_usernames_for_scrape(usernames, max_profiles, skip_existing)
            if not selected: return []
            return self.scrape_profiles_parallel(selected, max_workers=min(DEFAULT_MAX_PARALLEL_WORKERS, len(selected)))
        except Exception as e:
            print(e)
            return []

    def scrape_location(self, location_query: str, limit: int = 30, max_profiles: int = DEFAULT_MAX_PROFILE_SCRAPES, skip_existing: bool = True) -> List[dict]:
        run_input = {
            "search": location_query,
            "searchType": "place",
            "searchLimit": 5,
            "resultsType": "posts",
            "resultsLimit": limit
        }
        try:
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items: return []
            usernames = self._extract_unique_usernames(items)
            selected = self._prepare_usernames_for_scrape(usernames, max_profiles, skip_existing)
            if not selected: return []
            return self.scrape_profiles_parallel(selected, max_workers=min(DEFAULT_MAX_PARALLEL_WORKERS, len(selected)))
        except Exception as e:
            print(e)
            return []

    def scrape_hashtags_batch(self, hashtags: List[str], limit_per_tag: int = 20, max_profiles: int = DEFAULT_MAX_PROFILE_SCRAPES, skip_existing: bool = True) -> List[dict]:
        urls = [f"https://www.instagram.com/explore/tags/{h.replace('#','').strip()}/" for h in hashtags]
        run_input = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": limit_per_tag * len(hashtags),
            "searchType": "hashtag"
        }
        try:
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items: return []
            usernames = self._extract_unique_usernames(items)
            selected = self._prepare_usernames_for_scrape(usernames, max_profiles, skip_existing)
            if not selected: return []
            return self.scrape_profiles_parallel(selected, max_workers=min(DEFAULT_MAX_PARALLEL_WORKERS, len(selected)))
        except Exception as e:
            print(e)
            return []

    def scrape_profiles_parallel(self, usernames: List[str], max_workers: int = 5) -> List[dict]:
        kols = []
        total = len(usernames)
        self.update_scrape_status(f"Memulai batch scraping untuk {total} profil di Apify...")
        
        urls = [f"https://www.instagram.com/{u.replace('@','').strip()}/" for u in usernames]
        
        # Split into chunks of 50 URLs to stay within Apify run safe limits
        chunk_size = 50
        for idx in range(0, len(urls), chunk_size):
            chunk_urls = urls[idx : idx + chunk_size]
            chunk_usernames = usernames[idx : idx + chunk_size]
            
            self.update_scrape_status(f"Menganalisis {min(idx + len(chunk_urls), total)} dari {total} profil...")
            
            run_input = {
                "directUrls": chunk_urls,
                "resultsType": "details"
            }
            try:
                run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
                items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
                
                # Group items by username to handle multiple entries if any, though details typically return 1 per profile
                profile_items = {}
                for item in items:
                    username = item.get('username')
                    if username:
                        if username not in profile_items:
                            profile_items[username] = []
                        profile_items[username].append(item)
                
                # Process each profile
                for u in chunk_usernames:
                    u_clean = u.replace('@','').strip()
                    # Find matching item by username key (case insensitive comparison)
                    match_username = next((k for k in profile_items if k.lower() == u_clean.lower()), None)
                    if match_username:
                        processed = self._process_profile_data(profile_items[match_username], u)
                        if processed:
                            kols.append(processed)
            except Exception as e:
                print(f"Error scraping profile batch: {e}")
                
        self.update_scrape_status(f"Selesai batch scraping {total} profil.", False)
        return kols

    def scrape_single_profile(self, username: str) -> dict:
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username.replace('@','').strip()}/"],
            "resultsType": "details"
        }
        try:
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items: return {}
            return self._process_profile_data(items, username)
        except Exception as e:
            print(e)
            return {}

    def scrape_post_by_url(self, post_url: str) -> dict:
        run_input = {
            "directUrls": [post_url.strip()],
            "resultsType": "posts",
            "resultsLimit": 1
        }
        try:
            run = self.client.actor("apify/instagram-scraper").call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items: return {}
            item = items[0]
            likes = item.get('likesCount') or item.get('likes') or 0
            comments = item.get('commentsCount') or item.get('comments') or 0
            views = item.get('videoPlayCount') or item.get('videoViewCount') or item.get('playCount') or item.get('viewCount') or item.get('views') or 0
            caption = item.get('caption') or ''
            return {
                'likes': likes,
                'comments': comments,
                'views': views,
                'caption': caption
            }
        except Exception as e:
            print(f"Error scraping post: {e}")
            return {}

    def get_existing_usernames(self, filename: str = None) -> Set[str]:
        filename = filename or OUTPUT_FILE
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return {k.get('username', '') for k in json.load(f)}
            except: pass
        return set()

    # Keywords for Malang/Batu area detection
    MALANG_KEYWORDS = [
        "malang", "batu", "kepanjen", "singosari", "turen", "gondanglegi",
        "pakisaji", "dampit", "lawang", "tumpang", "pujon", "ngantang",
        "karangploso", "dau", "jabung", "pakis", "lowokwaru", "klojen",
        "blimbing", "kedungkandang", "sukun", "junrejo", "bumiaji", "bromo",
        "kwb", "malkot"
    ]

    def _is_malang_area(self, kol: dict) -> bool:
        """Check if a KOL is located strictly in the Malang/Batu/Kepanjen area."""
        username = kol.get('username', '').lower()
        name = kol.get('name', '').lower()
        bio = kol.get('bio', '').lower()
        location = (kol.get('location') or '').lower().strip()
        province = (kol.get('location_province') or '').lower().strip()
        detected = [d.lower().strip() for d in kol.get('detected_locations', [])]
        
        # Clean location prefix
        clean_location = location.replace("kabupaten ", "").replace("kota ", "").strip()
        
        # 1. Reject if province is explicitly NOT Jawa Timur
        if province and province != "jawa timur" and province != "unknown":
            return False
            
        # 2. Reject if primary location is explicitly another city in Indonesia/globally
        other_cities = [
            "surabaya", "sidoarjo", "gresik", "mojokerto", "jombang", "banyuwangi", 
            "jember", "lumajang", "probolinggo", "pasuruan", "blitar", "kediri", 
            "tulungagung", "trenggalek", "ponorogo", "pacitan", "magetan", "madiun", 
            "ngawi", "bojonegoro", "tuban", "lamongan", "bangkalan", "sampang", 
            "pamekasan", "sumenep", "jakarta", "bandung", "semarang", "yogyakarta", 
            "solo", "surakarta", "klaten", "denpasar", "bali", "medan", "makassar", 
            "united states", "porto", "galle", "singapore", "tokyo"
        ]
        
        if clean_location in other_cities:
            return False
            
        # 3. Reject if detected locations contains other cities but not Malang/Batu/Kepanjen
        has_other_city = False
        has_malang_city = False
        for d_loc in detected:
            clean_d_loc = d_loc.replace("kabupaten ", "").replace("kota ", "").strip()
            if clean_d_loc in ["malang", "batu"] or any(kw in clean_d_loc for kw in self.MALANG_KEYWORDS):
                has_malang_city = True
            elif clean_d_loc in other_cities:
                has_other_city = True
                
        if has_other_city and not has_malang_city:
            return False
            
        # 4. Check keywords in bio/username/name
        all_text = f" {username} {name} {bio} "
        keyword_matched = None
        for kw in self.MALANG_KEYWORDS:
            if kw in all_text:
                keyword_matched = kw
                break
                
        # Specially check "batu" as a whole word, and ensure it's not stone-related
        if not keyword_matched and re.search(r'\bbatu\b', all_text):
            stone_context = ["akik", "bara", "baterai", "es", "pantai", "sungai", "karang", "tembus", "gunung", "alam", "hias"]
            is_stone = False
            for sc in stone_context:
                if f"batu {sc}" in all_text or f"{sc} batu" in all_text:
                    is_stone = True
                    break
            if not is_stone:
                keyword_matched = "batu"
                
        # If location is explicitly Malang/Batu or surrounding, accept
        if clean_location in ["malang", "batu"] or any(kw in clean_location for kw in self.MALANG_KEYWORDS):
            return True
            
        return keyword_matched is not None

    def save_results(self, kols: List[dict], filename: str = None):
        filename = filename or OUTPUT_FILE
        # Filter: hanya simpan KOL yang terdeteksi di area Malang/Batu
        malang_kols = [k for k in kols if self._is_malang_area(k)]
        skipped = len(kols) - len(malang_kols)
        if skipped:
            print(f"[FILTER] {skipped} KOL dilewati karena bukan area Malang/Batu")
        if not malang_kols:
            print("[FILTER] Tidak ada KOL area Malang dari batch ini.")
            return

        existing = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except: pass
        
        db = {k.get('username'): k for k in existing}
        for k in malang_kols:
            db[k.get('username')] = k
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(list(db.values()), f, indent=4)

    def _extract_unique_usernames(self, items: List[dict]) -> List[str]:
        return list({i.get('ownerUsername') for i in items if i.get('ownerUsername')})

    def _prepare_usernames_for_scrape(self, usernames: List[str], max_profiles: int, skip_existing: bool) -> List[str]:
        if skip_existing:
            exist = self.get_existing_usernames()
            usernames = [u for u in usernames if u not in exist]
        return usernames[:max_profiles]

    def _download_avatar(self, username: str, url: str) -> str:
        if not url: return '/static/default-avatar.png'
        import requests
        save_dir = os.path.join('static', 'profiles')
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{username}.jpg"
        filepath = os.path.join(save_dir, filename)
        try:
            if os.path.exists(filepath): return f"/static/profiles/{filename}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                return f"/static/profiles/{filename}"
        except: pass
        return '/static/default-avatar.png'

    def _process_profile_data(self, items: List[dict], username: str) -> dict:
        profile = None
        posts = []
        for item in items:
            if item.get('username') or item.get('fullName'): 
                profile = item
                if 'latestPosts' in item:
                    posts.extend(item['latestPosts'])
            elif item.get('type') in ['Image', 'Video', 'Sidecar'] or item.get('shortCode'): 
                posts.append(item)
        
        if not profile and posts:
            p = posts[0]
            profile = {
                'username': p.get('ownerUsername', username),
                'fullName': p.get('ownerFullName', ''),
                'biography': '',
                'followersCount': 0,
                'profilePicUrl': p.get('ownerProfilePicUrl', '')
            }
        if not profile: profile = {'username': username}
        
        bio = profile.get('biography', '') or ''
        captions = [p.get('caption', '') or '' for p in posts if p.get('caption')]
        geotags = [p.get('locationName', '') for p in posts if p.get('locationName')]
        
        loc = self.location_service.analyze_kol_location(bio, captions[:POSTS_TO_SCAN], geotags[:POSTS_TO_SCAN])
        
        folls = profile.get('followersCount', 0)
        
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
        
        for p in posts:
            likes_p = p.get('likesCount') or p.get('likes') or 0
            comms_p = p.get('commentsCount') or p.get('comments') or 0
            
            views_p = p.get('videoPlayCount') or p.get('videoViewCount') or p.get('playCount') or p.get('viewCount') or p.get('views') or 0
            is_video = p.get('type') == 'Video' or p.get('isVideo') or views_p > 0
            
            total_likes += likes_p
            total_comments += comms_p
            if is_video:
                total_views += views_p
                video_posts_count += 1
                
            # Endorsement check
            caption_p = (p.get('caption') or '').lower()
            is_endo = any(kw in caption_p for kw in endorsement_keywords) or p.get('isSponsored') or p.get('isPaidPartnership') or False
            
            if is_endo:
                endo_posts.append(p)
                endo_likes += likes_p
                endo_comments += comms_p
                if is_video:
                    endo_views += views_p
                    endo_video_posts_count += 1

        avg_likes = int(total_likes / len(posts)) if posts else 0
        avg_comments = int(total_comments / len(posts)) if posts else 0
        avg_views = int(total_views / video_posts_count) if video_posts_count else 0
        er = ((total_likes + total_comments) / len(posts) / folls * 100) if folls and posts else 0
        
        endo_count = len(endo_posts)
        endo_avg_likes = int(endo_likes / endo_count) if endo_count else 0
        endo_avg_comments = int(endo_comments / endo_count) if endo_count else 0
        endo_avg_views = int(endo_views / endo_video_posts_count) if endo_video_posts_count else 0
        endo_er = ((endo_likes + endo_comments) / endo_count / folls * 100) if folls and endo_count else 0


        # Check latest post date and skip if > 1 year (inactive)
        latest_post_date_str = None
        if posts:
            sorted_dates = []
            for p in posts:
                t_str = p.get('timestamp') or p.get('pubDate')
                if t_str:
                    try:
                        clean_str = t_str.replace('Z', '+00:00')
                        dt = datetime.fromisoformat(clean_str)
                        sorted_dates.append(dt)
                    except:
                        pass
            if sorted_dates:
                latest_dt = max(sorted_dates)
                latest_post_date_str = latest_dt.isoformat()
                
                # Compare naive datetimes
                naive_latest = latest_dt.replace(tzinfo=None)
                one_year_ago = datetime.now() - timedelta(days=365)
                if naive_latest < one_year_ago:
                    print(f"[FILTER] User @{username} dilewati karena postingan terakhirnya ({naive_latest.strftime('%Y-%m-%d')}) sudah lebih dari 1 tahun yang lalu.")
                    return {}
        
        def fmt(c):
            if c >= 1000000: return f"{c/1000000:.1f}M"
            if c >= 1000: return f"{c/1000:.0f}K"
            return str(c)
            
        import re
        m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio)
        email = m.group(0) if m else ''
        
        # Extract phone number from bio
        phone = ''
        wa_m = re.search(r'(?:wa\.me|wa\.link|api\.whatsapp\.com/send\?phone=)(\d+)', bio.lower())
        if wa_m:
            phone = wa_m.group(1)
            if not phone.startswith('+') and not phone.startswith('0'):
                if phone.startswith('62'):
                    phone = '0' + phone[2:]
        else:
            clean_bio = re.sub(r'[\s\-()+]+', '', bio)
            ph_m = re.search(r'(?:62|0)8[1-9]\d{7,10}', clean_bio)
            if ph_m:
                phone = ph_m.group(0)
                if phone.startswith('62'):
                    phone = '0' + phone[2:]
        
        tags = set()
        txt = (bio + ' ' + ' '.join(captions[:5])).lower()
        cat = {
            'Beauty': ['beauty', 'makeup', 'skincare', 'cosmetic', 'mua', 'salon'],
            'Food': ['food', 'kuliner', 'makan', 'cafe', 'resto', 'jajan', 'kopi', 'coffee'],
            'Travel': ['travel', 'jalan', 'trip', 'explore', 'wisata', 'liburan'],
            'Lifestyle': ['lifestyle', 'daily', 'outfit', 'fashion'],
            'Parenting': ['mom', 'mama', 'ibu', 'parenting', 'kids', 'anak'],
            'Tech': ['tech', 'gadget', 'review', 'laptop', 'hp', 'smartphone'],
            'Fitness': ['fitness', 'gym', 'workout', 'olahraga', 'sehat'],
            'Entertainment': ['komedi', 'comedy', 'standup', 'music', 'musik', 'event', 'hiburan'],
            'Otomotif': ['motor', 'mobil', 'bengkel', 'otomotif', 'dealer', 'knalpot']
        }
        for c, kws in cat.items():
            for k in kws:
                if re.search(r'\b' + re.escape(k) + r'\b', txt):
                    tags.add(c)
                    break
        tags = list(tags)[:5] or ['General']
        
        # Ekstrak semua hashtag unik dari caption postingan (feed/reels)
        caption_hashtags = set()
        for cap in captions[:POSTS_TO_SCAN]:
            found = re.findall(r'#(\w+)', cap.lower())
            caption_hashtags.update(found)
        # Tambah juga hashtag dari bio
        bio_hashtags_found = re.findall(r'#(\w+)', bio.lower())
        caption_hashtags.update(bio_hashtags_found)
        caption_hashtags = sorted(caption_hashtags)
        
        # Classify Account Type: Personal, Creator, Business
        is_business = profile.get('isBusinessAccount', False)
        category = (profile.get('businessCategoryName') or profile.get('categoryName') or '').lower()
        
        account_type = "Personal"
        if is_business:
            # Creator categories
            creator_kws = ["creator", "public figure", "artist", "blogger", "writer", "actor", "musician", 
                           "model", "gamer", "journalist", "personal blog", "photographer", "kreator", "tokoh"]
            # Business categories
            business_kws = ["cafe", "restaurant", "store", "shop", "brand", "service", "company", "business", 
                            "agency", "retail", "estate", "hotel", "hospital", "spa", "salon", "clothing", 
                            "wedding", "boutique", "kuliner", "makanan", "minuman", "produk", "jasa", "sewa", 
                            "toko", "grosir", "reseller", "tour", "travel", "kopi", "coffee"]
            
            if any(kw in category for kw in creator_kws):
                account_type = "Creator"
            elif any(kw in category for kw in business_kws):
                account_type = "Business"
            else:
                # Ambiguous category, check bio
                bio_lower = bio.lower()
                if any(kw in bio_lower for kw in ["katalog", "order", "shopee", "ready stock", "sewa", "rent", "jual", "beli", "toko", "dijual", "pricelist", "price list"]):
                    account_type = "Business"
                elif any(kw in bio_lower for kw in ["endorse", "inquiries", "collab", "contact", "cp", "youtube", "tiktok", "vlog"]):
                    account_type = "Creator"
                else:
                    account_type = "Creator" if folls > 2000 else "Business"
        else:
            # Not marked as business, check bio for creator/business markers
            bio_lower = bio.lower()
            if any(kw in bio_lower for kw in ["katalog", "order via", "shopee", "price list", "pricelist", "ready stock", "wa:", "whatsapp:", "hubungi:", "sewa", "rent", "kopi", "coffee", "toko", "jasa"]):
                account_type = "Business"
            elif any(kw in bio_lower for kw in ["business inquiries", "endorse", "cp:", "contact:", "collab", "youtube", "tiktok", "blogger", "influencer"]):
                account_type = "Creator"
            else:
                # Fallback based on followers
                account_type = "Creator" if folls > 5000 else "Personal"

        if account_type == "Personal" and folls < 1000:
            print(f"[FILTER] User @{username} dilewati karena merupakan Account Type Personal dengan followers < 1000 ({folls}).")
            return {}

        return {
            'name': profile.get('fullName', '') or profile.get('username', username),
            'username': profile.get('username', username),
            'image': self._download_avatar(profile.get('username', username), profile.get('profilePicUrl', '')),
            'followers': fmt(folls),
            'followers_int': folls,
            'er': f"{er:.1f}%",
            'er_float': round(er, 2),
            'platform': 'instagram',
            'bio': bio,
            'email': email,
            'phone': phone,
            'location': loc['primary_location'] or 'Unknown',
            'location_country': loc['primary_country'] or 'Unknown',
            'location_province': loc.get('primary_province'),
            'location_confidence': loc['confidence'],
            'location_confidence_score': loc['confidence_score'],
            'detected_locations': loc['all_locations'],
            'location_sources': loc['sources'],
            'tags': tags,
            'account_type': account_type,
            'is_verified': profile.get('verified') or profile.get('isVerified') or False,
            'avg_likes': fmt(avg_likes),
            'avg_comments': avg_comments,
            'avg_views': fmt(avg_views),
            'avg_views_int': avg_views,
            'endorsement_posts_count': endo_count,
            'endorsement_avg_likes': endo_avg_likes,
            'endorsement_avg_comments': endo_avg_comments,
            'endorsement_avg_views': endo_avg_views,
            'endorsement_avg_views_fmt': fmt(endo_avg_views),
            'endorsement_er': f"{endo_er:.1f}%",
            'endorsement_er_float': round(endo_er, 2),
            'posts_count': profile.get('postsCount', len(posts)),
            'scraped_at': datetime.now().isoformat(),
            'posts_analyzed': len(posts),
            'latest_post_date': latest_post_date_str,
            'caption_hashtags': caption_hashtags
        }
