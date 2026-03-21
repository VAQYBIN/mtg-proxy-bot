from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user
from bot.models.user import User

router = APIRouter(prefix="/api", tags=["user"])


class UserResponse(BaseModel):
    id: int
    telegram_id: int | None
    username: str | None
    first_name: str | None
    display_name: str | None
    email: str | None
    email_verified: bool
    is_banned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
