import logging
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import normalize_email
from apps.api.db.models import AllowedActor, AppSession, Lead, Run, UsageRecord
from apps.api.services.notifications import send_access_granted_email

logger = logging.getLogger(__name__)


def _last_login_by_email(db: Session) -> dict[str, datetime]:
    rows = db.query(AppSession.email, func.max(AppSession.started_at)).group_by(AppSession.email).all()
    return {email: started_at for email, started_at in rows}


def org_usage_summary(db: Session) -> list[dict]:
    """Per-person aggregate spend and qualified-lead counts across every run
    they own -- the admin-only "how much has everyone spent, how many
    qualified leads do they have" view. Distinct from `list_allowed_actors`
    (which lists *grants*, i.e. who's allowed to sign in, not who actually
    has) -- this is grouped by `Run.supabase_user_id`, the real owner of
    real runs and real spend, and includes anyone who's ever run something
    even if their allowlist grant was later revoked (deliberately: cost
    oversight shouldn't disappear when access does)."""
    run_counts = db.query(Run.supabase_user_id, func.count(Run.id)).group_by(Run.supabase_user_id).all()
    if not run_counts:
        return []

    spend_by_user = {
        user_id: float(total)
        for user_id, total in (
            db.query(Run.supabase_user_id, func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0))
            .join(UsageRecord, UsageRecord.run_id == Run.id)
            .group_by(Run.supabase_user_id)
            .all()
        )
    }

    qualified_by_user = {
        user_id: count
        for user_id, count in (
            db.query(Run.supabase_user_id, func.count(Lead.id))
            .join(Lead, Lead.run_id == Run.id)
            .filter(Lead.qualification_status == "qualified")
            .group_by(Run.supabase_user_id)
            .all()
        )
    }

    # Most recent email per user_id -- app_sessions is keyed by
    # supabase_user_id directly (unlike AllowedActor, which has no such
    # column and has to be matched by email string instead).
    email_by_user: dict = {}
    for user_id, email in (
        db.query(AppSession.supabase_user_id, AppSession.email)
        .order_by(AppSession.started_at.desc())
        .all()
    ):
        email_by_user.setdefault(user_id, email)

    entries = [
        {
            "supabase_user_id": user_id,
            "email": email_by_user.get(user_id),
            "run_count": run_count,
            "qualified_lead_count": qualified_by_user.get(user_id, 0),
            "total_spend_usd": spend_by_user.get(user_id, 0.0),
        }
        for user_id, run_count in run_counts
    ]
    entries.sort(key=lambda e: e["total_spend_usd"], reverse=True)
    return entries


def list_allowed_actors(db: Session) -> list[tuple[AllowedActor, datetime | None]]:
    """Each entry paired with its last login, looked up from `app_sessions`
    (a fresh row per successful OTP verify, see auth_service.verify_otp_for_email
    -- there's no FK/denormalized column linking the two tables, so this is a
    read-time join by email rather than something written at login time).
    An email-scoped entry's last login is that exact email's most recent
    session; a domain-scoped entry's is the most recent session from ANY
    email ending in that domain, since a domain entry grants access to many
    actual logins, not one."""
    last_login = _last_login_by_email(db)
    actors = db.query(AllowedActor).order_by(AllowedActor.created_at.desc()).all()

    result: list[tuple[AllowedActor, datetime | None]] = []
    for actor in actors:
        if actor.email:
            result.append((actor, last_login.get(actor.email)))
        elif actor.email_domain:
            suffix = f"@{actor.email_domain}"
            matching = [ts for email, ts in last_login.items() if email.endswith(suffix)]
            result.append((actor, max(matching) if matching else None))
        else:
            result.append((actor, None))
    return result


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
