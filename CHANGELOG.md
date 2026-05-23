# Changelog

## v1.2.3 — 2026-05-22
### Added
- **Generate progress UI** — clicking Generate now shows:
  - 3-step indicator: Fetching commits → AI writing → Ready
  - Animated progress bar that advances through realistic stages
  - Status text updates every ~1.8s ("Connecting to GitHub…",
    "Fetching recent commits…", "AI is writing your changelog…" etc.)
  - Button disables with "Generating…" label during request
  - All resets automatically when result arrives

## v1.2.2 — 2026-05-22
### Fixed
- All remaining Turkish strings translated to English
- README rewritten with ngrok restart guide + testing checklist
