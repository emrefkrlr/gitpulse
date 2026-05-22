# Changelog

## v1.1.0 — 2026-05-22
### Added
- **GitHub Webhook otomasyonu** — Her push'ta otomatik changelog draft oluşturulur.
  Proje sayfasında webhook URL'i gösterilir, kullanıcı bunu GitHub repo ayarlarına
  ekler. HMAC-SHA256 ile imza doğrulaması yapılır, güvenli.
- **Embed widget** — `<script>` tag'i ile herhangi bir siteye changelog embed edilir.
  JSON olarak servis edilir, marked.js ile client-side render. Ayrıca iframe embed
  için `/embed/<user>/<slug>` endpoint'i eklendi.
- **Project modeline `webhook_token`** — Her proje oluşturulduğunda otomatik
  unique token atanır, webhook URL güvenliği için kullanılır.
- **Draft badge** — Webhook ile gelen otomatik draft'lar "auto" etiketi ile
  proje sayfasında listelenir, kullanıcı inceleyip yayınlayabilir.

## v1.0.5 — 2026-05-21
### Added
- Multi-provider AI fallback zinciri (AI_PROVIDERS)
- Groq model güncellendi: llama3-8b-8192 → llama-3.3-70b-versatile

## v1.0.4 — 2026-05-21
### Fixed
- GitHub OAuth invalid_state hatası

## v1.0.3 — 2026-05-18
### Fixed
- Starlette 1.0 TemplateResponse breaking change
