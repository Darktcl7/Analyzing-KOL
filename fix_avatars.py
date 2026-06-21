"""
Script untuk download foto profil yang belum ada di lokal.
Menggunakan ThreadPoolExecutor untuk mengunduh foto profil secara paralel.
"""
import json
import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = 'influencers.json'
SAVE_DIR = os.path.join('static', 'profiles')
STATUS_FILE = 'scraping_status.json'
DEFAULT_AVATAR = '/static/default-avatar.png'

def update_status(text, is_running=True, progress=0):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump({
                'status': text,
                'is_running': is_running,
                'progress': progress,
                'updated_at': datetime.now().isoformat()
            }, f)
    except: pass

def download_avatar(username, url):
    """Download satu avatar, return local path atau default avatar jika gagal."""
    if not url:
        return DEFAULT_AVATAR
    
    # Sudah lokal
    if url.startswith('/static/') or url.startswith('static/'):
        filepath = url.lstrip('/')
        if os.path.exists(filepath):
            return url if url.startswith('/') else f'/{url}'
        return DEFAULT_AVATAR
    
    filename = f"{username}.jpg"
    filepath = os.path.join(SAVE_DIR, filename)
    
    # Sudah ada file-nya
    if os.path.exists(filepath):
        return f"/static/profiles/{filename}"
    
    # Download dari URL
    try:
        resp = requests.get(url, timeout=3, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            return f"/static/profiles/{filename}"
        else:
            return DEFAULT_AVATAR
    except Exception:
        return DEFAULT_AVATAR

def main():
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    print("=" * 60)
    print(" DOWNLOAD FOTO PROFIL KE LOKAL (PARALEL)")
    print("=" * 60)
    
    # Load data
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] {INPUT_FILE} tidak ditemukan!")
        return
        
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total = len(data)
    print(f"\n[INFO] Total profil di database: {total}")
    
    # Cari yang perlu didownload atau diperbarui dari URL eksternal
    need_download = []
    
    for kol in data:
        img = kol.get('image', '')
        username = kol.get('username', '')
        if not username:
            continue
            
        # Jika gambarnya kosong, atau expired cdn url
        if not img or not (img.startswith('/static/') or img.startswith('static/')):
            need_download.append(kol)
        else:
            # Pastikan file lokalnya benar-benar ada
            filepath = img.lstrip('/')
            if not os.path.exists(filepath):
                need_download.append(kol)
                
    print(f"[INFO] Perlu download/diperbarui: {len(need_download)}")
    
    if not need_download:
        print("\n[OK] Semua foto profil sudah ada di lokal!")
        update_status("Semua foto profil sudah lengkap.", False)
        return
    
    update_status(f"Mengunduh {len(need_download)} foto profil secara paralel...", True, 0)
    
    downloaded = 0
    failed = 0
    
    # Menjalankan download paralel dengan 80 workers
    max_workers = 80
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_kol = {
            executor.submit(download_avatar, kol.get('username'), kol.get('image')): kol 
            for kol in need_download
        }
        
        for i, future in enumerate(as_completed(future_to_kol), 1):
            kol = future_to_kol[future]
            username = kol.get('username')
            try:
                result = future.result()
                kol['image'] = result
                if result != DEFAULT_AVATAR:
                    downloaded += 1
                    print(f"  [{i}/{len(need_download)}] OK @{username}")
                else:
                    failed += 1
                    print(f"  [{i}/{len(need_download)}] FAIL/DEFAULT @{username}")
            except Exception as e:
                kol['image'] = DEFAULT_AVATAR
                failed += 1
                print(f"  [{i}/{len(need_download)}] ERROR @{username}: {e}")
            
            # Update status progress
            if i % 10 == 0 or i == len(need_download):
                progress = round(i / len(need_download) * 100, 1)
                update_status(
                    f"Mengunduh foto profil: {i}/{len(need_download)} ({downloaded} berhasil, {failed} default/gagal)",
                    True, progress
                )
                
    # Simpan data yang sudah diupdate
    print(f"\n[INFO] Menyimpan database yang diperbarui...")
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    msg = f"Download foto selesai: {downloaded} berhasil, {failed} menggunakan default avatar dari {len(need_download)} profil."
    print(f"\n[SELESAI] {msg}")
    update_status(msg, False)

if __name__ == '__main__':
    main()
