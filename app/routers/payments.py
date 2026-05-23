"""
Polar.sh payment routes.

/pricing/checkout/starter  — redirect to Polar checkout for Starter plan
/pricing/checkout/pro      — redirect to Polar checkout for Pro plan
/polar/webhook             — receive Polar webhook events
/billing                   — customer billing portal
"""
import hashlib
import hmac
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import Plan, User
from app.services.auth import get_current_user

router = APIRouter(tags=["payments"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
log = logging.getLogger(__name__)


def _get_polar_client():
    from polar_sdk import Polar
    return Polar(
        access_token=settings.polar_access_token,
        server=settings.polar_server,
    )


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.get("/pricing/checkout/{plan}")
async def checkout(plan: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Create a Polar checkout session and redirect user to it."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/auth/github")

    product_id = {
        "starter": settings.polar_starter_product_id,
        "pro": settings.polar_pro_product_id,
    }.get(plan)

    if not product_id:
        raise HTTPException(status_code=404, detail="Plan not found")

    if not settings.polar_access_token:
        raise HTTPException(status_code=500, detail="Polar not configured")

    try:
        polar = _get_polar_client()
        result = polar.checkouts.create(request={
            "products": [{"product_id": product_id}],
            "success_url": f"{settings.app_base_url}/billing/success?plan={plan}",
            "customer_email": user.email or "",
            "metadata": {
                "user_id": str(user.id),
                "plan": plan,
            },
        })
        return RedirectResponse(result.url)
    except Exception as e:
        log.error("Polar checkout error: %s", e)
        raise HTTPException(status_code=500, detail=f"Checkout failed: {e}")


# ── Webhook ───────────────────────────────────────────────────────────────────

def _verify_polar_signature(secret: str, body: bytes, sig_header: str | None) -> bool:
    if not sig_header or not secret:
        return not secret  # if no secret configured, allow
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


@router.post("/polar/webhook")
async def polar_webhook(
    request: Request,
    webhook_id: str | None = Header(default=None, alias="webhook-id"),
    webhook_signature: str | None = Header(default=None, alias="webhook-signature"),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()

    # Verify signature using Polar SDK
    if settings.polar_webhook_secret:
        try:
            from polar_sdk.webhooks import WebhookVerificationError, validate_event
            event = validate_event(
                body,
                dict(request.headers),
                settings.polar_webhook_secret,
            )
        except Exception as e:
            log.warning("Polar webhook signature invalid: %s", e)
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        try:
            event = json.loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
    log.info("Polar webhook received: %s", event_type)

    # Handle subscription events
    if event_type in ("subscription.created", "subscription.active", "subscription.updated"):
        await _handle_subscription_activated(event, db)
    elif event_type in ("subscription.canceled", "subscription.revoked"):
        await _handle_subscription_canceled(event, db)

    return {"status": "ok"}


async def _get_subscription_data(event) -> dict:
    """Extract subscription data from event (handles both dict and object)."""
    if isinstance(event, dict):
        data = event.get("data", {})
    else:
        data = getattr(event, "data", {})
        if not isinstance(data, dict):
            data = data.__dict__ if hasattr(data, "__dict__") else {}
    return data


async def _handle_subscription_activated(event, db: AsyncSession):
    data = await _get_subscription_data(event)
    metadata = data.get("metadata", {}) or {}
    user_id = metadata.get("user_id")
    plan_name = metadata.get("plan", "starter")

    if not user_id:
        # Try to find user by email
        customer = data.get("customer", {}) or {}
        email = customer.get("email")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        else:
            log.warning("No user_id or email in subscription webhook")
            return
    else:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        log.warning("User not found for subscription webhook, user_id=%s", user_id)
        return

    new_plan = Plan.pro if plan_name == "pro" else Plan.starter
    user.plan = new_plan
    log.info("User %s upgraded to %s", user.username, new_plan)


async def _handle_subscription_canceled(event, db: AsyncSession):
    data = await _get_subscription_data(event)
    metadata = data.get("metadata", {}) or {}
    user_id = metadata.get("user_id")

    if not user_id:
        customer = data.get("customer", {}) or {}
        email = customer.get("email")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        else:
            return
    else:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        return

    user.plan = Plan.free
    log.info("User %s downgraded to free (subscription canceled)", user.username)


# ── Billing portal ────────────────────────────────────────────────────────────

@router.get("/billing/success", response_class=HTMLResponse)
async def billing_success(request: Request, plan: str = "starter", db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    return templates.TemplateResponse(
        request, "billing_success.html",
        {"user": user, "plan": plan},
    )


@router.get("/billing", response_class=HTMLResponse)
async def billing_portal(request: Request, db: AsyncSession = Depends(get_db)):
    """Redirect user to Polar customer portal."""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/auth/github")

    # Polar customer portal URL
    portal_url = (
        "https://sandbox.polar.sh/settings/orders"
        if settings.polar_server == "sandbox"
        else "https://polar.sh/settings/orders"
    )
    return RedirectResponse(portal_url)
