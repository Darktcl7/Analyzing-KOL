import os
import json
from datetime import datetime
from typing import List, Set, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from apify_client import ApifyClient
from location_service import LocationService
from config import APIFY_API_TOKEN

DEFAULT_MAX_PROFILE_SCRAPES = 20
DEFAULT_MAX_PARALLEL_WORKERS = 5
OUTPUT_FILE = 'influencers.json'
POSTS_TO_SCAN = 5

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
        self.update_scrape_status(f"Memulai parallel scraping untuk {total} profil...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_username = {
                executor.submit(self.scrape_single_profile, u): u for u in usernames
            }
            for i, future in enumerate(as_completed(future_to_username), 1):
                u = future_to_username[future]
                try:
                    res = future.result()
                    if res: kols.append(res)
                except Exception as e:
                    print(e)
                if i % 5 == 0 or i == total:
                    self.update_scrape_status(f"Menganalisis {i} dari {total} profil...")
        self.update_scrape_status(f"Selesai parallel scraping {total} profil.", False)
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

    def get_existing_usernames(self, filename: str = None) -> Set[str]:
        filename = filename or OUTPUT_FILE
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return {k.get('username', '') for k in json.load(f)}
            except: pass
        return set()

    def save_results(self, kols: List[dict], filename: str = None):
        filename = filename or OUTPUT_FILE
        existing = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except: pass
        
        db = {k.get('username'): k for k in existing}
        for k in kols:
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
        likes = sum(p.get('likesCount', 0) for p in posts)
        comms = sum(p.get('commentsCount', 0) for p in posts)
        er = ((likes + comms) / len(posts) / folls * 100) if folls and posts else 0
        
        def fmt(c):
            if c >= 1000000: return f"{c/1000000:.1f}M"
            if c >= 1000: return f"{c/1000:.0f}K"
            return str(c)
            
        import re
        m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio)
        email = m.group(0) if m else ''
        
        tags = set()
        txt = (bio + ' ' + ' '.join(captions[:5])).lower()
        cat = {
            'Beauty': ['beauty', 'makeup', 'skincare', 'cosmetic'],
            'Food': ['food', 'kuliner', 'makan', 'cafe', 'resto'],
            'Travel': ['travel', 'jalan', 'trip', 'explore'],
            'Lifestyle': ['lifestyle', 'daily'],
            'Parenting': ['mom', 'mama', 'ibu', 'parenting'],
            'Tech': ['tech', 'gadget', 'review'],
            'Fitness': ['fitness', 'gym', 'workout']
        }
        for c, kws in cat.items():
            if any(k in txt for k in kws): tags.add(c)
        tags = list(tags)[:5] or ['General']
        
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
            'location': loc['primary_location'] or 'Unknown',
            'location_country': loc['primary_country'] or 'Unknown',
            'location_province': loc.get('primary_province'),
            'location_confidence': loc['confidence'],
            'location_confidence_score': loc['confidence_score'],
            'detected_locations': loc['all_locations'],
            'location_sources': loc['sources'],
            'tags': tags,
            'avg_likes': fmt(int(likes / len(posts)) if posts else 0),
            'avg_comments': int(comms / len(posts)) if posts else 0,
            'posts_count': profile.get('postsCount', len(posts)),
            'scraped_at': datetime.now().isoformat(),
            'posts_analyzed': len(posts)
        }
