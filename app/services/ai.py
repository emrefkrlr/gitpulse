"""
AI service — multi-provider fallback chain.

Providers are tried in the order defined in AI_PROVIDERS (config).
Each entry is  "<provider>:<api_key>", e.g.:
  openai:sk-...
  anthropic:sk-ant-...
  groq:gsk_...
  openrouter:sk-or-...

On any error (auth, rate-limit, quota, network) the next provider is tried.
All errors are logged so you can see which keys are failing.
"""

import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical writer for a software product.
Transform raw Git commit messages into a clear, human-friendly changelog entry written in MARKETING language.

Rules:
- Group changes into: ✨ New Features, 🐛 Bug Fixes, ⚡ Improvements, 🔒 Security
- Omit categories with no relevant commits
- Skip trivial commits: "fix typo", "merge branch", "update deps" (unless significant)
- Write in second person: "You can now...", "We fixed..."
- Keep it concise: 5-15 bullet points total
- Return Markdown only, no preamble"""


# ── Provider drivers ─────────────────────────────────────────────────────────

async def _try_openai(api_key: str, user_prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1000,
        temperature=0.4,
    )
    return response.choices[0].message.content or ""


async def _try_anthropic(api_key: str, user_prompt: str) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text if message.content else ""


async def _try_groq(api_key: str, user_prompt: str) -> str:
    """Groq uses an OpenAI-compatible API."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1000,
        temperature=0.4,
    )
    return response.choices[0].message.content or ""


async def _try_openrouter(api_key: str, user_prompt: str) -> str:
    """OpenRouter uses an OpenAI-compatible API."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": settings.app_base_url},
    )
    response = await client.chat.completions.create(
        model="mistralai/mistral-7b-instruct:free",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1000,
        temperature=0.4,
    )
    return response.choices[0].message.content or ""


# Map provider name → driver function
DRIVERS = {
    "openai": _try_openai,
    "anthropic": _try_anthropic,
    "groq": _try_groq,
    "openrouter": _try_openrouter,
}


# ── Public API ────────────────────────────────────────────────────────────────

def _format_commits(commits: list[dict[str, Any]]) -> str:
    lines = []
    for c in commits:
        msg = c.get("commit", {}).get("message", "").split("\n")[0]
        sha = c.get("sha", "")[:7]
        lines.append(f"- [{sha}] {msg}")
    return "\n".join(lines)


def _parse_providers() -> list[tuple[str, str]]:
    """
    Parse AI_PROVIDERS env var into [(provider, api_key), ...].
    Format: comma-separated  "<provider>:<api_key>"
    Example: openai:sk-...,groq:gsk_...,anthropic:sk-ant-...
    """
    raw = settings.ai_providers.strip()
    if not raw:
        return []
    providers = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            log.warning("AI_PROVIDERS entry skipped (no colon): %s", entry[:20])
            continue
        provider, _, api_key = entry.partition(":")
        provider = provider.strip().lower()
        api_key = api_key.strip()
        if provider not in DRIVERS:
            log.warning("Unknown AI provider '%s', skipping.", provider)
            continue
        if not api_key:
            log.warning("Empty API key for provider '%s', skipping.", provider)
            continue
        providers.append((provider, api_key))
    return providers


async def generate_changelog(commits: list[dict[str, Any]], version: str, repo_name: str) -> str:
    """Try each configured provider in order; raise only if all fail."""
    commit_text = _format_commits(commits)
    user_prompt = (
        f"Repository: {repo_name}\nVersion: {version}\n\n"
        f"Commits:\n{commit_text}\n\nGenerate the changelog now."
    )

    providers = _parse_providers()
    if not providers:
        raise RuntimeError(
            "No AI providers configured. Add AI_PROVIDERS to your .env file.\n"
            "Example: AI_PROVIDERS=openai:sk-...,groq:gsk_..."
        )

    last_error: Exception | None = None
    for provider, api_key in providers:
        driver = DRIVERS[provider]
        try:
            log.info("Trying AI provider: %s", provider)
            result = await driver(api_key, user_prompt)
            log.info("AI provider succeeded: %s", provider)
            return result
        except Exception as e:
            log.warning("AI provider '%s' failed: %s", provider, str(e)[:120])
            last_error = e
            continue  # try next

    raise RuntimeError(
        f"All AI providers failed. Last error: {last_error}"
    )
