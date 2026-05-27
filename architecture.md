# GitPulse — Architecture

## Overview

GitPulse is a single-process FastAPI application with a PostgreSQL database.
No microservices, no message queues, no Redis. Deliberately simple for a solo
developer operating at zero cost.

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│         HTMX + Jinja2 (no React, no build step)        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────────┐
│                  Render (Free Tier)                      │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │              FastAPI Application                  │  │
│   │                                                   │  │
│   │  /auth/*        GitHub OAuth flow                 │  │
│   │  /dashboard     Repo picker (HTMX)               │  │
│   │  /projects/*    Changelog generate/publish        │  │
│   │  /webhook/*     GitHub push events                │  │
│   │  /embed/*       JS widget + iframe                │  │
│   │  /polar/*       Payment webhooks                  │  │
│   │  /{user}/{repo} Public changelog page             │  │
│   └───────────┬──────────────────┬───────────────────┘  │
└───────────────┼──────────────────┼─────────────────────┘
                │                  │
    ┌───────────▼──────┐  ┌───────▼──────────┐
    │  Supabase        │  │  External APIs    │
    │  PostgreSQL      │  │                   │
    │                  │  │  GitHub API       │
    │  users           │  │  DeepSeek API     │
    │  projects        │  │  Groq API         │
    │  changelogs      │  │  OpenAI API       │
    └──────────────────┘  │  Anthropic API    │
                          │  Polar.sh API     │
                          └──────────────────┘
```

---

## Data Models

```
User
├── id (PK)
├── github_id (unique)
├── username
├── email
├── avatar_url
├── github_access_token   ← stored, used for API calls
├── plan                  ← free | starter | pro
├── changelogs_this_month ← reset monthly
└── timestamps

Project
├── id (PK)
├── owner_id (FK → User)
├── github_repo_full_name  ← "emrefkrlr/gitpulse"
├── slug                   ← URL-safe name
├── webhook_token          ← unique secret per project
└── created_at

Changelog
├── id (PK)
├── project_id (FK → Project)
├── version               ← "v1.2.0" or "auto-20260522-0718"
├── title
├── content_md            ← AI-generated Markdown
├── raw_commits           ← JSON array of commit SHAs
├── is_published          ← draft vs live
└── timestamps
```

---

## Request Flows

### 1. User Login (GitHub OAuth)

```
Browser → GET /auth/github
  → Redirect to github.com/login/oauth/authorize
  → User approves
  → GitHub → GET /auth/github/callback?code=xxx&state=yyy
  → Exchange code for access token (GitHub API)
  → Fetch user info (GitHub API)
  → Upsert user in DB
  → Set session cookie
  → Redirect to /dashboard
```

### 2. Manual Changelog Generation

```
Browser → POST /projects/{id}/generate (HTMX)
  → Check plan limit (changelogs_this_month < limit)
  → Fetch commits (GitHub API, last 50)
  → AI fallback chain:
      DeepSeek → if error → Groq → if error → OpenAI → if error → Anthropic
  → Save Changelog (is_published=False)
  → Increment changelogs_this_month
  → Return HTML preview partial (HTMX swap)
```

### 3. Webhook (Automatic on Push)

```
GitHub → POST /webhook/github/{project_id}/{token}
  → Verify event is "push"
  → Verify webhook token matches project
  → Load project owner's GitHub token
  → Fetch commits (GitHub API)
  → AI fallback chain (same as manual)
  → Save Changelog as draft
  → Return 200 OK
```

### 4. Payment Flow (Polar.sh)

```
Browser → GET /pricing/checkout/starter
  → Create Polar checkout session (Polar API)
  → Redirect to polar.sh/checkout/...
  → User pays
  → Polar → POST /polar/webhook
      → Verify signature (webhook secret)
      → Extract user_id from metadata
      → Update user.plan = "starter"
      → Return 200 OK
```

### 5. Embed Widget

```
External site has:
  <div id="gitpulse-changelog"></div>
  <script src="gitpulse.../embed/user/repo.js"></script>

Browser → GET /embed/{username}/{slug}.js
  → Query published changelogs
  → Return JavaScript that:
      1. Loads marked.js (markdown parser)
      2. Renders changelogs into #gitpulse-changelog div
      3. Caches for 60 seconds (Cache-Control header)
```

---

## AI Fallback Chain

```python
AI_PROVIDERS = "deepseek:sk-...,groq:gsk_...,openai:sk-..."

for provider, api_key in parse_providers():
    try:
        result = await call_provider(provider, api_key, prompt)
        return result          # success → stop
    except Exception as e:
        log.warning(e)
        continue               # fail → try next
        
raise RuntimeError("All providers failed")
```

Providers and their models:

| Provider | Model | Cost |
|---|---|---|
| DeepSeek | deepseek-chat | ~$0.14/M tokens |
| Groq | llama-3.3-70b-versatile | Free tier |
| OpenAI | gpt-4o-mini | ~$0.15/M tokens |
| Anthropic | claude-haiku-4-5 | ~$0.25/M tokens |
| OpenRouter | mistral-7b-instruct:free | Free |

---

## Session Management

- Cookie-based sessions via Starlette `SessionMiddleware`
- Signed with `APP_SECRET_KEY` (itsdangerous)
- 30-day expiry
- `https_only=False` — Render handles TLS termination at proxy level
- State validation for OAuth uses both session cookie AND in-memory dict
  for resilience against cookie loss during redirects

---

## Database Connection

Supabase uses PgBouncer in transaction pooling mode.
asyncpg requires `statement_cache_size=0` with connection poolers:

```python
connect_args = {"statement_cache_size": 0} if "supabase" in DATABASE_URL else {}
engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
```

---

## Plan Limits

```python
PLAN_LIMITS = {
    Plan.free:    3,       # changelogs per month
    Plan.starter: 20,
    Plan.pro:     999999,  # unlimited
}
```

Enforcement: checked before every generate (manual + webhook).
Reset: manual for now — APScheduler job planned.

---

## Deployment

```
GitHub (source) 
  → push to main 
  → Render auto-deploys (Dockerfile)
    → docker build
    → alembic upgrade head  (migrations)
    → uvicorn app.main:app
```

Environment: all secrets in Render environment variables, never in code.

---

## Known Limitations

1. **Render free tier sleeps** after 15 min inactivity — first request takes 30-60s
2. **Single process** — APScheduler monthly reset not yet implemented
3. **No background queue** — webhook processing is synchronous in request lifecycle
4. **In-memory OAuth state** — lost on restart, mitigated by session fallback
5. **No email notifications** — Resend integrated but not wired up yet
