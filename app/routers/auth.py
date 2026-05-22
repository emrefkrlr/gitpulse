import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.github import exchange_code_for_token, get_github_user

router = APIRouter(prefix="/auth", tags=["auth"])
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
SCOPES = "read:user user:email repo"

# In-memory state store (sufficient for single-process dev/prod with one worker)
_pending_states: dict[str, bool] = {}


@router.get("/github")
async def github_login(request: Request):
    state = secrets.token_urlsafe(16)
    # Store state both in session AND in-memory for resilience
    request.session["oauth_state"] = state
    _pending_states[state] = True

    params = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.app_base_url}/auth/github/callback",
        "scope": SCOPES,
        "state": state,
    })
    return RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{params}")


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    # Accept state if it matches session OR in-memory store
    session_state = request.session.pop("oauth_state", None)
    in_memory_valid = _pending_states.pop(state, False)

    if session_state != state and not in_memory_valid:
        return RedirectResponse("/?error=invalid_state")

    try:
        token = await exchange_code_for_token(
            code=code,
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
        )
        gh_user = await get_github_user(token)
    except Exception as e:
        print(f"GitHub auth error: {e}")
        return RedirectResponse("/?error=github_auth_failed")

    result = await db.execute(select(User).where(User.github_id == gh_user["id"]))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=gh_user["id"],
            username=gh_user["login"],
            email=gh_user.get("email"),
            avatar_url=gh_user.get("avatar_url"),
            github_access_token=token,
        )
        db.add(user)
    else:
        user.github_access_token = token
        user.avatar_url = gh_user.get("avatar_url")
        user.email = gh_user.get("email")

    await db.flush()
    await db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
