#!/usr/bin/env bash
# ==============================================================================
# Setup Script for VM 2 (LiveKit Server + LiveKit SIP Gateway on GCP Ubuntu)
# Run as root: sudo bash setup_livekit_vm.sh
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "🚀 Installing Redis, LiveKit Server & LiveKit SIP..."
echo "=========================================================="

# 1. Update system & install dependencies
apt-get update
apt-get install -y curl wget redis-server ufw docker.io

# 2. Configure & start Redis
systemctl enable redis-server
systemctl restart redis-server

# 3. Install LiveKit Server binary (Open-Source)
echo "📥 Downloading LiveKit Server..."
curl -sSL https://get.livekit.io | bash

# 4. Pull official LiveKit SIP Docker image
echo "📥 Pulling LiveKit SIP Docker image..."
systemctl enable docker
systemctl restart docker
docker pull livekit/sip:latest

# 5. Create config directory
mkdir -p /etc/livekit
if [ ! -f /etc/livekit/livekit.yaml ]; then
    cp livekit.yaml /etc/livekit/livekit.yaml
fi
if [ ! -f /etc/livekit/sip.yaml ]; then
    cp sip.yaml /etc/livekit/sip.yaml
fi

# 6. Create systemd service for LiveKit Server
cat << 'EOF' > /etc/systemd/system/livekit-server.service
[Unit]
Description=LiveKit Server
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=root
LimitNOFILE=65535
ExecStart=/usr/local/bin/livekit-server --config /etc/livekit/livekit.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 7. Create systemd service for LiveKit SIP (Docker container with --net=host)
cat << 'EOF' > /etc/systemd/system/livekit-sip.service
[Unit]
Description=LiveKit SIP Gateway (Docker)
After=network.target docker.service livekit-server.service
Requires=docker.service
Wants=livekit-server.service

[Service]
Type=simple
User=root
LimitNOFILE=65535
ExecStartPre=-/usr/bin/docker stop livekit-sip
ExecStartPre=-/usr/bin/docker rm livekit-sip
ExecStart=/usr/bin/docker run --name livekit-sip --net=host -v /etc/livekit/sip.yaml:/etc/livekit/sip.yaml livekit/sip:latest --config /etc/livekit/sip.yaml
ExecStop=/usr/bin/docker stop livekit-sip
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 8. Reload systemd and start services
systemctl daemon-reload
systemctl enable livekit-server
systemctl restart livekit-server
systemctl enable livekit-sip
systemctl restart livekit-sip

echo "=========================================================="
echo "✅ LiveKit Server & SIP installed and running!"
echo "Status check:"
systemctl status livekit-server --no-pager
systemctl status livekit-sip --no-pager
echo "=========================================================="
