"""
Location Intelligence Service
=============================
Module untuk mendeteksi lokasi KOL secara otomatis dari:
1. Bio profile
2. Caption posts
3. Geotag/locationName dari posts

Mendukung deteksi lokasi Indonesia (detail) dan Global.
"""

import json
import re
import os
from typing import List, Dict, Optional, Tuple
from collections import Counter

# Path ke database
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
INDONESIA_DB_PATH = os.path.join(DATA_DIR, 'indonesia_cities.json')
GLOBAL_DB_PATH = os.path.join(DATA_DIR, 'global_cities.json')


class LocationService:
    """Service untuk deteksi dan analisis lokasi KOL - Indonesia & Global"""
    
    def __init__(self):
        self.indonesia_data = self._load_json(INDONESIA_DB_PATH)
        self.global_data = self._load_json(GLOBAL_DB_PATH)
        self.location_index = self._build_location_index()
        print(f"[OK] LocationService initialized with {len(self.location_index)} locations")
    
    def _load_json(self, path: str) -> dict:
        """Load JSON file safely"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Database not found at {path}")
            return {}
    
    def _build_location_index(self) -> Dict[str, dict]:
        """
        Build unified index untuk Indonesia & Global locations.
        Key: nama lokasi (lowercase)
        Value: info lengkap (negara, provinsi, tipe, dll)
        """
        index = {}
        
        # === INDEX INDONESIA (Prioritas lebih tinggi, lebih detail) ===
        for province in self.indonesia_data.get('provinces', []):
            prov_name = province['name']
            
            # Index provinsi
            index[prov_name.lower()] = {
                'name': prov_name,
                'type': 'provinsi',
                'province': prov_name,
                'country': 'Indonesia',
                'country_code': 'ID'
            }
            
            # Index alias provinsi
            for alias in province.get('aliases', []):
                index[alias.lower()] = {
                    'name': prov_name,
                    'type': 'provinsi',
                    'province': prov_name,
                    'country': 'Indonesia',
                    'country_code': 'ID'
                }
            
            # Index kota/kabupaten
            for city in province.get('cities', []):
                city_name = city['name']
                city_type = city.get('type', 'kota')
                
                index[city_name.lower()] = {
                    'name': city_name,
                    'type': city_type,
                    'province': prov_name,
                    'country': 'Indonesia',
                    'country_code': 'ID'
                }
                
                # Index alias kota
                for alias in city.get('aliases', []):
                    if alias.lower() not in index:  # Hindari overwrite
                        index[alias.lower()] = {
                            'name': city_name,
                            'type': city_type,
                            'province': prov_name,
                            'country': 'Indonesia',
                            'country_code': 'ID'
                        }
                
                # Index kecamatan
                for kecamatan in city.get('kecamatan', []):
                    if kecamatan.lower() not in index:
                        index[kecamatan.lower()] = {
                            'name': kecamatan,
                            'type': 'kecamatan',
                            'city': city_name,
                            'province': prov_name,
                            'country': 'Indonesia',
                            'country_code': 'ID'
                        }
        
        # === INDEX GLOBAL ===
        for country in self.global_data.get('countries', []):
            country_name = country['name']
            country_code = country.get('code', '')
            
            # Index negara
            index[country_name.lower()] = {
                'name': country_name,
                'type': 'country',
                'country': country_name,
                'country_code': country_code
            }
            
            # Index alias negara
            for alias in country.get('aliases', []):
                if alias.lower() not in index:
                    index[alias.lower()] = {
                        'name': country_name,
                        'type': 'country',
                        'country': country_name,
                        'country_code': country_code
                    }
            
            # Index kota dalam negara
            for city in country.get('cities', []):
                city_name = city['name']
                
                if city_name.lower() not in index:
                    index[city_name.lower()] = {
                        'name': city_name,
                        'type': 'city',
                        'country': country_name,
                        'country_code': country_code
                    }
                
                # Index alias kota
                for alias in city.get('aliases', []):
                    if alias.lower() not in index:
                        index[alias.lower()] = {
                            'name': city_name,
                            'type': 'city',
                            'country': country_name,
                            'country_code': country_code
                        }
        
        return index
    
    def detect_location_from_text(self, text: str) -> List[dict]:
        """
        Deteksi lokasi dari teks (bio atau caption).
        Optimized version untuk ribuan lokasi.
        """
        if not text:
            return []
        
        detected = []
        text_lower = text.lower()
        
        # Tokenize text untuk pencarian kata tunggal (sangat cepat)
        tokens = set(re.findall(r'\b\w+\b', text_lower))
        
        # 1. Cek Kata Tunggal (Single word locations) via Set Lookup
        for token in tokens:
            if len(token) >= 3 and token in self.location_index:
                loc_info = self.location_index[token]
                # Pastikan ini benar-benar single word key (tidak punya spasi)
                if ' ' not in token:
                    if not any(d['name'] == loc_info['name'] for d in detected):
                        detected.append(loc_info.copy())

        # 2. Cek Kata Majemuk (Multi-word locations) via Loop (hanya untuk keys dengan spasi)
        multi_word_locations = [k for k in self.location_index.keys() if ' ' in k]
        sorted_multi = sorted(multi_word_locations, key=len, reverse=True)
        
        for location_key in sorted_multi:
            if len(location_key) < 3:
                continue
            
            # Gunakan word boundary only if necessary
            if location_key in text_lower:
                # Double check with word boundary to avoid partial matches
                pattern = r'\b' + re.escape(location_key) + r'\b'
                if re.search(pattern, text_lower):
                    location_info = self.location_index[location_key]
                    if not any(d['name'] == location_info['name'] for d in detected):
                        detected.append(location_info.copy())
        
        return detected
    
    def detect_location_from_geotag(self, location_name: str) -> Optional[dict]:
        """
        Parse locationName dari geotag Instagram.
        Format biasanya: "Nama Tempat, Kota" atau "Kota, Negara"
        """
        if not location_name:
            return None
        
        # Split by comma dan cari match
        parts = [p.strip() for p in location_name.split(',')]
        
        # Coba exact match dulu
        for part in parts:
            part_lower = part.lower()
            if part_lower in self.location_index:
                return self.location_index[part_lower].copy()
        
        # Jika tidak ada exact match, coba partial match
        for part in parts:
            for location_key, location_info in self.location_index.items():
                if len(location_key) >= 3:
                    if location_key in part.lower() or part.lower() in location_key:
                        return location_info.copy()
        
        # Return raw geotag jika tidak ada match
        return {
            'name': location_name,
            'type': 'unknown',
            'country': 'Unknown',
            'country_code': ''
        }
    
    def analyze_kol_location(
        self,
        bio: str = "",
        captions: List[str] = None,
        geotags: List[str] = None
    ) -> dict:
        """
        Analisis lengkap lokasi KOL dari berbagai sumber.
        
        Args:
            bio: Bio/biography dari profile Instagram
            captions: List caption dari posts (10-20 posts)
            geotags: List locationName dari posts
        
        Returns:
            {
                'primary_location': str,           # Lokasi utama terdeteksi
                'primary_country': str,            # Negara
                'primary_province': str,           # Provinsi (jika Indonesia)
                'confidence': str,                 # HIGH, MEDIUM, LOW, UNKNOWN
                'confidence_score': float,         # 0.0 - 1.0
                'all_locations': List[str],        # Semua lokasi terdeteksi
                'sources': {
                    'bio': List[str],
                    'captions': List[str],
                    'geotags': List[str]
                }
            }
        """
        captions = captions or []
        geotags = geotags or []
        
        sources = {
            'bio': [],
            'captions': [],
            'geotags': []
        }
        
        location_counts = Counter()
        location_details = {}
        
        # 1. Analisis Bio (bobot tertinggi = 3)
        bio_locations = self.detect_location_from_text(bio)
        for loc in bio_locations:
            loc_name = loc['name']
            sources['bio'].append(loc_name)
            location_counts[loc_name] += 3
            location_details[loc_name] = loc
        
        # 2. Analisis Captions (bobot = 1 per caption)
        for caption in captions:
            caption_locations = self.detect_location_from_text(caption)
            for loc in caption_locations:
                loc_name = loc['name']
                if loc_name not in sources['captions']:
                    sources['captions'].append(loc_name)
                location_counts[loc_name] += 1
                location_details[loc_name] = loc
        
        # 3. Analisis Geotags (bobot = 2, sangat akurat)
        for geotag in geotags:
            if geotag:
                geotag_location = self.detect_location_from_geotag(geotag)
                if geotag_location and geotag_location.get('type') != 'unknown':
                    loc_name = geotag_location['name']
                    if loc_name not in sources['geotags']:
                        sources['geotags'].append(loc_name)
                    location_counts[loc_name] += 2
                    location_details[loc_name] = geotag_location
        
        # Hitung hasil
        if not location_counts:
            return {
                'primary_location': None,
                'primary_country': None,
                'primary_province': None,
                'confidence': 'UNKNOWN',
                'confidence_score': 0.0,
                'all_locations': [],
                'sources': sources
            }
        
        # Lokasi dengan count terbanyak
        primary_location = location_counts.most_common(1)[0][0]
        primary_count = location_counts[primary_location]
        primary_info = location_details.get(primary_location, {})
        
        # Hitung confidence
        in_bio = primary_location in sources['bio']
        in_geotags = primary_location in sources['geotags']
        in_captions = primary_location in sources['captions']
        
        # Confidence scoring
        if (in_bio and in_geotags) or (in_bio and in_captions and primary_count >= 4):
            confidence = 'HIGH'
            confidence_score = 0.9
        elif in_bio or in_geotags or primary_count >= 3:
            confidence = 'MEDIUM'
            confidence_score = 0.6
        else:
            confidence = 'LOW'
            confidence_score = 0.3
        
        return {
            'primary_location': primary_location,
            'primary_country': primary_info.get('country'),
            'primary_country_code': primary_info.get('country_code'),
            'primary_province': primary_info.get('province'),
            'primary_type': primary_info.get('type'),
            'confidence': confidence,
            'confidence_score': confidence_score,
            'all_locations': list(location_counts.keys()),
            'sources': sources
        }
    
    def search_locations(self, query: str, limit: int = 10) -> List[dict]:
        """Search lokasi berdasarkan query (untuk autocomplete)"""
        if not query or len(query) < 2:
            return []
        
        query_lower = query.lower()
        results = []
        seen_names = set()
        
        for location_key, location_info in self.location_index.items():
            if query_lower in location_key:
                if location_info['name'] not in seen_names:
                    results.append(location_info.copy())
                    seen_names.add(location_info['name'])
                    if len(results) >= limit:
                        break
        
        return results
    
    def get_popular_locations(self) -> dict:
        """Get daftar lokasi populer"""
        return {
            'indonesia': self.indonesia_data.get('popular_locations', []),
            'global': self.global_data.get('popular_global_cities', [])
        }


# Singleton instance
_location_service = None

def get_location_service() -> LocationService:
    """Get singleton instance of LocationService"""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    service = get_location_service()
    
    print("\n" + "=" * 60)
    print("LOCATION SERVICE TEST - GLOBAL + INDONESIA")
    print("=" * 60)
    
    # Test 1: Indonesia KOL
    print("\nTEST 1: Indonesia KOL")
    result = service.analyze_kol_location(
        bio="Beauty Content Creator 💄 Based in Klaten, Jawa Tengah 📍",
        captions=[
            "Jalan-jalan ke Solo!",
            "Back to Klaten",
            "Weekend di Prambanan"
        ],
        geotags=["Klaten, Central Java", "Solo Grand Mall"]
    )
    print(f"   Location: {result['primary_location']}")
    print(f"   Country: {result['primary_country']}")
    print(f"   Province: {result['primary_province']}")
    print(f"   Confidence: {result['confidence']}")
    
    # Test 2: Global KOL - Singapore
    print("\nTEST 2: Singapore KOL")
    result = service.analyze_kol_location(
        bio="Fashion Blogger 👗 Singapore 🇸🇬 DM for collabs",
        captions=[
            "Exploring Orchard Road today!",
            "Weekend brunch at Marina Bay Sands",
            "Back in SG after my trip"
        ],
        geotags=["Singapore", "Marina Bay Sands, Singapore"]
    )
    print(f"   Location: {result['primary_location']}")
    print(f"   Country: {result['primary_country']}")
    print(f"   Confidence: {result['confidence']}")
    
    # Test 3: Global KOL - USA
    print("\nTEST 3: USA KOL")
    result = service.analyze_kol_location(
        bio="NYC based photographer 📸 Available worldwide",
        captions=[
            "Sunset in Manhattan",
            "Brooklyn vibes",
            "Central Park morning run"
        ],
        geotags=["New York City", "Brooklyn, NY"]
    )
    print(f"   Location: {result['primary_location']}")
    print(f"   Country: {result['primary_country']}")
    print(f"   Confidence: {result['confidence']}")
    
    # Test 4: Malaysia KOL
    print("\nTEST 4: Malaysia KOL")
    result = service.analyze_kol_location(
        bio="Food blogger KL 🍜 Halal food reviews",
        captions=[
            "Best nasi lemak in Kuala Lumpur!",
            "Petaling Jaya food hunt",
            "Penang trip coming soon"
        ],
        geotags=["Kuala Lumpur, Malaysia"]
    )
    print(f"   Location: {result['primary_location']}")
    print(f"   Country: {result['primary_country']}")
    print(f"   Confidence: {result['confidence']}")
    
    print("\n[OK] All tests completed!")
