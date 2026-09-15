"""管理员权限检查"""
from nonebot.adapters import Event
from typing import Optional
from .settings import ADMIN_USER_IDS


def is_admin(user_id) -> bool:
    return str(user_id) in ADMIN_USER_IDS


def require_admin_text(user_id) -> Optional[str]:
    if not is_admin(user_id):
        return "无权限"
    return None


def get_event_user_id(event: Event) -> str:
    return event.get_user_id()
