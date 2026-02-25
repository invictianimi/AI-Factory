# EMERGENCY PROCEDURES

**Keep this document accessible. Print if needed.**

---

## CONTROL LEVELS

### Level 1 — PAUSE (Gentle)
**Use when:** Reviewing output, costs look weird, want to check something
```bash
docker compose pause
```
- Freezes all containers, state preserved in memory
- Resume with: `docker compose unpause`

### Level 2 — STOP (Firm)
**Use when:** Investigating an issue, need to read logs carefully
```bash
docker compose stop
```
- Graceful shutdown, state saved to disk
- Restart with: `docker compose start`

### Level 3 — KILL (Nuclear)
**Use when:** Something is seriously wrong, runaway costs, unexpected behavior
```bash
docker compose down
```
- Stops and removes all containers
- Persistent data survives in Docker volumes
- Restart requires: `docker compose up -d`

### Level 4 — FULL STOP (Everything Off)
**Use when:** Security concern, compromised API key, unknown activity
```bash
docker compose down
# Revoke/rotate all API keys immediately:
# - Anthropic: console.anthropic.com → API Keys
# - OpenAI: platform.openai.com → API Keys
# - DeepSeek: platform.deepseek.com → API Keys
# Then update .env with new keys
```

---

## COMMON EMERGENCIES

### Costs Spiking
```bash
# Check current spend
cat ~/AI-Factory/logs/cost-log.md | tail -30

# Pause everything
docker compose pause

# Review what's running
docker ps
docker logs ai-news-factory --tail 100

# If costs look runaway, stop everything
docker compose down
```

### Pipeline Producing Bad Content
```bash
# Stop the pipeline
docker compose stop

# Review the latest output
cat ~/AI-Factory/projects/the-llm-report/outputs/latest-edition.md

# Check compliance logs
grep "FAIL" ~/AI-Factory/logs/as-built.md | tail -20

# If already published, the website auto-deploys from Git
# Rollback the website:
cd ~/AI-Factory/projects/the-llm-report/website
git log --oneline -10
git revert HEAD  # Reverts the last commit
git push origin main  # Auto-deploys the rollback
```

### Cannot SSH Into Ubuntu-1
1. Open **Hyper-V Manager** on Windows
2. Right-click Ubuntu-1 → **Connect** (opens console directly)
3. Login and check: `sudo systemctl status ssh`
4. Restart SSH if needed: `sudo systemctl restart ssh`
5. Check IP hasn't changed: `ip addr show`

### Docker Not Starting
```bash
# Check Docker daemon
sudo systemctl status docker
sudo systemctl restart docker

# Check disk space
df -h
# If disk full, clean Docker:
docker system prune -a
```

### Git Conflict / Corrupted Repo
```bash
cd ~/AI-Factory

# Check status
git status

# If messy, stash changes and pull
git stash
git pull origin main

# Nuclear option: re-clone
cd ~
mv AI-Factory AI-Factory-backup-$(date +%Y%m%d)
git clone git@github.com:invictianimi/AI-Factory.git
cp AI-Factory-backup-*/. env AI-Factory/.env
```

### API Key Compromised
```bash
# IMMEDIATELY stop all containers
docker compose down

# Rotate the compromised key at the provider's dashboard
# Update .env with the new key
nano ~/AI-Factory/.env

# Restart
docker compose up -d
```

---

## CHECKING LOGS

```bash
# Factory activity log (most useful)
tail -50 ~/AI-Factory/logs/as-built.md

# Cost tracking
tail -20 ~/AI-Factory/logs/cost-log.md

# Sync log
tail -20 ~/AI-Factory/logs/sync.log

# Docker container logs
docker logs ai-news-factory --tail 100
docker logs ai-news-factory --since 1h

# System resources
htop
df -h
```

---

## CONTACT

- **Factory Email:** aifactory.ops@outlook.com
- **Boss Email:** invicti.animi@gmail.com
- **Claude Code:** SSH into Ubuntu-1, `tmux attach -t factory`, then interact directly
- **Claude.ai:** Check Google Drive → AI-Factory folder for synced outputs and logs
