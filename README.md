# GitPulse 🚀

> AI-powered changelog generator — turns Git commits into human-friendly release notes automatically.

**Live:** https://emrefkrlr.github.io/gitpulse  
**App:** https://gitpulse-2p8d.onrender.com

---

## What it does

Connect your GitHub repo → add a webhook → every `git push` triggers AI to read your commits and draft a changelog. You review it, publish it, done.

No more blank Notion pages. No more copy-pasting commits into ChatGPT before every release.

---

## Features

- **GitHub OAuth** — one-click login, read-only access to your commits
- **Webhook automation** — every push creates a draft changelog automatically
- **AI fallback chain** — DeepSeek → Groq → OpenAI → Anthropic, switches silently on quota/errors
- **Public changelog page** — `gitpulse-2p8d.onrender.com/username/repo`
- **Embed widget** — `<script>` tag or iframe, works on any site
- **Freemium** — 3 changelogs/month free, paid plans from $7/month

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | HTMX + Jinja2 + Tailwind CSS CDN |
| Database | PostgreSQL (Supabase) |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Auth | GitHub OAuth (session-based) |
| AI | DeepSeek / Groq / OpenAI / Anthropic (fallback chain) |
| Payments | Polar.sh |
| Hosting | Render (free tier) |
| Analytics | Google Analytics 4 |

---

## Local Development

### Prerequisites
- Docker + Docker Compose
- GitHub OAuth App
- At least one AI API key

### Setup

```bash
git clone https://github.com/emrefkrlr/gitpulse.git
cd gitpulse
cp .env.example .env
# Fill in .env
docker compose up -d --build
```

App runs at `http://localhost:8000`

### Environment Variables

```env
APP_SECRET_KEY=random-32-char-string
APP_ENV=development
APP_BASE_URL=http://localhost:8000

DATABASE_URL=postgresql+asyncpg://gitpulse:gitpulse_dev@db:5432/gitpulse

GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# At least one required — tried in order, fails silently to next
AI_PROVIDERS=deepseek:sk-...,groq:gsk_...,openai:sk-...

POLAR_ENV=sandbox
POLAR_ACCESS_TOKEN=...
POLAR_WEBHOOK_SECRET=...
POLAR_STARTER_PRODUCT_ID=...
POLAR_PRO_PRODUCT_ID=...
```

### GitHub OAuth App

1. GitHub → Settings → Developer Settings → OAuth Apps → New
2. Homepage URL: `http://localhost:8000`
3. Callback URL: `http://localhost:8000/auth/github/callback`

---

## Ngrok (local webhook testing)

Every PC restart requires these steps:

```bash
# 1. Start Docker
docker compose up -d

# 2. Start ngrok
ngrok http 8000

# 3. Update .env
APP_BASE_URL=https://xxxx.ngrok-free.app

# 4. Restart web
docker compose restart web

# 5. Update GitHub OAuth App callback URL
# 6. Update GitHub repo webhook URL (on project page)
```

---

## Production Deploy

**Database:** Supabase (free PostgreSQL)  
**Backend:** Render (free Web Service, Docker)  
**Payments:** Polar.sh  

See `README.md` deploy section for step-by-step.

---

## Pricing

| Plan | Price | Changelogs/month | Projects |
|---|---|---|---|
| Free | $0 | 3 | 1 |
| Starter | $7/mo | 20 | 3 |
| Pro | $19/mo | Unlimited | 10 |

---

## Project Structure

```
gitpulse/
├── app/
│   ├── main.py              # FastAPI app, middleware, routers
│   ├── config.py            # Pydantic Settings
│   ├── database.py          # Async SQLAlchemy engine
│   ├── models/
│   │   └── user.py          # User, Project, Changelog models
│   ├── routers/
│   │   ├── auth.py          # GitHub OAuth
│   │   ├── dashboard.py     # Dashboard + repo picker
│   │   ├── changelog.py     # Generate / publish / public page
│   │   ├── webhook.py       # GitHub webhook receiver
│   │   ├── embed.py         # Embed script + iframe
│   │   ├── payments.py      # Polar.sh checkout + webhook
│   │   └── pages.py         # Landing, pricing, how-it-works
│   ├── services/
│   │   ├── github.py        # GitHub API wrapper
│   │   ├── ai.py            # Multi-provider fallback chain
│   │   └── auth.py          # Session helpers
│   └── templates/           # Jinja2 HTML templates
│       └── partials/        # HTMX partials
├── alembic/                 # DB migrations
├── index.html               # GitHub Pages landing page
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Security Checklist

- [ ] `APP_SECRET_KEY` is random 32+ chars, never committed
- [ ] `.env` is in `.gitignore`
- [ ] `APP_ENV=production` on Render
- [ ] GitHub OAuth callback URL matches production domain
- [ ] Polar webhook signature verified on every event

---

## Roadmap

- [ ] Email notifications (Resend) — new changelog alerts for subscribers
- [ ] Slack / Discord integration
- [ ] Custom domain support (Pro plan)
- [ ] Monthly usage auto-reset (APScheduler)
- [ ] GitLab support

---

## License

MIT
