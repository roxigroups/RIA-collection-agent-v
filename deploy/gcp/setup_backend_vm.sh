#!/usr/bin/env bash
# ==============================================================================
# Setup Script for VM 1 (Backend API, Voice Worker, Dialer on GCP Ubuntu)
# Run as root: sudo bash setup_backend_vm.sh
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "🚀 Bootstrapping VM 1 (RIA Backend & Voice Worker)..."
echo "=========================================================="

APP_DIR="/opt/ria-collection-agent"

# 1. Update system & install Python 3 and system libraries
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl build-essential libpq-dev ffmpeg

# 2. Setup user and permissions if not already present
id -u ubuntu &>/dev/null || useradd -m -s /bin/bash ubuntu

# 3. Create app directory if not cloned yet
mkdir -p "$APP_DIR"
chown -R ubuntu:ubuntu "$APP_DIR"

# 4. Create virtual environment
if [ ! -d "$APP_DIR/backend/.venv" ]; then
    echo "📦 Creating Python virtual environment..."
    sudo -u ubuntu python3 -m venv "$APP_DIR/backend/.venv"
fi

# 5. Install backend dependencies
echo "📥 Installing Python requirements..."
sudo -u ubuntu "$APP_DIR/backend/.venv/bin/pip" install --upgrade pip
sudo -u ubuntu "$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

# 6. Install systemd services
echo "⚙️ Installing systemd service units..."
cp "$APP_DIR/deploy/systemd/ria-api.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/ria-dialer.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/ria-agent.service" /etc/systemd/system/

# Allow ubuntu user to restart ria services without password prompt during CI/CD auto-deploy
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart ria-api, /bin/systemctl restart ria-dialer, /bin/systemctl restart ria-agent, /bin/systemctl restart ria-api ria-dialer ria-agent" > /etc/sudoers.d/ria-deploy
chmod 0440 /etc/sudoers.d/ria-deploy

systemctl daemon-reload

echo "=========================================================="
echo "✅ VM 1 Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Configure $APP_DIR/backend/.env with your Cloud SQL DATABASE_URL and VM 2 LIVEKIT_URL"
echo "2. Run database setup: $APP_DIR/backend/.venv/bin/python setup_db.py"
echo "3. Start all services:"
echo "   sudo systemctl enable --now ria-api"
echo "   sudo systemctl enable --now ria-dialer"
echo "   sudo systemctl enable --now ria-agent"
echo "4. Monitor logs:"
echo "   journalctl -u ria-api -f"
echo "   journalctl -u ria-dialer -f"
echo "   journalctl -u ria-agent -f"
echo "=========================================================="
