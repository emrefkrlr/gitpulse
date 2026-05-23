# GitPulse 🚀

> Automated marketing-language changelogs from Git commits — for solo developers and indie hackers.

**Stack:** Python 3.12 · FastAPI · HTMX · PostgreSQL · SQLAlchemy async · Jinja2 · Tailwind CSS CDN

---

## Quick start (local)

### 1. Clone & configure

```bash
git clone https://github.com/YOUR_USERNAME/gitpulse.git
cd gitpulse
cp .env.example .env
# Fill in .env — see below
```

### 2. Create a GitHub OAuth App

1. Go to **GitHub → Settings → Developer Settings → OAuth Apps → New OAuth App**
2. Fill in:
   - **Homepage URL:** `http://localhost:8000`
   - **Authorization callback URL:** `http://localhost:8000/auth/github/callback`
3. Copy **Client ID** and **Client Secret** into `.env`

### 3. Configure AI providers

Add at least one to `.env`:

```env
AI_PROVIDERS=deepseek:sk-...,groq:gsk_...,openai:sk-...
```

Providers are tried in order — if one fails, the next is used automatically.

### 4. Run

```bash
docker compose down -v   # fresh start
docker compose up -d --build
# App available at http://localhost:8000
```

---

## 🔄 Every time you restart your PC (ngrok setup)

ngrok gives you a **new URL every time** you start it on the free plan. Follow these steps each time:

### Step 1 — Start Docker

```bash
cd /path/to/gitpulse
docker compose up -d
```

### Step 2 — Start ngrok

```bash
ngrok http 8000
```

Copy the new `https://xxxx.ngrok-free.app` URL from the output.

### Step 3 — Update .env

Open `.env` and update:

```env
APP_BASE_URL=https://xxxx.ngrok-free.app
```

### Step 4 — Restart the web container

```bash
docker compose restart web
```

### Step 5 — Update GitHub OAuth App

Go to **GitHub → Settings → Developer Settings → OAuth Apps → GitPulse → Edit**:

```
Homepage URL:              https://xxxx.ngrok-free.app
Authorization callback URL: https://xxxx.ngrok-free.app/auth/github/callback
```

Click **Update application**.

### Step 6 — Update GitHub Webhook

For each project that has a webhook set up:

1. Go to **GitHub → your repo → Settings → Webhooks**
2. Click **Edit** on the existing webhook
3. Update **Payload URL** to:
   ```
   https://xxxx.ngrok-free.app/webhook/github/<project_id>/<token>
   ```
   *(Find this URL on your GitPulse project page)*
4. Click **Update webhook**

> 💡 **Tip:** To avoid repeating steps 3–6 every time, consider deploying to Railway (free tier) — you get a permanent URL. See the deploy section below.

---

## Testing checklist

After every restart, verify these work:

| Test | How | Expected |
|---|---|---|
| Landing page | Open `https://xxxx.ngrok-free.app` | Page loads, no errors |
| GitHub login | Click "Start Free with GitHub" | Redirects to GitHub, then back to dashboard |
| Load repos | Click "Load My Repos" | Your GitHub repos appear |
| Connect repo | Click "Connect" on a repo | Redirected to project page |
| Manual generate | Enter a version, click "Generate" | AI changelog draft appears |
| Publish | Click "Publish" on a draft | Green success message, public URL shown |
| Public page | Open `https://xxxx.ngrok-free.app/username/repo` | Changelog visible without login |
| Webhook | `git push` to connected repo | Draft appears on project page automatically |
| Embed preview | Click "Preview iframe →" on project page | Changelog renders in minimal layout |

---

## Free production deploy (Railway + Supabase)

### Supabase (free PostgreSQL)

1. Create account at https://supabase.com → New project
2. Go to **Settings → Database** → copy the **URI**
3. Change `postgresql://` to `postgresql+asyncpg://`
4. Set as `DATABASE_URL` in Railway env vars

### Railway (free backend hosting)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Set all env vars from your `.env` in the Railway dashboard. Railway auto-detects the `Dockerfile`.

Your app gets a permanent URL like `https://gitpulse.up.railway.app` — no more ngrok needed.

---

## Project structure

```
gitpulse/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (reads .env)
│   ├── database.py          # Async SQLAlchemy
│   ├── models/user.py       # User, Project, Changelog models
│   ├── routers/
│   │   ├── auth.py          # GitHub OAuth
│   │   ├── dashboard.py     # Dashboard + repo picker
│   │   ├── changelog.py     # Generate / publish / public page
│   │   ├── webhook.py       # GitHub webhook receiver
│   │   ├── embed.py         # Embed script + iframe
│   │   └── pages.py         # Landing, pricing, how-it-works
│   ├── services/
│   │   ├── github.py        # GitHub API wrapper
│   │   ├── ai.py            # Multi-provider AI fallback chain
│   │   └── auth.py          # Session helpers
│   └── templates/           # Jinja2 HTML templates
├── alembic/                 # DB migrations
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## AI providers

| Provider | Format | Free? | Notes |
|---|---|---|---|
| DeepSeek | `deepseek:sk-...` | Cheap ($0.14/M tokens) | Recommended first |
| Groq | `groq:gsk_...` | Free tier | Fast, llama-3.3-70b |
| OpenAI | `openai:sk-...` | Paid | gpt-4o-mini |
| Anthropic | `anthropic:sk-ant-...` | Paid | claude-haiku |
| OpenRouter | `openrouter:sk-or-...` | Free models | mistral-7b free |

---

## Security checklist (before going live)

- [ ] `APP_SECRET_KEY` is a random 32+ char string, never committed to git
- [ ] `.env` is in `.gitignore` — never push real keys
- [ ] `APP_ENV=production` on Railway (disables `/api/docs`)
- [ ] GitHub OAuth App callback URL matches your production domain
- [ ] Rotate `APP_SECRET_KEY` invalidates all sessions
