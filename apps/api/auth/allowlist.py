from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from apps.api.db.models import AllowedActor


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_email_allowed(db: Session, email: str) -> bool:
    normalized = normalize_email(email)
    domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else ""
    now = datetime.now(timezone.utc)

    match = (
        db.query(AllowedActor)
        .filter(
            or_(AllowedActor.email == normalized, AllowedActor.email_domain == domain),
            or_(AllowedActor.expires_at.is_(None), AllowedActor.expires_at > now),
        )
        .first()
    )
    return match is not None


def is_admin_email(db: Session, email: str) -> bool:
    normalized = normalize_email(email)
    now = datetime.now(timezone.utc)
    match = (
        db.query(AllowedActor)
        .filter(
            AllowedActor.email == normalized,
            AllowedActor.is_admin.is_(True),
            or_(AllowedActor.expires_at.is_(None), AllowedActor.expires_at > now),
        )
        .first()
    )
    return match is not None
