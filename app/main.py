"""GitPulse — FastAPI application."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import engine
from app.models.user import Base  # noqa: F401
from app.routers import auth, changelog, dashboard, embed, pages, payments, webhook

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="GitPulse",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_dev else None,
    redoc_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="gitpulse_session",
    https_only=False,
    same_site="lax",
    max_age=60 * 60 * 24 * 30,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(webhook.router)
app.include_router(embed.router)
app.include_router(payments.router)
app.include_router(dashboard.router)
app.include_router(changelog.router)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(request, "404.html", {}, status_code=404)
