import json
import os
from flask import Flask, render_template, request, session, redirect, url_for, jsonify

# ============================================================================
# SCRAPER CONFIGURATION
# ============================================================================
# Default ke Apify dulu, user bisa switch ke Smartproxy dengan mengubah import
try:
    # Option A: Apify (Existing)
    from apify_scraper import ApifyInstagramScraper
    
    # Option B: Smartproxy (New) - Uncomment to use if you have credentials
    # from smartproxy_scraper import SmartproxyInstagramScraper as ApifyInstagramScraper
    
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-me')

# Subpath configuration for VPS deployment
# When deployed at /kolproject, set this. For local dev, leave empty.
SUBPATH = os.environ.get('APPLICATION_ROOT', '')
if SUBPATH:
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.wrappers import Response
    app.config['APPLICATION_ROOT'] = SUBPATH


def load_data():
    file_path = 'influencers.json'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_regions_data():
    file_path = 'data/indonesia_cities.json'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"provinces": []}

REGIONS_DB = load_regions_data()
AUTO_SCRAPE_MIN_LOCAL_RESULTS = int(os.environ.get('AUTO_SCRAPE_MIN_LOCAL_RESULTS', '5'))
AUTO_SCRAPE_MAX_HASHTAGS = int(os.environ.get('AUTO_SCRAPE_MAX_HASHTAGS', '2'))
AUTO_SCRAPE_LIMIT_PER_TAG = int(os.environ.get('AUTO_SCRAPE_LIMIT_PER_TAG', '20'))
AUTO_SCRAPE_LOCATION_LIMIT = int(os.environ.get('AUTO_SCRAPE_LOCATION_LIMIT', '20'))
AUTO_SCRAPE_PROFILE_LIMIT = int(os.environ.get('AUTO_SCRAPE_PROFILE_LIMIT', '5'))
AUTO_SCRAPE_REQUIRE_CITY = os.environ.get('AUTO_SCRAPE_REQUIRE_CITY', '1') == '1'


def normalize_province_name(value):
    return (
        (value or '')
        .lower()
        .strip()
        .replace("dki ", "")
        .replace("d.i. ", "")
        .replace("di ", "")
        .replace("daerah istimewa ", "")
    )


def parse_followers_count(value):
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value or '').strip().upper().replace(',', '')
    if not text:
        return 0

    multiplier = 1
    if text.endswith('K'):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith('M'):
        multiplier = 1000000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except ValueError:
        digits_only = ''.join(ch for ch in text if ch.isdigit())
        return int(digits_only) if digits_only else 0


def parse_engagement_rate(value):
    text = str(value or '0').replace('%', '').replace(',', '.').strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def influencer_matches_filters(influencer, filters, raw_query, clean_query, niche_list):
    name = influencer.get('name', '').lower()
    username = influencer.get('username', '').lower()
    bio = influencer.get('bio', '').lower()
    tags = [t.lower() for t in influencer.get('tags', [])]
    location = influencer.get('location', '').lower()
    province = (influencer.get('location_province') or '').lower().strip()
    detected = [d.lower() for d in influencer.get('detected_locations', [])]

    if raw_query:
        text_match = any(
            query in field
            for query in {raw_query, clean_query}
            if query
            for field in (name, username, bio)
        )
        tag_match = any(clean_query == tag or clean_query in tag for tag in tags) if clean_query else False
        if not text_match and not tag_match:
            return False

    if filters["province"]:
        if not province:
            return False
        if normalize_province_name(filters["province"]) != normalize_province_name(province):
            return False

    if filters["city"]:
        city_filter = filters["city"]
        city_match = (
            city_filter in location
            or location in city_filter
            or city_filter in province
            or province in city_filter
            or any(city_filter in item or item in city_filter for item in detected)
        )
        if not city_match:
            return False

    if filters["district"]:
        district_filter = filters["district"]
        district_match = (
            any(district_filter in item or item in district_filter for item in detected)
            or district_filter in location
            or location in district_filter
        )
        if not district_match:
            return False

    if filters["min_fol"]:
        try:
            min_followers = int(filters["min_fol"])
        except ValueError:
            min_followers = 0
        current_followers = influencer.get('followers_int') or parse_followers_count(influencer.get('followers'))
        if current_followers < min_followers:
            return False

    if filters.get("max_fol"):
        try:
            max_followers = int(filters["max_fol"])
        except ValueError:
            max_followers = float('inf')
        current_followers = influencer.get('followers_int') or parse_followers_count(influencer.get('followers'))
        if current_followers > max_followers:
            return False

    if filters["er_min"] and filters["er_min"] != "0":
        if parse_engagement_rate(influencer.get('er')) < parse_engagement_rate(filters["er_min"]):
            return False

    if niche_list:
        niche_match = any(any(niche in tag for niche in niche_list) for tag in tags) or any(
            niche in bio for niche in niche_list
        )
        if not niche_match:
            return False

    return True


def filter_influencers(influencers, filters, raw_query, clean_query, niche_list):
    return [
        influencer
        for influencer in influencers
        if influencer_matches_filters(influencer, filters, raw_query, clean_query, niche_list)
    ]


def build_scrape_terms(filters, clean_query, niche_list):
    scrape_terms = []

    if clean_query:
        scrape_terms.append(clean_query)

    if filters["province"]:
        province_clean = filters["province"].lower().replace(" ", "").replace("dki", "")
        scrape_terms.extend([province_clean, f"explore{province_clean}"])

    if filters["city"]:
        city_clean = (
            filters["city"]
            .lower()
            .replace("kota ", "")
            .replace("kabupaten ", "")
            .replace(" ", "")
        )
        scrape_terms.extend([city_clean, f"explore{city_clean}"])

    for niche in niche_list[:3]:
        niche_clean = niche.strip().replace("#", "").replace(" ", "")
        if niche_clean and len(niche_clean) > 2:
            scrape_terms.append(niche_clean)

    return sorted(set(scrape_terms))[:AUTO_SCRAPE_MAX_HASHTAGS]


def dedupe_influencers(influencers):
    unique = []
    seen = set()
    for influencer in influencers:
        username = influencer.get('username')
        if not username or username in seen:
            continue
        unique.append(influencer)
        seen.add(username)
    return unique


def maybe_auto_scrape(filtered_data, filters, scrape_terms, niche_list, raw_query, clean_query):
    has_precise_location = bool(filters["city"])
    should_scrape = (
        len(filtered_data) < AUTO_SCRAPE_MIN_LOCAL_RESULTS
        and bool(scrape_terms)
        and SCRAPER_AVAILABLE
        and (has_precise_location or not AUTO_SCRAPE_REQUIRE_CITY)
    )
    print(f"[DEBUG] filtered_data count: {len(filtered_data)}")
    print(f"[DEBUG] scrape_terms: {scrape_terms}")
    print(f"[DEBUG] SCRAPER_AVAILABLE: {SCRAPER_AVAILABLE}")

    if not should_scrape:
        print(f"[DEBUG] Scraping skipped - should_scrape={should_scrape}")
        return filtered_data

    print(f"[INFO] Data minim ({len(filtered_data)}). Auto-Scrape dengan terms: {scrape_terms}")
    try:
        scraper = ApifyInstagramScraper()
        all_new_kols = []

        if filters["city"]:
            city_name = filters["city"].replace("kota ", "").replace("kabupaten ", "").title()
            print(f"[SCRAPE] Scraping by location: {city_name}...")
            try:
                location_kols = scraper.scrape_location(
                    city_name,
                    limit=AUTO_SCRAPE_LOCATION_LIMIT,
                    max_profiles=AUTO_SCRAPE_PROFILE_LIMIT,
                )
                if location_kols:
                    all_new_kols.extend(location_kols)
                    print(f"[OK] Got {len(location_kols)} KOLs from location search")
            except Exception as loc_err:
                print(f"[WARN] Location scrape error: {loc_err}")

        if len(filtered_data) + len(all_new_kols) < AUTO_SCRAPE_MIN_LOCAL_RESULTS and scrape_terms:
            terms_to_scrape = scrape_terms[:AUTO_SCRAPE_MAX_HASHTAGS]
            print(f"[SCRAPE] Batch Scraping hashtags: #{', #'.join(terms_to_scrape)}...")
            hashtag_kols = scraper.scrape_hashtags_batch(
                terms_to_scrape,
                limit_per_tag=AUTO_SCRAPE_LIMIT_PER_TAG,
                max_profiles=AUTO_SCRAPE_PROFILE_LIMIT,
            )
            if hashtag_kols:
                all_new_kols.extend(hashtag_kols)
                print(f"[OK] Got {len(hashtag_kols)} KOLs from hashtags")

        if not all_new_kols:
            print("[WARN] No new KOLs found from scraping")
            return filtered_data

        scraper.save_results(all_new_kols)
        matched_new_kols = filter_influencers(all_new_kols, filters, raw_query, clean_query, niche_list)
        combined_results = dedupe_influencers(filtered_data + matched_new_kols)
        print(f"[OK] Auto-scrape done. Total matched: {len(combined_results)}")
        return combined_results
    except Exception as err:
        print(f"[ERROR] Auto-scrape error: {err}")
        return filtered_data


def build_light_regions(regions_db):
    light_regions = {"provinces": []}
    for prov in regions_db.get("provinces", []):
        light_regions["provinces"].append({
            "name": prov["name"],
            "cities": [{"name": city["name"]} for city in prov.get("cities", [])]
        })
    return light_regions

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/', methods=['GET', 'POST'])
def home():
    filters = {
        "query": "", "province": "", "city": "", "district": "",
        "min_fol": "", "max_fol": "", "er_min": "0", "platform": "instagram", "niche_tags": "",
        "sort_by": ""
    }
    search_performed = False
    filtered_data = []

    if request.method == 'POST':
        search_performed = True
        influencers_db = load_data()
        
        raw_query = request.form.get('search_keyword', '').lower().strip()
        clean_query = raw_query.replace('#', '')
        filters["query"] = raw_query
        
        filters["province"] = request.form.get('province', '')
        filters["city"] = request.form.get('city', '').lower()
        filters["district"] = request.form.get('district', '').lower()
        filters["min_fol"] = request.form.get('min_followers', '')
        filters["max_fol"] = request.form.get('max_followers', '')
        filters["er_min"] = request.form.get('er_rate', '0')
        filters["platform"] = request.form.get('platform', 'instagram')
        filters["niche_tags"] = request.form.get('niche_tags', '').lower()
        filters["sort_by"] = request.form.get('sort_by', '')
        niche_list = [tag.strip() for tag in filters["niche_tags"].split(',') if tag.strip()]
        filtered_data = filter_influencers(influencers_db, filters, raw_query, clean_query, niche_list)
        
        if filters["sort_by"] == "followers_desc":
            filtered_data.sort(key=lambda x: x.get('followers_int') or parse_followers_count(x.get('followers')), reverse=True)
        elif filters["sort_by"] == "followers_asc":
            filtered_data.sort(key=lambda x: x.get('followers_int') or parse_followers_count(x.get('followers')))
        elif filters["sort_by"] == "er_desc":
            filtered_data.sort(key=lambda x: parse_engagement_rate(x.get('er')), reverse=True)

    light_regions = build_light_regions(REGIONS_DB)
    return render_template('index.html', influencers=filtered_data, f=filters, regions=light_regions, search_performed=search_performed)

# ... (Sisa Routes: api/districts, influencer, add_to_list, dll TETAP SAMA) ...
@app.route('/api/districts/<city_name>')
def get_districts(city_name):
    # ... code ...
    city_name_lower = city_name.lower()
    for prov in REGIONS_DB.get("provinces", []):
        for city in prov.get("cities", []):
            if city["name"].lower() == city_name_lower:
                return {"districts": city.get("kecamatan", [])}
    return {"districts": []}

@app.route('/influencer/<username>')
def profile_detail(username):
    all_data = load_data()
    infl = next((i for i in all_data if i['username'].replace('@','') == username.replace('@','')), None)
    if infl: return render_template('profile.html', kol=infl)
    return "Not Found", 404

@app.route('/add_to_list/<username>')
def add_to_list(username):
    if 'my_list' not in session: session['my_list'] = []
    all_data = load_data()
    infl = next((i for i in all_data if i['username'] == username), None) # simplified
    # ... logic ...
    if infl:
        cur = list(session['my_list'])
        if not any(d['username'] == infl['username'] for d in cur):
            cur.append(infl)
            session['my_list'] = cur
            session.modified = True
    return redirect(url_for('home'))

@app.route('/saved-lists')
def saved_lists():
    return render_template('saved_lists.html', influencers=session.get('my_list', []))

@app.route('/remove_from_list/<username>')
def remove_from_list(username):
    if 'my_list' in session:
        cur = list(session['my_list'])
        session['my_list'] = [i for i in cur if i['username'] != username]
        session.modified = True
    return redirect(url_for('saved_lists'))

@app.route('/clear_list')
def clear_list():
    session['my_list'] = []
    session.modified = True
    return redirect(url_for('saved_lists'))

@app.route('/api/search', methods=['POST'])
def api_search():
    # Legacy support
    return jsonify({"status": "deprecated, use home search"})

# ============================================================================
# ADMIN MODULE
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'admin123':
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error='Password salah.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('admin.html', total_db=len(load_data()))

@app.route('/api/start_scrape', methods=['POST'])
def start_scrape():
    if not session.get('is_admin'): return jsonify({'status': 'unauthorized'}), 401
    import subprocess
    try:
        subprocess.Popen([os.path.join('.', 'venv', 'Scripts', 'python.exe'), 'scrape_malang.py'])
        return jsonify({'status': 'started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scraping_status')
def scraping_status():
    if not session.get('is_admin'): return jsonify({'status': 'unauthorized'}), 401
    file_path = 'scraping_status.json'
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except: pass
    return jsonify({'status': 'Tidak ada proses berjalan', 'is_running': False})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
