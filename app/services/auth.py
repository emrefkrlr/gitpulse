from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


def get_session_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


async def get_current_user(request: Request, db: AsyncSession) -> User | None:
    user_id = get_session_user_id(request)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
