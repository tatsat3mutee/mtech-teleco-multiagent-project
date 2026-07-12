# AWS Deployment Guide (EC2 + Docker Compose)

This guide deploys the full RCA platform to a single AWS EC2 instance using the
existing `docker-compose.yml` and `deploy/setup_vps.sh` bootstrap script. No
AWS-specific code changes are required — Docker Compose runs identically on EC2.

## ⚡ Tonight checklist (total hands-on ≈ 20 min)

1. ☐ Create AWS account → verify email/card → sign in to console
2. ☐ **§8 first**: create $5/month budget alert (2 min — do not skip)
3. ☐ EC2 → Launch instance per §2, pasting `deploy/aws-user-data.sh` into
   **Advanced details → User data** (auto-installs everything at boot)
4. ☐ Wait ~5–8 min, SSH in, add keys: `sudo nano /opt/rca-platform/.env`
   (GROQ_API_KEY, OPENROUTER_API_KEY, RCA_API_KEY, CORS_ORIGINS)
5. ☐ `sudo systemctl start rca-platform` → wait for build → open
   `http://<EC2_PUBLIC_IP>:8501`
6. ☐ `aws ec2 stop-instances` (or console Stop) when done — pay ~$2/mo idle

> **Co-hosting DevPulse (ai-pulse) on the same box?** Use **30 GB** storage in
> step 3 and follow §9 (Caddy owns 80/443 — skip the nginx overlay).

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
8. **Advanced details → User data:** paste the contents of
   [`deploy/aws-user-data.sh`](../deploy/aws-user-data.sh). This runs the full
   bootstrap automatically at first boot (Docker, repo clone, 2 GB swap, firewall,
   systemd service, image pre-build) — progress log at `/var/log/rca-bootstrap.log`.
9. Launch.

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

> If you pasted `deploy/aws-user-data.sh` as User data in §2, bootstrap already ran
> at boot — skip straight to “Add your API keys” below. Check
> `sudo tail -50 /var/log/rca-bootstrap.log` if anything looks off.

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

Set at minimum:

```ini
GROQ_API_KEY=gsk_...                  # required
OPENROUTER_API_KEY=sk-or-...          # fallback pool (recommended)
RCA_API_KEY=<long-random-string>      # protects the public FastAPI endpoint
CORS_ORIGINS=http://<EC2_PUBLIC_IP>:8501,http://<EC2_PUBLIC_IP>
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

For a clean `http://<ip>/` URL, use the provided overlay file — no editing needed:

```bash
cd /opt/rca-platform
docker compose -f docker-compose.yml -f docker-compose.nginx.yml up -d --build
```

(To make the systemd service use it permanently, edit `ExecStart`/`ExecStop` in
`/etc/systemd/system/rca-platform.service` to include both `-f` flags, then
`sudo systemctl daemon-reload && sudo systemctl restart rca-platform`.)

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

---

## 9. Co-hosting DevPulse (ai-pulse) on the same instance

One `t3.medium` comfortably runs both projects: the RCA stack uses ~1.5–1.8 GB,
DevPulse (single Bun container, Neon-hosted DB) ~0.4 GB, Caddy + OS ~0.4 GB —
≈2.5 GB of 4 GB, plus the 2 GB swap from `aws-user-data.sh`.

**Changes vs. single-project setup:**

| Setting | Single project | Co-hosted |
|---|---|---|
| Storage | 20 GB gp3 | **30 GB gp3** (two Docker images + build cache) |
| Port 80/443 | optional nginx overlay | **Caddy owns 80/443** — do NOT use `docker-compose.nginx.yml` |
| Security group | §3 | §3 **plus** 443 from anywhere; port 3000 stays closed (Caddy proxies internally) |
| Elastic IP | skip | **keep one** (stable DNS for both subdomains; ~$3.6/mo while stopped — acceptable) |

**Deploy DevPulse** after §4, following `ai-pulse/DEPLOY_AWS.md` §§2–4 (clone,
`backend/.env`, `docker run -p 3000:3000`). Then install Caddy (its §5) with a
combined Caddyfile routing both apps:

```
# /etc/caddy/Caddyfile — one front door, two apps, auto-HTTPS for both
devpulse.tatsatpandey.com {
    reverse_proxy localhost:3000
}

rca.tatsatpandey.com {
    reverse_proxy localhost:8501     # Caddy handles Streamlit WebSockets natively
}

rca-api.tatsatpandey.com {
    reverse_proxy localhost:8000     # optional: expose FastAPI (RCA_API_KEY required)
}
```

```bash
sudo systemctl restart caddy
```

**DNS:** A records for `devpulse`, `rca` (and optionally `rca-api`) → the Elastic IP.

**RCA `.env` addition** — allow the new origin:

```ini
CORS_ORIGINS=https://rca.tatsatpandey.com,https://devpulse.tatsatpandey.com
```

**LLM quota isolation (important):** DevPulse's summarizer is Groq-first
(token bucket rpm=25 in `backend/src/llm/client.ts`) and RCA's router caps at
rpm=28 — together they over-budget a single shared Groq account's 30 rpm cap
during overlapping bursts. Use **two separate free Groq accounts** (one key per
app). Keep one OpenRouter account with a $10 lifetime credit balance (unlocks
1000 free-model requests/day) shared by both apps + the RCA LLM-judge.

Both apps stop/start together with the instance — one Stop click pauses all compute
billing for the pair.

