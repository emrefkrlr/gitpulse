"""
Embed widget endpoint.

Kullanıcı kendi sitesine şunu ekler:
  <script src="https://your-domain.com/embed/<username>/<slug>.js"></script>
  <div id="gitpulse-changelog"></div>

Script, changelog'u div içine render eder.
Ayrıca iframe embed de desteklenir.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_db
from app.models.user import Changelog, Project, User

router = APIRouter(tags=["embed"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/embed/{username}/{slug}.js")
async def embed_script(
    username: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns a JS snippet that renders the changelog into #gitpulse-changelog."""
    result = await db.execute(select(User).where(User.username == username))
    owner = result.scalar_one_or_none()
    if not owner:
        return Response("console.error('GitPulse: user not found');", media_type="application/javascript")

    result = await db.execute(
        select(Project).where(Project.owner_id == owner.id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        return Response("console.error('GitPulse: project not found');", media_type="application/javascript")

    result = await db.execute(
        select(Changelog)
        .where(Changelog.project_id == project.id, Changelog.is_published == True)
        .order_by(Changelog.published_at.desc())
        .limit(10)
    )
    changelogs = result.scalars().all()

    # Build JSON payload
    import json
    entries = [
        {
            "version": cl.version,
            "date": cl.published_at.strftime("%B %d, %Y") if cl.published_at else "",
            "content": cl.content_md,
        }
        for cl in changelogs
    ]

    base_url = settings.app_base_url
    entries_json = json.dumps(entries)

    js = f"""
(function() {{
  var data = {entries_json};
  var target = document.getElementById('gitpulse-changelog');
  if (!target) {{ console.warn('GitPulse: no element with id="gitpulse-changelog" found'); return; }}

  // Load marked.js for markdown rendering
  function loadScript(src, cb) {{
    var s = document.createElement('script'); s.src = src; s.onload = cb; document.head.appendChild(s);
  }}

  function render() {{
    var html = '<div style="font-family:Inter,system-ui,sans-serif;max-width:640px;">';
    html += '<div style="margin-bottom:16px;font-size:12px;color:#9ca3af;">Powered by <a href="{base_url}" target="_blank" style="color:#6366f1;text-decoration:none;">GitPulse</a></div>';
    data.forEach(function(entry) {{
      html += '<div style="margin-bottom:32px;padding-bottom:32px;border-bottom:1px solid #f3f4f6;">';
      html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">';
      html += '<span style="background:#111;color:#fff;font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;">' + entry.version + '</span>';
      html += '<span style="font-size:12px;color:#9ca3af;">' + entry.date + '</span>';
      html += '</div>';
      html += '<div class="gitpulse-md" style="font-size:14px;color:#374151;line-height:1.6;">' + (window.marked ? window.marked.parse(entry.content) : entry.content) + '</div>';
      html += '</div>';
    }});
    html += '</div>';
    target.innerHTML = html;
    // Style bullet lists
    target.querySelectorAll('ul').forEach(function(ul) {{
      ul.style.paddingLeft = '20px'; ul.style.listStyle = 'disc';
    }});
  }}

  if (window.marked) {{ render(); }}
  else {{ loadScript('https://cdn.jsdelivr.net/npm/marked/marked.min.js', render); }}
}})();
""".strip()

    return Response(js, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=60"})


@router.get("/embed/{username}/{slug}", response_class=HTMLResponse)
async def embed_iframe(
    username: str,
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Iframe-friendly full-page embed."""
    result = await db.execute(select(User).where(User.username == username))
    owner = result.scalar_one_or_none()
    if not owner:
        return HTMLResponse("<p>Not found</p>", status_code=404)

    result = await db.execute(
        select(Project).where(Project.owner_id == owner.id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        return HTMLResponse("<p>Not found</p>", status_code=404)

    result = await db.execute(
        select(Changelog)
        .where(Changelog.project_id == project.id, Changelog.is_published == True)
        .order_by(Changelog.published_at.desc())
        .limit(10)
    )
    changelogs = result.scalars().all()

    return templates.TemplateResponse(
        request, "embed.html",
        {"owner": owner, "project": project, "changelogs": changelogs},
    )
