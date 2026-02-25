# AI Factory — Security Model Knowledge Base

## Security Principles

1. **Both repos are private** — invictianimi/AI-Factory, invictianimi/thellmreport-website
2. **Deploy keys, not PATs** — SSH ed25519 keys per repo
3. **API keys in .env only** — chmod 600, never committed
4. **LiteLLM proxy local** — API keys never traverse public internet to proxy
5. **No PII in pipeline** — Subscriber data stays in Buttondown only
6. **Git checkpoints** — Before and after every milestone

## API Key Inventory

All keys in `.env`, never in code or logs.

| Key | Provider | Scope | Rotation |
|-----|----------|-------|---------|
| ANTHROPIC_API_KEY | Anthropic | Claude API | Annual |
| OPENAI_API_KEY | OpenAI | GPT API | Annual |
| DEEPSEEK_API_KEY | DeepSeek | DeepSeek API | Annual |
| GOOGLE_API_KEY | Google | Gemini API | Annual |
| BUTTONDOWN_API_KEY | Buttondown | Newsletter API | Annual |
| PORKBUN_API_KEY + SECRET | Porkbun | DNS management | Annual |
| SMTP_USER + SMTP_PASS | Outlook | Email sending | Annual |
| X_API_KEY + X_API_SECRET | X/Twitter | Social posting | Annual |
| LITELLM_MASTER_KEY | Local | LiteLLM proxy auth | Per-deployment |

## Network Security

### Allowlisted Domains
```
api.anthropic.com
api.openai.com
api.deepseek.com
generativelanguage.googleapis.com
github.com, api.github.com
registry.npmjs.org, pypi.org, files.pythonhosted.org
api.buttondown.com
api.x.com
porkbun.com/api
smtp-mail.outlook.com:587
+ source domains from sources.yaml
```

### Docker Network Architecture
- `factory-internal`: Factory ↔ LiteLLM only (no internet)
- `factory-external`: Factory → internet (app-level allowlist)
- LiteLLM has no direct internet access (uses factory-internal only)

## Bridge Security

- Email whitelist: BRIDGE_BOSS_EMAIL_WHITELIST env var
- Non-whitelisted senders: rejected and logged, no action taken
- File drop: inbox only writable by aifactory user
- All Bridge interactions logged in logs/bridge/

## Log Security Rules

- Pipeline logs NEVER contain: API keys, subscriber emails, auth tokens
- Alerts NEVER expose: key values, personal data
- as-built.md NEVER contains: credentials or PII

## Incident Response

1. `factory kill` — immediate pipeline stop
2. `factory pause` — pause between runs
3. `factory rollback` — revert to last git checkpoint
4. Email alert to Vit at configured ALERT_TO address
5. Logs preserved for post-incident board review

## Secrets Rotation

When rotating API keys:
1. Update `.env` file
2. Restart LiteLLM proxy (picks up new env vars)
3. No code changes needed — all keys from environment
