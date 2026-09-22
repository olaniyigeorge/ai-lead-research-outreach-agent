import logging
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import normalize_email
from apps.api.db.models import AllowedActor
from apps.api.services.notifications import send_access_granted_email

logger = logging.getLogger(__name__)


def list_allowed_actors(db: Session) -> list[AllowedActor]:
    return db.query(AllowedActor).order_by(AllowedActor.created_at.desc()).all()


def create_allowed_actor(
    db: Session,
    email: str | None,
    email_domain: str | None,
    label: str | None,
    expires_at,
) -> AllowedActor:
    entry = AllowedActor(
        email=normalize_email(email) if email else None,
        email_domain=email_domain.strip().lower().lstrip("@") if email_domain else None,
        label=label,
        expires_at=expires_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Best-effort: the grant is already persisted regardless of whether the
    # notification email succeeds. Domain grants have no single recipient,
    # so only email-based grants get one.
    if entry.email:
        try:
            send_access_granted_email(entry.email, entry.label, entry.expires_at)
        except Exception:
            logger.exception("failed to send access-granted email to %s", entry.email)

    return entry


def delete_allowed_actor(db: Session, entry_id: uuid.UUID) -> None:
    entry = db.get(AllowedActor, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Allowlist entry not found")
    if entry.is_admin:
        raise HTTPException(status_code=400, detail="Cannot revoke an admin entry from this page")
    db.delete(entry)
    db.commit()
