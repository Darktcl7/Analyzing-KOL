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

import database
database.init_db()

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

    if filters.get("account_type"):
        acc_type_filter = filters["account_type"].lower()
        if influencer.get("account_type", "").lower() != acc_type_filter:
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

ITEMS_PER_PAGE = 100

@app.route('/', methods=['GET', 'POST'])
def home():
    filters = {
        "query": "", "province": "", "city": "", "district": "",
        "min_fol": "", "max_fol": "", "er_min": "0", "platform": "instagram", "niche_tags": "",
        "sort_by": "", "account_type": ""
    }
    search_performed = False
    filtered_data = []
    pagination = None

    has_params = any(request.args.get(k) for k in [
        'search_keyword', 'province', 'city', 'district',
        'min_followers', 'max_followers', 'er_rate', 'niche_tags', 'sort_by', 'page',
        'account_type'
    ])

    if has_params:
        search_performed = True
        influencers_db = load_data()
        
        raw_query = request.args.get('search_keyword', '').lower().strip()
        clean_query = raw_query.replace('#', '')
        filters["query"] = raw_query
        
        filters["province"] = request.args.get('province', '')
        filters["city"] = request.args.get('city', '').lower()
        filters["district"] = request.args.get('district', '').lower()
        filters["min_fol"] = request.args.get('min_followers', '')
        filters["max_fol"] = request.args.get('max_followers', '')
        filters["er_min"] = request.args.get('er_rate', '0')
        filters["platform"] = request.args.get('platform', 'instagram')
        filters["niche_tags"] = request.args.get('niche_tags', '').lower()
        filters["sort_by"] = request.args.get('sort_by', '')
        filters["account_type"] = request.args.get('account_type', '').strip()
        niche_list = [tag.strip() for tag in filters["niche_tags"].split(',') if tag.strip()]
        filtered_data = filter_influencers(influencers_db, filters, raw_query, clean_query, niche_list)
        
        if filters["sort_by"] == "followers_desc":
            filtered_data.sort(key=lambda x: x.get('followers_int') or parse_followers_count(x.get('followers')), reverse=True)
        elif filters["sort_by"] == "followers_asc":
            filtered_data.sort(key=lambda x: x.get('followers_int') or parse_followers_count(x.get('followers')))
        elif filters["sort_by"] == "er_desc":
            filtered_data.sort(key=lambda x: parse_engagement_rate(x.get('er')), reverse=True)

        total_results = len(filtered_data)
        total_pages = max(1, (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        try:
            current_page = int(request.args.get('page', 1))
        except (ValueError, TypeError):
            current_page = 1
        current_page = max(1, min(current_page, total_pages))

        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        paginated_data = filtered_data[start_idx:end_idx]

        pagination = {
            "page": current_page,
            "total_pages": total_pages,
            "total_results": total_results,
            "per_page": ITEMS_PER_PAGE,
            "has_prev": current_page > 1,
            "has_next": current_page < total_pages,
        }
        filtered_data = paginated_data

    light_regions = build_light_regions(REGIONS_DB)
    if 'user_id' in session:
        saved_usernames = database.get_all_saved_usernames_by_user(session['user_id'])
    else:
        saved_usernames = {i['username'] for i in session.get('my_list', [])}
    return render_template('index.html', influencers=filtered_data, f=filters, regions=light_regions, search_performed=search_performed, pagination=pagination, saved_usernames=saved_usernames)

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
    if infl:
        if 'user_id' in session:
            saved_usernames = database.get_all_saved_usernames_by_user(session['user_id'])
        else:
            saved_usernames = {i['username'] for i in session.get('my_list', [])}
        return render_template('profile.html', kol=infl, saved_usernames=saved_usernames)
    return "Not Found", 404

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            return render_template('register.html', error='Username dan password wajib diisi.', username_val=username)
            
        if len(password) < 6:
            return render_template('register.html', error='Password minimal harus 6 karakter.', username_val=username)
            
        if password != confirm_password:
            return render_template('register.html', error='Konfirmasi password tidak cocok.', username_val=username)
            
        import database
        user_id = database.create_user(username, password)
        if user_id:
            return render_template('login.html', success='Pendaftaran berhasil! Silakan masuk dengan akun Anda.', username_val=username)
        else:
            return render_template('register.html', error='Username sudah digunakan.', username_val=username)
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next') or ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Check if admin login
        if username == 'admin' and password == 'admin123':
            session['is_admin'] = True
            session['username'] = 'admin'
            session['user_id'] = 9999
            return redirect(next_url or url_for('admin_dashboard'))
            
        import database
        user = database.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            # Migrate any session-based list items
            if 'my_list' in session and session['my_list']:
                lists = database.get_user_lists(user['id'])
                if lists:
                    default_list_id = lists[0]['id']
                    for kol in session['my_list']:
                        database.add_to_list(default_list_id, kol['username'])
                session.pop('my_list', None)
                
            return redirect(next_url or url_for('home'))
        else:
            return render_template('login.html', error='Username atau password salah.', next_url=next_url, username_val=username)
            
    return render_template('login.html', next_url=next_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/add_to_list/<username>')
def add_to_list(username):
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))
        
    user_id = session['user_id']
    import database
    folders = database.get_user_lists(user_id)
    if folders:
        list_id = request.args.get('list_id')
        active_folder = None
        if list_id:
            active_folder = next((f for f in folders if str(f['id']) == str(list_id)), None)
        if not active_folder:
            active_folder = folders[0]
            
        database.add_to_list(active_folder['id'], username)
        
    return redirect(request.referrer or url_for('home'))

@app.route('/saved-lists')
def saved_lists():
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))
        
    user_id = session['user_id']
    import database
    folders = database.get_user_lists(user_id)
    
    active_folder_id = request.args.get('list_id')
    active_folder = None
    if active_folder_id:
        active_folder = next((f for f in folders if str(f['id']) == str(active_folder_id)), None)
    if not active_folder and folders:
        active_folder = folders[0]
        
    items = []
    if active_folder:
        items = database.get_list_items(active_folder['id'])
        
    all_influencers = load_data()
    influencer_map = {i['username']: i for i in all_influencers}
    
    merged_items = []
    for item in items:
        username = item['username']
        if username in influencer_map:
            infl_detail = dict(influencer_map[username])
            infl_detail['status'] = item['status']
            infl_detail['notes'] = item['notes']
            merged_items.append(infl_detail)
            
    return render_template('saved_lists.html', 
                           folders=folders, 
                           active_folder=active_folder, 
                           influencers=merged_items)

@app.route('/remove_from_list/<username>')
def remove_from_list(username):
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))
        
    user_id = session['user_id']
    import database
    
    list_id = request.args.get('list_id')
    if list_id:
        database.remove_from_list(list_id, username)
    else:
        folders = database.get_user_lists(user_id)
        for folder in folders:
            database.remove_from_list(folder['id'], username)
            
    ref = request.referrer
    if ref and 'saved-lists' in ref:
        return redirect(url_for('saved_lists', list_id=list_id))
    return redirect(ref or url_for('home'))

@app.route('/clear_list')
def clear_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    list_id = request.args.get('list_id')
    if list_id:
        import database
        folders = database.get_user_lists(session['user_id'])
        if any(str(f['id']) == str(list_id) for f in folders):
            items = database.get_list_items(list_id)
            for item in items:
                database.remove_from_list(list_id, item['username'])
                
    return redirect(url_for('saved_lists', list_id=list_id))

@app.route('/create_list', methods=['POST'])
def create_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    list_name = request.form.get('list_name', '').strip()
    if list_name:
        import database
        database.create_list(session['user_id'], list_name)
    return redirect(url_for('saved_lists'))

@app.route('/delete_list/<int:list_id>', methods=['POST'])
def delete_list(list_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    import database
    database.delete_list(session['user_id'], list_id)
    return redirect(url_for('saved_lists'))

@app.route('/update_item_status', methods=['POST'])
def update_item_status():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    list_id = data.get('list_id')
    username = data.get('username')
    status = data.get('status')
    notes = data.get('notes')
    
    if not list_id or not username:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
        
    import database
    folders = database.get_user_lists(session['user_id'])
    if not any(str(f['id']) == str(list_id) for f in folders):
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403
        
    success = database.update_item_crm(list_id, username, status, notes)
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Database update failed'}), 500

@app.route('/export_list/<int:list_id>')
def export_list(list_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    import database
    folders = database.get_user_lists(session['user_id'])
    folder = next((f for f in folders if f['id'] == list_id), None)
    if not folder:
        return "Access denied", 403
        
    items = database.get_list_items(list_id)
    all_influencers = load_data()
    influencer_map = {i['username']: i for i in all_influencers}
    
    import io
    import csv
    from flask import Response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Username', 'Nama', 'Followers', 'ER', 'Niche', 'Email', 'No WA', 'Lokasi', 'Status', 'Catatan'])
    
    for item in items:
        username = item['username']
        if username in influencer_map:
            inf = influencer_map[username]
            writer.writerow([
                inf.get('username', ''),
                inf.get('name', ''),
                inf.get('followers', ''),
                inf.get('er', ''),
                ', '.join(inf.get('tags', [])),
                inf.get('email', ''),
                inf.get('phone', ''),
                inf.get('location', ''),
                item.get('status', 'Scouted'),
                item.get('notes', '')
            ])
            
    csv_data = output.getvalue()
    filename = f"KOL_Scout_{folder['name'].replace(' ', '_')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/search', methods=['POST'])
def api_search():
    return jsonify({"status": "deprecated, use home search"})

# ============================================================================
# ADMIN MODULE
# ============================================================================

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
