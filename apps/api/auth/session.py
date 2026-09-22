import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.db.models import AppSession


def start_session(db: Session, supabase_user_id: uuid.UUID, email: str) -> AppSession:
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=get_settings().app_session_ttl_minutes)
    session = AppSession(
        supabase_user_id=supabase_user_id,
        email=email,
        started_at=now,
        expires_at=now + ttl,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def is_session_active(db: Session, supabase_user_id: uuid.UUID) -> bool:
    now = datetime.now(timezone.utc)
    stmt = (
        select(AppSession)
        .where(AppSession.supabase_user_id == supabase_user_id)
        .where(AppSession.expires_at > now)
        .order_by(AppSession.expires_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None
