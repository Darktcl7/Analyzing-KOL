# Panduan Deploy KOL Scouting ke VPS CyberPanel

## Info Server
- **IP**: 148.230.97.130
- **URL Target**: http://148.230.97.130/kolproject
- **Port Internal**: 5001

---

## Langkah 1: Upload Project ke VPS

### Opsi A: Menggunakan SCP (dari Windows PowerShell)
```powershell
# Dari folder project, jalankan:
scp -r "./*" root@148.230.97.130:/var/www/kol_scouting/
```

### Opsi B: Menggunakan Git (Jika sudah di GitHub)
```bash
# SSH ke VPS
ssh root@148.230.97.130

# Clone repository
cd /var/www
git clone https://github.com/username/kol_scouting.git kol_scouting
```

---

## Langkah 2: Setup di VPS

SSH ke server:
```bash
ssh root@148.230.97.130
```

Jalankan perintah berikut:
```bash
# Buat direktori
mkdir -p /var/www/kol_scouting
cd /var/www/kol_scouting

# Install Python venv (jika belum ada)
yum install -y python3 python3-pip python3-devel  # CentOS/AlmaLinux
# atau
apt install -y python3 python3-pip python3-venv   # Ubuntu/Debian

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask gunicorn apify-client

# Test jalankan
gunicorn --bind 127.0.0.1:5001 wsgi:app
# Ctrl+C untuk stop
```

---

## Langkah 3: Buat Systemd Service

```bash
# Buat file service
nano /etc/systemd/system/kolscouting.service
```

Paste konten berikut:
```ini
[Unit]
Description=KOL Scouting Flask App
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/kol_scouting
Environment="PATH=/var/www/kol_scouting/venv/bin"
ExecStart=/var/www/kol_scouting/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8080 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Simpan (Ctrl+X, Y, Enter), lalu:
```bash
systemctl daemon-reload
systemctl enable kolscouting
systemctl start kolscouting
systemctl status kolscouting  # Pastikan "active (running)"
```

---

## Langkah 4: Konfigurasi CyberPanel Proxy

### Opsi A: Via CyberPanel UI
1. Login ke CyberPanel: https://148.230.97.130:8090
2. Pilih website yang sudah ada
3. Pergi ke: **vHost Conf** atau **Rewrite Rules**
4. Tambahkan proxy rule untuk `/kolproject`

### Opsi B: Edit vHost Config Manual
```bash
nano /usr/local/lsws/conf/vhosts/[nama_website]/vhconf.conf
```

Tambahkan di bagian `context`:
```
context /kolproject {
  type                    proxy
  handler                 127.0.0.1:5001
  addDefaultCharset       off
}
```

Restart LiteSpeed:
```bash
systemctl restart lsws
```

---

## Langkah 5: Test

```bash
# Test internal
curl http://127.0.0.1:5001

# Test via browser
# Buka: http://148.230.97.130/kolproject
```

---

## Troubleshooting

### Cek Log Error
```bash
# Log aplikasi
journalctl -u kolscouting -f

# Log LiteSpeed
tail -f /usr/local/lsws/logs/error.log
```

### Restart Service
```bash
systemctl restart kolscouting
systemctl restart lsws
```

---

## File yang HARUS Ada di /var/www/kol_scouting:
- app.py
- wsgi.py
- location_service.py
- apify_scraper.py
- influencers.json
- requirements.txt
- templates/ (folder)
- data/ (folder dengan indonesia_cities.json, global_cities.json)
