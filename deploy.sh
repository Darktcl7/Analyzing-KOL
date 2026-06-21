#!/bin/bash
# ============================================================================
# DEPLOY SCRIPT - KOL Scouting Project
# ============================================================================
# Jalankan di VPS:
#   chmod +x deploy.sh && ./deploy.sh
# ============================================================================

set -e

echo "=========================================="
echo "KOL SCOUTING PROJECT - DEPLOYMENT"
echo "=========================================="

# Variabel
PROJECT_DIR="/var/www/kol_scouting"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="kolscouting"
PORT=5001

# 1. Install dependencies sistem
echo "[1/6] Installing system dependencies..."
yum install -y python3 python3-pip python3-devel gcc || apt install -y python3 python3-pip python3-venv

# 2. Buat direktori project
echo "[2/6] Setting up project directory..."
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 3. Setup virtual environment
echo "[3/6] Creating virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 4. Install Python packages
echo "[4/6] Installing Python packages..."
pip install --upgrade pip
pip install flask gunicorn apify-client

# 5. Buat systemd service
echo "[5/6] Creating systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=KOL Scouting Flask App
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn --workers 2 --bind 127.0.0.1:$PORT wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable dan start service
echo "[6/6] Starting service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo "Service running on: http://127.0.0.1:$PORT"
echo ""
echo "NEXT STEPS:"
echo "1. Upload project files to $PROJECT_DIR"
echo "2. Configure CyberPanel proxy for /kolproject -> 127.0.0.1:$PORT"
echo "3. Test: curl http://127.0.0.1:$PORT"
echo ""
