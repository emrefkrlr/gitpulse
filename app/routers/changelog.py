import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import Changelog, Plan, Project, User
from app.services.ai import generate_changelog
from app.services.auth import get_current_user
from app.services.github import get_commits

router = APIRouter(tags=["changelog"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

PLAN_LIMITS = {
    Plan.free: settings.free_changelog_limit,
    Plan.starter: settings.starter_changelog_limit,
    Plan.pro: 999999,
}


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    project = await _get_project(project_id, user.id, db)
    if not project:
        return RedirectResponse("/dashboard")
    result = await db.execute(
        select(Changelog).where(Changelog.project_id == project.id).order_by(Changelog.created_at.desc())
    )
    changelogs = result.scalars().all()
    limit = PLAN_LIMITS[user.plan]
    return templates.TemplateResponse(
        request, "project.html",
        {
            "user": user,
            "project": project,
            "changelogs": changelogs,
            "can_generate": user.changelogs_this_month < limit,
            "limit": limit,
            "base_url": settings.app_base_url,
        },
    )


@router.post("/projects/{project_id}/generate", response_class=HTMLResponse)
async def generate(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return HTMLResponse('<p class="text-red-500">Not authenticated</p>')
    project = await _get_project(project_id, user.id, db)
    if not project:
        return HTMLResponse('<p class="text-red-500">Project not found</p>')
    limit = PLAN_LIMITS[user.plan]
    if user.changelogs_this_month >= limit:
        return HTMLResponse(
            f'<div class="rounded-lg bg-amber-50 border border-amber-200 p-4">'
            f'<p class="font-medium text-amber-800">Monthly limit reached ({limit} changelogs).</p>'
            f'<a href="/pricing" class="text-amber-600 underline">Upgrade →</a></div>'
        )
    form = await request.form()
    version = str(form.get("version", "")).strip() or "latest"
    try:
        commits = await get_commits(token=user.github_access_token, repo_full_name=project.github_repo_full_name)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-500">GitHub error: {e}</p>')
    if not commits:
        return HTMLResponse('<p class="text-gray-500">No commits found.</p>')
    try:
        content_md = await generate_changelog(commits, version, project.github_repo_full_name)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-500">AI error: {e}</p>')
    changelog = Changelog(
        project_id=project.id, version=version,
        title=f"{project.slug} {version}", content_md=content_md,
        raw_commits=json.dumps([c.get("sha") for c in commits[:50]]), is_published=False,
    )
    db.add(changelog)
    user.changelogs_this_month += 1
    await db.flush()
    await db.refresh(changelog)
    return templates.TemplateResponse(
        request, "partials/changelog_preview.html",
        {"changelog": changelog, "project": project},
    )


@router.post("/projects/{project_id}/changelogs/{changelog_id}/publish", response_class=HTMLResponse)
async def publish(project_id: int, changelog_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return HTMLResponse("", headers={"HX-Redirect": "/"})
    result = await db.execute(
        select(Changelog).where(Changelog.id == changelog_id, Changelog.project_id == project_id)
    )
    changelog = result.scalar_one_or_none()
    if not changelog:
        return HTMLResponse('<p class="text-red-500">Changelog not found</p>')
    changelog.is_published = True
    changelog.published_at = datetime.utcnow()
    await db.flush()
    project = await _get_project(project_id, user.id, db)
    public_url = f"{settings.app_base_url}/{user.username}/{project.slug}"
    return templates.TemplateResponse(
        request, "partials/publish_success.html",
        {"changelog": changelog, "public_url": public_url, "project": project},
    )


@router.get("/{username}/{slug}", response_class=HTMLResponse)
async def public_changelog(username: str, slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == username))
    owner = result.scalar_one_or_none()
    if not owner:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    result = await db.execute(select(Project).where(Project.owner_id == owner.id, Project.slug == slug))
    project = result.scalar_one_or_none()
    if not project:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    result = await db.execute(
        select(Changelog)
        .where(Changelog.project_id == project.id, Changelog.is_published == True)
        .order_by(Changelog.published_at.desc())
    )
    changelogs = result.scalars().all()
    return templates.TemplateResponse(
        request, "public_changelog.html",
        {"owner": owner, "project": project, "changelogs": changelogs},
    )


async def _get_project(project_id: int, user_id: int, db: AsyncSession) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.owner_id == user_id))
    return result.scalar_one_or_none()
