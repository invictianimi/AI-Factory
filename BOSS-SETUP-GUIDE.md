# AI FACTORY — BOSS SETUP GUIDE

**Last Updated:** 2026-02-24
**Estimated Boss Time:** 2-4 hours (one-time)
**Result:** Fully autonomous AI Factory ready to build

---

## PHASE 0: PRE-FLIGHT CHECKLIST

### 0.1 Accounts to Create / Gather

| # | Account | Action | Credential Needed |
|---|---------|--------|-------------------|
| 1 | **GitHub** (invictianimi) | Already exists. Create 2 private repos: `AI-Factory` and `thellmreport-website` | SSH deploy keys (generated in Phase 3) |
| 2 | **Anthropic API** | console.anthropic.com → API Keys → Create | `ANTHROPIC_API_KEY=sk-ant-...` |
| 3 | **OpenAI API** | platform.openai.com → API Keys → Create | `OPENAI_API_KEY=sk-...` |
| 4 | **DeepSeek API** | platform.deepseek.com → API Keys → Create | `DEEPSEEK_API_KEY=sk-...` |
| 5 | **Google AI (Gemini)** | aistudio.google.com → Get API Key | `GOOGLE_API_KEY=AI...` |
| 6 | **Buttondown** | buttondown.com → Sign up (free tier) | `BUTTONDOWN_API_KEY=...` |
| 7 | **Outlook** | aifactory.ops@outlook.com — **CREATED** | Used for factory alert emails via SMTP |
| 8 | **Google Drive** | invicti.animi@gmail.com — **EXISTS** | rclone OAuth (configured in Phase 3) |
| 9 | **Porkbun** | porkbun.com → Account → API Access → Enable | `PORKBUN_API_KEY=pk1_...` and `PORKBUN_API_SECRET=sk1_...` |
| 10 | **X (Twitter)** | Create account manually → Apply for developer access (24-48h approval) | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` |
| 11 | **Substack** | Create free publication "The LLM Report" | Credentials for cross-posting (Phase 2+) |

### 0.2 Fund API Accounts

| Provider | Initial Deposit | Why |
|----------|----------------|-----|
| Anthropic | $50 | Primary LLM provider — build phase + first month runtime |
| OpenAI | $20 | GPT for adversarial review, Codex for code tasks |
| DeepSeek | $10 | Cheap verification and batch processing |
| Google AI | $0 | Free tier sufficient initially |

### 0.3 Porkbun API Setup

1. Log in to porkbun.com
2. Go to **Account** → **API Access**
3. Click **Enable API Access**
4. Generate API key pair — save both:
   - API Key: `pk1_xxxxxxxx...`
   - API Secret: `sk1_xxxxxxxx...`
5. **Do NOT use Porkbun hosting** — only DNS. Claude Code will point DNS at Vercel/Netlify/Cloudflare Pages.

---

## PHASE 1: UBUNTU-1 VM SETUP

### 1.1 Hyper-V Resource Adjustment

Open **Hyper-V Manager** on your Windows host:

1. Right-click **Ubuntu-1** → **Settings**
2. **Memory:** Set to 8192 MB minimum (12288 MB recommended). Enable Dynamic Memory.
3. **Processor:** Set to 4 virtual processors
4. **Hard Drive:** Expand to 50GB+ if currently smaller
5. **Network Adapter:** Ensure connected to **External Virtual Switch** (internet access required)
6. Click **OK** and start the VM

### 1.2 SSH Setup (So You Can PuTTY/SSH In)

**On Ubuntu-1** (logged in directly or via Hyper-V console):

```bash
# Install OpenSSH Server
sudo apt update
sudo apt install -y openssh-server

# Start and enable SSH service
sudo systemctl start ssh
sudo systemctl enable ssh

# Verify it's running
sudo systemctl status ssh
# Should show "active (running)"

# Check Ubuntu-1's IP address
ip addr show | grep "inet " | grep -v 127.0.0.1
# Note the IP address (e.g., 192.168.1.xxx or 172.x.x.x)

# Optional: Allow SSH through firewall (if UFW is active)
sudo ufw allow ssh
```

**On your Windows machine:**

1. Open **PuTTY**
2. Host Name: `<Ubuntu-1 IP from above>`
3. Port: `22`
4. Connection type: `SSH`
5. (Optional) Save the session as "Ubuntu-1" for quick access
6. Click **Open** → Login with your Ubuntu-1 username and password

**For Windows Terminal / PowerShell (alternative to PuTTY):**
```powershell
ssh username@<Ubuntu-1-IP>
```

**Make the IP static (recommended):**
```bash
# On Ubuntu-1, check your network interface name
ip link show
# Usually "eth0" or "ens33" or similar

# Edit netplan config
sudo nano /etc/netplan/01-netcfg.yaml
```

Example static IP config:
```yaml
network:
  version: 2
  ethernets:
    eth0:  # Replace with your interface name
      dhcp4: no
      addresses:
        - 192.168.1.100/24  # Pick an unused IP on your network
      gateway4: 192.168.1.1  # Your router's IP
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

```bash
# Apply the config
sudo netplan apply

# Verify
ip addr show
```

### 1.3 Create Dedicated Factory User

```bash
# Create aifactory user with admin privileges
sudo adduser aifactory
sudo usermod -aG sudo aifactory

# Switch to the new user
su - aifactory
```

### 1.4 Install Dependencies

```bash
# System packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    curl git ssh build-essential python3 python3-pip python3-venv \
    nodejs npm sqlite3 jq ripgrep wget ca-certificates gnupg \
    docker.io docker-compose-v2 tmux htop samba rclone

# Add aifactory user to docker group (no sudo needed for docker commands)
sudo usermod -aG docker aifactory
newgrp docker

# Verify Docker
docker run hello-world

# Install Claude Code
sudo npm install -g @anthropic-ai/claude-code

# Install Node.js 20+ (if default is older)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify versions
node --version    # Should be 20+
npm --version
python3 --version # Should be 3.12+
docker --version
claude --version
```

---

## PHASE 2: NETWORK SHARE & DIRECTORY STRUCTURE

### 2.1 Mount Windows Transport Share

The transport share at `smb://vitsim/transport` is your bridge between Windows and Ubuntu-1.

```bash
# Create mount point
sudo mkdir -p /mnt/transport

# Install CIFS utilities
sudo apt install -y cifs-utils

# Create credentials file (so password isn't in fstab)
sudo nano /etc/samba/transport-creds
```

Add your Windows credentials:
```
username=YOUR_WINDOWS_USERNAME
password=YOUR_WINDOWS_PASSWORD
domain=VITSIM
```

```bash
# Secure the credentials file
sudo chmod 600 /etc/samba/transport-creds

# Add to fstab for persistent mount
sudo nano /etc/fstab
```

Add this line:
```
//vitsim/transport /mnt/transport cifs credentials=/etc/samba/transport-creds,uid=aifactory,gid=aifactory,iocharset=utf8 0 0
```

```bash
# Mount it now
sudo mount -a

# Verify
ls /mnt/transport/
# You should see the transport share contents
```

### 2.2 Create AI-Factory Directory on Transport Share

```bash
# Create the shared subdirectory
mkdir -p /mnt/transport/AI-Factory

# This is where you'll drop files from Windows
# Windows path: \\vitsim\transport\AI-Factory
# Ubuntu path:  /mnt/transport/AI-Factory
```

### 2.3 Create Local Working Directory

```bash
# Main workspace (this is where Claude Code operates)
mkdir -p /home/aifactory/AI-Factory

# Symlink for convenience
ln -s /home/aifactory/AI-Factory ~/factory
```

---

## PHASE 3: GITHUB, GOOGLE DRIVE & SYNC SETUP

### 3.1 Generate SSH Key for GitHub

```bash
# Generate ed25519 key for AI-Factrory
ssh-keygen -t ed25519 -C "aifactory@ubuntu-1" -f ~/.ssh/id_ed25519_github
# Press Enter for no passphrase (required for autonomous operation)

# Display public key
cat ~/.ssh/id_ed25519_github.pub
```

**Copy the public key, then on GitHub:**
1. Go to `github.com/invictianimi/AI-Factory` → Settings → Deploy Keys → Add
2. Paste the public key, check **Allow write access**, name it "Ubuntu-1 Factory"

```bash
# Generate ed25519 key for thellmreport-website
ssh-keygen -t ed25519 -C "aifactory@ubuntu-1-website" -f ~/.ssh/id_ed25519_website

# Display public key
cat ~/.ssh/id_ed25519_website.pub
```
**Copy the public key, then on GitHub:**
1. Go to `github.com/invictianimi/thellmreport-website` → Settings → Deploy Keys → Add
2. Paste the public key, check **Allow write access**, name it "Ubuntu-1 Website"

```bash
# Configure SSH to use this key for GitHub
cat >> ~/.ssh/config << 'EOF'
Host github.com-factory
    HostName github.com
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes

Host github.com-website
    HostName github.com
    IdentityFile ~/.ssh/id_ed25519_website
    IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config

# Test connection
ssh -T git@github.com-factory
# Should say: "Hi invictianimi/AI-Factory!"

ssh -T git@github.com-website
# Should say: "Hi invictianimi/thellmreport-website!"
```

### 3.2 Clone / Initialize the Repo

```bash
cd /home/aifactory
git clone git@github.com-factory:invictianimi/AI-Factory.git
cd AI-Factory

# If the clone created an empty repo, or if it fails because the repo is empty:
# git init
# git remote add origin git@github.com-factory:invictianimi/AI-Factory.git

git config user.name "AI Factory"
git config user.email "aifactory.ops@outlook.com"
git config init.defaultBranch main
```

### 3.3 Configure Google Drive Sync (rclone)

This connects to your **invicti.animi@gmail.com** Google Drive, folder: `My Drive/AI-Factory`

```bash
rclone config
```

Follow these prompts:
```
n) New remote
name> gdrive
Storage> drive         (or type the number for "Google Drive")
client_id>             (press Enter for default)
client_secret>         (press Enter for default)
scope> 1               (Full access)
service_account_file>  (press Enter to skip)
Edit advanced config?> n

Use auto config?> n    ← IMPORTANT: Say NO (headless server)
```

**rclone will display a URL.** This is the critical step:

1. **Copy the entire URL** that rclone displays
2. **On your Windows machine**, open a browser and paste that URL
3. **Log in with `invicti.animi@gmail.com`**
4. **Grant rclone access** when prompted
5. **Copy the verification code** the browser shows you
6. **Paste it back into the Ubuntu-1 terminal** where rclone is waiting

```
Configure this as a Shared Drive (Team Drive)?> n
```

Verify it works:
```bash
# List your Google Drive root
rclone ls gdrive: --max-depth 1

# Create the AI-Factory folder if it doesn't exist
rclone mkdir gdrive:AI-Factory

# Test write
echo "Factory sync test $(date)" > /tmp/sync-test.txt
rclone copy /tmp/sync-test.txt gdrive:AI-Factory/
rclone ls gdrive:AI-Factory/
# Should show sync-test.txt
```

### 3.4 Configure Outlook SMTP for Alerts

The factory sends alert emails from `aifactory.ops@outlook.com`. To enable SMTP sending:

1. Log in to outlook.com as aifactory.ops@outlook.com
2. Go to **Settings** → **View all Outlook settings** → **Mail** → **Sync email**
3. Note the SMTP settings:
   - Server: `smtp-mail.outlook.com`
   - Port: `587`
   - Encryption: `STARTTLS`
   - Username: `aifactory.ops@outlook.com`
   - Password: Your Outlook password

These go in the `.env` file (Phase 4).

### 3.5 Create Tri-Sync Script

This keeps Local ↔ Transport Share ↔ GitHub ↔ Google Drive synchronized:

```bash
cat > /home/aifactory/AI-Factory/scripts/sync.sh << 'SYNCEOF'
#!/bin/bash
# AI Factory Tri-Sync: Local <-> Transport <-> GitHub <-> Google Drive
set -euo pipefail

FACTORY_DIR="/home/aifactory/AI-Factory"
TRANSPORT_DIR="/mnt/transport/AI-Factory"
GDRIVE_REMOTE="gdrive:AI-Factory"
LOG_FILE="$FACTORY_DIR/logs/sync.log"

mkdir -p "$FACTORY_DIR/logs"
echo "[$(date -Iseconds)] Sync started" >> "$LOG_FILE"

# 1. Git: commit and push any local changes
cd "$FACTORY_DIR"
git add -A 2>/dev/null
git diff --cached --quiet || git commit -m "auto-sync: $(date +%Y%m%d-%H%M%S)" 2>/dev/null
git push origin main 2>/dev/null || echo "[$(date -Iseconds)] Git push skipped (no remote or conflict)" >> "$LOG_FILE"

# 2. Transport share: sync bidirectional (local is source of truth)
if mountpoint -q /mnt/transport 2>/dev/null; then
    rsync -av --delete --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
        "$FACTORY_DIR/" "$TRANSPORT_DIR/" 2>/dev/null
    echo "[$(date -Iseconds)] Transport share synced" >> "$LOG_FILE"
else
    echo "[$(date -Iseconds)] Transport share not mounted, skipping" >> "$LOG_FILE"
fi

# 3. Google Drive: sync key files (not the full repo — just outputs, logs, dashboards)
rclone sync "$FACTORY_DIR/outputs/" "$GDRIVE_REMOTE/outputs/" 2>/dev/null
rclone sync "$FACTORY_DIR/logs/" "$GDRIVE_REMOTE/logs/" 2>/dev/null
rclone sync "$FACTORY_DIR/docs/" "$GDRIVE_REMOTE/docs/" 2>/dev/null
rclone copy "$FACTORY_DIR/CLAUDE.md" "$GDRIVE_REMOTE/" 2>/dev/null
echo "[$(date -Iseconds)] Google Drive synced" >> "$LOG_FILE"

echo "[$(date -Iseconds)] Sync complete" >> "$LOG_FILE"
SYNCEOF

chmod +x /home/aifactory/AI-Factory/scripts/sync.sh
```

Add to cron:
```bash
# Run sync every 15 minutes during active hours (6am-11pm), hourly overnight
crontab -e
```

Add:
```cron
*/15 6-23 * * * /home/aifactory/AI-Factory/scripts/sync.sh
0 0-5 * * * /home/aifactory/AI-Factory/scripts/sync.sh
```

---

## PHASE 4: ENVIRONMENT FILE & SECURITY

### 4.1 Create .env File

```bash
cd /home/aifactory/AI-Factory
nano .env
```

Paste and fill in your actual keys:
```bash
# ============================================================
# AI FACTORY — ENVIRONMENT VARIABLES
# This file MUST be in .gitignore. NEVER commit this.
# ============================================================

# --- LLM API Keys ---
ANTHROPIC_API_KEY=sk-ant-REPLACE_ME
OPENAI_API_KEY=sk-REPLACE_ME
DEEPSEEK_API_KEY=sk-REPLACE_ME
GOOGLE_API_KEY=REPLACE_ME

# --- Publishing ---
BUTTONDOWN_API_KEY=REPLACE_ME

# --- Domain / DNS ---
PORKBUN_API_KEY=pk1_REPLACE_ME
PORKBUN_API_SECRET=sk1_REPLACE_ME

# --- Alert Email (Outlook SMTP) ---
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=aifactory.ops@outlook.com
SMTP_PASS=REPLACE_ME
ALERT_FROM=aifactory.ops@outlook.com
ALERT_TO=invicti.animi@gmail.com

# --- X (Twitter) API — fill after developer access approved ---
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=

# --- Claude Code Settings ---
CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000
BASH_DEFAULT_TIMEOUT_MS=120000
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# --- Budget Caps ---
BUDGET_PER_RUN=15
BUDGET_PER_DAY=20
BUDGET_PER_MONTH=200
```

### 4.2 Lock Down Permissions

```bash
# Restrict .env to owner only
chmod 600 .env

# Ensure .gitignore exists and includes .env
cat >> .gitignore << 'EOF'
.env
*.sqlite
*.db
__pycache__/
node_modules/
.venv/
data/chroma/
EOF

# Restrict SSH keys
chmod 600 ~/.ssh/id_ed25519_github
chmod 644 ~/.ssh/id_ed25519_github.pub
```

---

## PHASE 5: COPY STARTER FILES & LAUNCH

### 5.1 Copy Files from Transport Share

Before this step, drop all the generated documents into `\\vitsim\transport\AI-Factory\` from Windows.

```bash
# Copy starter files from transport share to working directory
cp -r /mnt/transport/AI-Factory/* /home/aifactory/AI-Factory/

# Verify structure
ls -la /home/aifactory/AI-Factory/
# Should see: CLAUDE.md, docs/, projects/, .env.example, etc.
```

### 5.2 Initial Git Commit

```bash
cd /home/aifactory/AI-Factory
git add -A
git commit -m "feat: initial factory scaffold with specs and context"
git push -u origin main
```

### 5.3 Launch Claude Code

```bash
# Start a tmux session (persists if SSH disconnects)
tmux new-session -s factory

# Navigate to factory root
cd /home/aifactory/AI-Factory

# Source environment
source <(grep -v '^#' .env | sed 's/^/export /')

# Launch Claude Code
claude
```

**Paste the Build Prompt** (see CLAUDE-CODE-BUILD-PROMPT.md) into Claude Code.

Then sit back. Claude Code builds the entire factory autonomously.

### 5.4 Monitoring While Building

In another terminal/tmux pane:
```bash
# Watch the factory log
tail -f /home/aifactory/AI-Factory/logs/as-built.md

# Check costs
cat /home/aifactory/AI-Factory/logs/cost-log.md

# Check Docker containers (once they're running)
docker ps
```

---

## PHASE 6: POST-BUILD

### 6.1 Review First Test Edition

Claude Code will produce a test newsletter edition. Review it:
```bash
cat /home/aifactory/AI-Factory/projects/the-llm-report/outputs/latest-edition.md
```

### 6.2 Point DNS (Porkbun)

Claude Code will attempt to configure DNS automatically via the Porkbun API. If it needs manual help:

1. Log in to porkbun.com
2. Go to **Domain Management** → **theLLMreport.com** → **DNS**
3. Claude Code will tell you exactly what records to add (typically a CNAME pointing to the hosting platform)

With the API key in `.env`, Claude Code can do this programmatically:
```bash
# Claude Code will use the Porkbun API directly:
# POST https://porkbun.com/api/json/v3/dns/create/thellmreport.com
# No manual steps needed if API key is correct
```

### 6.3 Enable Cron Schedule

```bash
# Add pipeline cron job (Mon/Tue/Wed/Fri at 05:00 UTC + Sat deep-dive at 06:00 UTC)
crontab -e
```

Add:
```cron
# AI Factory — The LLM Report pipeline runs
0 5 * * 1,3,5 cd /home/aifactory/AI-Factory && ./scripts/run-pipeline.sh >> logs/cron.log 2>&1
0 6 * * 6 cd /home/aifactory/AI-Factory && ./scripts/run-pipeline.sh --deep-dive >> logs/cron.log 2>&1

# Sync (already added in Phase 3.5)
*/15 6-23 * * * /home/aifactory/AI-Factory/scripts/sync.sh
0 0-5 * * * /home/aifactory/AI-Factory/scripts/sync.sh
```

### 6.4 Verify Auto-Publish

After the first pipeline run completes:
- [ ] Website loads at theLLMreport.com
- [ ] Newsletter draft appears in Buttondown
- [ ] Costs logged within budget
- [ ] Status dashboard accessible
- [ ] Sync working (check Google Drive `AI-Factory/outputs/`)

---

## QUICK REFERENCE CARD

Print this and keep it near your desk.

```
═══════════════════════════════════════════════════════════
  AI FACTORY — QUICK REFERENCE
═══════════════════════════════════════════════════════════

SSH INTO UBUNTU-1:
  ssh aifactory@<Ubuntu-1-IP>
  (or PuTTY → saved session "Ubuntu-1")

OPEN CLAUDE CODE:
  tmux attach -t factory    ← resume existing session
  -- OR --
  tmux new -s factory       ← start new session
  cd ~/AI-Factory && source <(grep -v '^#' .env | sed 's/^/export /') && claude

CHECK STATUS:
  cat ~/AI-Factory/logs/as-built.md | tail -50
  docker ps
  cat ~/AI-Factory/logs/cost-log.md | tail -20

PAUSE (gentle):     docker compose pause
RESUME:             docker compose unpause
STOP (firm):        docker compose stop
RESTART:            docker compose start
KILL (nuclear):     docker compose down
REBUILD:            docker compose up -d --build

MANUAL SYNC:        ~/AI-Factory/scripts/sync.sh
MANUAL PIPELINE:    ~/AI-Factory/scripts/run-pipeline.sh

VIEW LATEST EDITION:
  cat ~/AI-Factory/projects/the-llm-report/outputs/latest-edition.md

EMERGENCY:
  See docs/EMERGENCY-PROCEDURES.md

COSTS THIS MONTH:
  grep "$(date +%Y-%m)" ~/AI-Factory/logs/cost-log.md | tail -20

═══════════════════════════════════════════════════════════
```
