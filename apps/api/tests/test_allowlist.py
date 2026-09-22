from datetime import datetime, timedelta, timezone

from apps.api.auth.allowlist import is_admin_email, is_email_allowed
from apps.api.db.models import AllowedActor


def test_exact_email_match_is_allowed(db_session):
    db_session.add(AllowedActor(email="exact-match@example.com", label="test"))
    db_session.commit()

    assert is_email_allowed(db_session, "Exact-Match@example.com ") is True


def test_domain_match_is_allowed(db_session):
    db_session.add(AllowedActor(email_domain="koyatalent.com", label="test"))
    db_session.commit()

    assert is_email_allowed(db_session, "someone@koyatalent.com") is True


def test_unlisted_email_is_rejected(db_session):
    assert is_email_allowed(db_session, "nobody@nowhere.example") is False


def test_expired_entry_no_longer_allows(db_session):
    db_session.add(
        AllowedActor(
            email="expired@example.com",
            label="temp invite",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    assert is_email_allowed(db_session, "expired@example.com") is False


def test_future_expiry_still_allows(db_session):
    db_session.add(
        AllowedActor(
            email="not-yet-expired@example.com",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db_session.commit()

    assert is_email_allowed(db_session, "not-yet-expired@example.com") is True


def test_is_admin_email_true_only_for_admin_flagged_entries(db_session):
    db_session.add(AllowedActor(email="admin@example.com", is_admin=True))
    db_session.add(AllowedActor(email="regular@example.com", is_admin=False))
    db_session.commit()

    assert is_admin_email(db_session, "admin@example.com") is True
    assert is_admin_email(db_session, "regular@example.com") is False
    assert is_admin_email(db_session, "nobody@nowhere.example") is False


def test_is_admin_email_respects_expiry(db_session):
    db_session.add(
        AllowedActor(
            email="expired-admin@example.com",
            is_admin=True,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    assert is_admin_email(db_session, "expired-admin@example.com") is False
