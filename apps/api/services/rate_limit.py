import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.db.models import ObjectiveRejection


def record_rejection(db: Session, supabase_user_id: uuid.UUID) -> None:
    db.add(ObjectiveRejection(supabase_user_id=supabase_user_id))
    db.commit()


def is_rate_limited(db: Session, supabase_user_id: uuid.UUID) -> bool:
    """True if this user has hit `vague_objective_max_attempts` rejected
    objectives within the trailing `vague_objective_cooldown_minutes` window.
    The window rolls forward, so the effective pause is up to (but not
    always exactly) the configured cooldown after the most recent rejection."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.vague_objective_cooldown_minutes)
    count = (
        db.query(func.count(ObjectiveRejection.id))
        .filter(
            ObjectiveRejection.supabase_user_id == supabase_user_id,
            ObjectiveRejection.created_at >= cutoff,
        )
        .scalar()
    )
    return count >= settings.vague_objective_max_attempts
