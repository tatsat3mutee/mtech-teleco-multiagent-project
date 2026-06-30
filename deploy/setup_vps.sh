#!/usr/bin/env bash
# Bootstrap script for Ubuntu 22.04 VPS (Hetzner CX21 / DigitalOcean Basic / Vultr 1GB)
# Run as root: curl -sL <raw_url> | bash
# Or: wget -qO- <raw_url> | bash
set -euo pipefail

REPO_URL="https://github.com/tatsat3mutee/mtech-teleco-multiagent-project.git"
REPO_DIR="/opt/rca-platform"
DEPLOY_USER="rca"

echo "=== Telecom RCA Platform — VPS Bootstrap ==="

# ── 1. System packages ──────────────────────────────────────────────
apt-get update -q
apt-get install -y --no-install-recommends \
    curl git ca-certificates gnupg lsb-release ufw

# ── 2. Docker Engine ────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    echo "Docker installed: $(docker --version)"
else
    echo "Docker already installed: $(docker --version)"
fi

# ── 3. Deploy user ──────────────────────────────────────────────────
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    usermod -aG docker "$DEPLOY_USER"
    echo "Created user: $DEPLOY_USER"
fi

# ── 4. Clone / pull repo ────────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
    echo "Pulling latest changes..."
    git -C "$REPO_DIR" pull origin main
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$REPO_DIR"
fi
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$REPO_DIR"

# ── 5. Environment file ─────────────────────────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    echo ""
    echo "IMPORTANT: Edit $REPO_DIR/.env and add your API keys before starting."
    echo "  Required: GROQ_API_KEY (free at console.groq.com)"
    echo "  Optional: GEMINI_API_KEY, DEEPSEEK_API_KEY, KIMI_API_KEY"
fi

# ── 6. Firewall ─────────────────────────────────────────────────────
ufw --force enable
ufw allow ssh
ufw allow 80/tcp    # Nginx HTTP (proxies to Streamlit + MLflow)
ufw allow 8501/tcp  # Streamlit direct (optional, for debugging)
ufw allow 5000/tcp  # MLflow direct (optional, restrict in production)
echo "Firewall configured."

# ── 7. systemd service ──────────────────────────────────────────────
cat > /etc/systemd/system/rca-platform.service <<EOF
[Unit]
Description=Telecom RCA Platform (Docker Compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
User=$DEPLOY_USER
WorkingDirectory=$REPO_DIR
ExecStart=/usr/bin/docker compose up --build
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rca-platform
echo ""
echo "=== Setup complete ==="
echo "Start the platform: systemctl start rca-platform"
echo "View logs:          journalctl -u rca-platform -f"
echo "Streamlit:          http://$(hostname -I | awk '{print $1}'):8501"
echo "MLflow:             http://$(hostname -I | awk '{print $1}'):5000"
