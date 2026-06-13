# AWS Deployment Guide (EC2 + Docker Compose)

This guide deploys the full RCA platform to a single AWS EC2 instance using the
existing `docker-compose.yml` and `deploy/setup_vps.sh` bootstrap script. No
AWS-specific code changes are required — Docker Compose runs identically on EC2.

---

## 1. Sizing & cost

The stack runs four containers. Approximate memory budget:

| Service   | Memory limit |
|-----------|--------------|
| Streamlit | 2.0 GB |
| API       | 1.0 GB |
| MLflow    | 0.5 GB |
| Redis     | 0.25 GB |
| **Total** | **~3.75 GB** |

**Recommended instance: `t3.medium` (2 vCPU, 4 GB RAM).**

- The AWS free-tier `t2.micro`/`t3.micro` (1 GB) is **too small** — the stack will
  be OOM-killed. Do not use it for the full stack.
- A `t3.small` (2 GB) works only in lean mode (Streamlit alone — see §6).

### Cost with $100 credit

| Mode | Instance | Approx. cost | How long $100 lasts |
|------|----------|--------------|---------------------|
| 24/7 | `t3.medium` | ~$0.0416/hr ≈ $30/mo | ~3 months |
| Stop-when-idle | `t3.medium` | only EBS while stopped (~$2/mo) | many months |

**Tip:** Stop the instance between demos. You keep the disk (EBS) and pay only a
couple of dollars a month for storage. Start it ~10 minutes before a viva/demo.

---

## 2. Launch the EC2 instance

1. EC2 → **Launch instance**.
2. **Name:** `rca-platform`.
3. **AMI:** Ubuntu Server 22.04 LTS (x86_64).
4. **Instance type:** `t3.medium`.
5. **Key pair:** create a new one (e.g. `rca-key`), download the `.pem` — you need
   it to SSH in. Keep it safe.
6. **Storage:** 20 GB gp3 (default 8 GB is too small once the image + ChromaDB are
   built).
7. **Security group:** see §3 below.
8. Launch.

---

## 3. Security group (firewall)

This is the AWS equivalent of the `ufw` rules in `setup_vps.sh`. Create inbound
rules:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | **My IP** | Admin access only |
| HTTP | 80 | Anywhere (0.0.0.0/0) | Nginx (if enabled — see §5) |
| Custom TCP | 8501 | **My IP** | Streamlit direct (demo/debug) |
| Custom TCP | 5000 | **My IP** | MLflow direct (debug) |

> Restrict 22, 8501, and 5000 to **My IP** wherever possible. Only open 80 to the
> world, and only if you front the app with nginx + a domain.

---

## 4. Bootstrap the platform

SSH in (replace with your key path and the instance's public IP):

```bash
ssh -i rca-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Run the existing bootstrap script — it installs Docker, clones the repo, configures
a firewall and a systemd service:

```bash
curl -sL https://raw.githubusercontent.com/tatsat3mutee/mtech-teleco-multiagent-project/main/deploy/setup_vps.sh | sudo bash
```

Add your API keys (at least Groq — free at console.groq.com):

```bash
sudo nano /opt/rca-platform/.env
```

Start the stack:

```bash
sudo systemctl start rca-platform
sudo systemctl status rca-platform
journalctl -u rca-platform -f      # follow logs; first build takes a few minutes
```

The app is then reachable at:

- Streamlit: `http://<EC2_PUBLIC_IP>:8501`
- MLflow:    `http://<EC2_PUBLIC_IP>:5000`

---

## 5. Optional: nginx on port 80

`docker-compose.yml` does **not** include an nginx service, so port 80 is not served
by default. For a demo, hitting Streamlit directly on `:8501` is fine.

If you want a clean `http://<ip>/` URL (and later HTTPS with a domain), add an nginx
service to compose that mounts `deploy/nginx.conf`:

```yaml
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - streamlit
      - mlflow
    restart: unless-stopped
    networks:
      - rca_net
```

The provided `nginx.conf` already proxies `/` → Streamlit and `/mlflow/` → MLflow on
the `rca_net` Docker network.

---

## 6. Lean mode (cost-saving, `t3.small` / 2 GB)

To run only the Streamlit app (no API, MLflow, or Redis), start a single service:

```bash
cd /opt/rca-platform
docker compose up -d --build streamlit
```

MLflow tracking falls back to local file logging inside the container; the API and
Redis features are unavailable in this mode. Good enough for a UI walkthrough.

---

## 7. Stop, start, and clean up

```bash
# From your laptop, via AWS console or CLI:
aws ec2 stop-instances  --instance-ids <id>   # stop (keep disk, ~$2/mo)
aws ec2 start-instances --instance-ids <id>   # resume before a demo

# On the box:
sudo systemctl stop rca-platform              # stop containers, keep instance
docker compose -f /opt/rca-platform/docker-compose.yml down
```

When fully done, **terminate** the instance and delete its EBS volume to stop all
charges.

---

## 8. Billing safety (do this first)

1. Billing → **Budgets** → create a budget at **$5/month** with an email alert. AWS
   warns you before any surprise spend.
2. Note: an **Elastic IP** is free only while attached to a *running* instance; it is
   **billed when the instance is stopped**. For demos, skip the Elastic IP (the public
   IP changes on restart, which is fine) or release it when stopping.
3. Stop the instance whenever you are not actively demoing.
