# Changelog

## v1.3.0 — 2026-05-23
### Added
- **Polar.sh payment integration** — full subscription flow:
  - `/pricing/checkout/starter` and `/pricing/checkout/pro` create Polar
    checkout sessions and redirect user to hosted payment page
  - `/polar/webhook` receives subscription events and upgrades/downgrades
    user plan in DB automatically
  - `/billing/success` confirmation page after payment
  - `/billing` redirects to Polar customer portal (manage/cancel)
- **Pricing page updated** — buttons now show "Current plan" for active plan,
  "Upgrade" for others; logged-out users see sign-in prompt
- **polar-sdk==0.31.3** added to requirements
- Sandbox mode by default (`POLAR_ENV=sandbox`) — switch to `production`
  when going live

## v1.2.3 — 2026-05-22
### Added
- Generate progress bar with step indicators
