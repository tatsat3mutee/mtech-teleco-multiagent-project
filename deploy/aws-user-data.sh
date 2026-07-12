#!/bin/bash
# EC2 User Data — Telecom RCA Platform auto-bootstrap
# Paste this whole file into: EC2 Launch Instance → Advanced details → User data.
# Runs ONCE as root at first boot. After ~5 min the instance is fully provisioned;
# you only SSH in to add API keys to /opt/rca-platform/.env and start the service.
#
# AMI: Ubuntu Server 22.04 or 24.04 LTS (x86_64)
# Instance: t3.medium (4 GB) full stack | t3.small (2 GB) lean mode
set -euxo pipefail
exec > /var/log/rca-bootstrap.log 2>&1   # everything logged here for debugging

# Run the repo's canonical bootstrap (installs Docker, clones repo, ufw,
# creates systemd service 'rca-platform', copies .env.example → .env)
curl -sL https://raw.githubusercontent.com/tatsat3mutee/mtech-teleco-multiagent-project/main/deploy/setup_vps.sh | bash

# 2 GB swap — safety net against OOM during the first image build on t3.medium
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Pre-build images so first 'systemctl start' is fast (keys not needed to build)
cd /opt/rca-platform
docker compose build || true   # non-fatal: service rebuilds on start anyway

echo "=== RCA bootstrap complete: $(date -u) ==="
echo "Next: sudo nano /opt/rca-platform/.env  (add GROQ_API_KEY etc.)"
echo "Then: sudo systemctl start rca-platform"
