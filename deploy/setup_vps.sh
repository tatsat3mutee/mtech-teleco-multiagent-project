#!/usr/bin/env bash
# Bootstrap script for Ubuntu 22.04 / 24.04 / 26.04 LTS
# (Hetzner CX21 / DigitalOcean Basic / Vultr 1GB / AWS EC2)
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

    # Ubuntu codename (from os-release; always present). Docker's apt repo can
    # lag brand-new Ubuntu releases (e.g. 26.04), so if the repo has no dist for
    # this codename yet, fall back to the latest known-good LTS (noble / 24.04),
    # whose packages are forward-compatible. This keeps first boot from aborting.
    CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
    if ! curl -fsSL "https://download.docker.com/linux/ubuntu/dists/${CODENAME}/Release" >/dev/null 2>&1; then
        echo "Docker repo has no '${CODENAME}' dist yet — falling back to 'noble'."
        CODENAME="noble"
    fi

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
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
    echo "  Recommended: OPENROUTER_API_KEY (fallback pool), RCA_API_KEY (API auth),"
    echo "               CORS_ORIGINS (your public URL)"
    echo "  Optional: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY (observability)"
fi

# ── 6. Firewall ─────────────────────────────────────────────────────
ufw --force enable
ufw allow ssh
ufw allow 80/tcp    # Caddy HTTP (ACME challenge + HTTP→HTTPS redirect)
ufw allow 443/tcp   # Caddy HTTPS (both apps) — REQUIRED for the live site
ufw allow 8501/tcp  # Streamlit direct (debug; AWS SG already restricts to your IP)
ufw allow 5000/tcp  # MLflow direct (debug; AWS SG already restricts to your IP)
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
