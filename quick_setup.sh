#!/bin/bash
# ============================================================================
# QUICK SETUP - Jalankan di VPS setelah upload files
# ============================================================================

cd /var/www/kol_scouting

# Create service file
cat > /etc/systemd/system/kolscouting.service << 'ENDSERVICE'
[Unit]
Description=KOL Scouting Flask App
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/kol_scouting
ExecStart=/var/www/kol_scouting/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5001 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
ENDSERVICE

# Reload and start
systemctl daemon-reload
systemctl enable kolscouting
systemctl restart kolscouting
sleep 2
systemctl status kolscouting

echo ""
echo "================================================"
echo "Service should be running on port 5001"
echo "Test: curl http://127.0.0.1:5001"
echo "================================================"
