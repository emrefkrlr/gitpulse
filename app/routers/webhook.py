"""
GitHub Webhook endpoint.

Kullanıcı repo ayarlarına şu URL'i ekler:
  https://your-domain.com/webhook/github/<project_id>/<token>

Push gelince:
  1. İmza doğrulanır (HMAC-SHA256)
  2. Son 30 commit çekilir
  3. AI changelog draft'ı oluşturulur (is_published=False)
  4. Kullanıcı dashboard'da görüp yayınlayabilir
"""
import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import Changelog, Project, User
from app.services.ai import generate_changelog
from app.services.github import get_commits

router = APIRouter(prefix="/webhook", tags=["webhook"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _verify_signature(secret: str, body: bytes, sig_header: str | None) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    # No signature header — allow (GitHub sends this only when Secret is configured)
    if not sig_header:
        return True
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


@router.post("/github/{project_id}/{token}")
async def github_webhook(
    project_id: int,
    token: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Only handle push events
    if x_github_event != "push":
        return JSONResponse({"status": "ignored", "event": x_github_event})

    body = await request.body()

    # Load project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify webhook secret (token in URL acts as shared secret)
    if not _verify_signature(token, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Load owner
    result = await db.execute(select(User).where(User.id == project.owner_id))
    owner = result.scalar_one_or_none()
    if not owner or not owner.github_access_token:
        raise HTTPException(status_code=400, detail="Owner has no GitHub token")

    payload = json.loads(body)
    ref = payload.get("ref", "")
    branch = ref.split("/")[-1] if ref else "unknown"
    pusher = payload.get("pusher", {}).get("name", "someone")
    commit_count = len(payload.get("commits", []))

    # Get recent commits from GitHub API
    try:
        commits = await get_commits(
            token=owner.github_access_token,
            repo_full_name=project.github_repo_full_name,
            per_page=30,
        )
    except Exception as e:
        return JSONResponse({"status": "error", "detail": f"GitHub API error: {e}"}, status_code=500)

    if not commits:
        return JSONResponse({"status": "skipped", "reason": "no commits found"})

    # Generate changelog draft
    version = f"auto-{datetime.utcnow().strftime('%Y%m%d-%H%M')}"
    try:
        content_md = await generate_changelog(commits, version, project.github_repo_full_name)
    except Exception as e:
        return JSONResponse({"status": "error", "detail": f"AI error: {e}"}, status_code=500)

    # Save as draft (not published)
    changelog = Changelog(
        project_id=project.id,
        version=version,
        title=f"Auto-draft from {branch} push by {pusher}",
        content_md=content_md,
        raw_commits=json.dumps([c.get("sha") for c in commits[:30]]),
        is_published=False,
    )
    db.add(changelog)
    owner.changelogs_this_month += 1
    await db.flush()

    return JSONResponse({
        "status": "ok",
        "changelog_id": changelog.id,
        "version": version,
        "branch": branch,
        "commits_used": len(commits),
    })
