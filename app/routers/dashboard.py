from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import Project
from app.services.auth import get_current_user
from app.services.github import list_repos

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    result = await db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return templates.TemplateResponse(request, "dashboard.html", {"user": user, "projects": projects})


@router.get("/dashboard/repos", response_class=HTMLResponse)
async def list_github_repos(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return HTMLResponse('<p class="text-red-500">Not authenticated</p>')
    try:
        repos = await list_repos(user.github_access_token)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-500">GitHub error: {e}</p>')
    return templates.TemplateResponse(request, "partials/repo_list.html", {"repos": repos})


@router.post("/dashboard/projects", response_class=HTMLResponse)
async def create_project(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    form = await request.form()
    repo_full_name = str(form.get("repo_full_name", ""))
    if not repo_full_name or "/" not in repo_full_name:
        return HTMLResponse('<p class="text-red-500">Invalid repo selected.</p>')
    slug = repo_full_name.split("/")[-1].lower().replace("_", "-")
    existing = await db.execute(
        select(Project).where(Project.owner_id == user.id, Project.github_repo_full_name == repo_full_name)
    )
    if existing.scalar_one_or_none():
        return HTMLResponse('<p class="text-yellow-500">Project already connected.</p>')
    project = Project(owner_id=user.id, github_repo_full_name=repo_full_name, slug=slug)
    db.add(project)
    await db.flush()
    return HTMLResponse("", headers={"HX-Redirect": f"/projects/{project.id}"})
