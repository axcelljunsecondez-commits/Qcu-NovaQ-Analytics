"""Preview or remove expired authentication records safely."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import sessionmaker

from backend.db.models import AuthChallenge, SessionRecord
from backend.db.session import get_engine


def cleanup(*, apply: bool, retention_days: int) -> tuple[int, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    engine = get_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        session_filter = or_(
            SessionRecord.expires_at < cutoff,
            SessionRecord.revoked_at.is_not(None) & (SessionRecord.revoked_at < cutoff),
        )
        challenge_filter = or_(
            AuthChallenge.expires_at < cutoff,
            AuthChallenge.consumed_at.is_not(None) & (AuthChallenge.consumed_at < cutoff),
        )
        sessions = len(db.execute(select(SessionRecord.id).where(session_filter)).all())
        challenges = len(db.execute(select(AuthChallenge.id).where(challenge_filter)).all())
        if apply:
            db.execute(delete(SessionRecord).where(session_filter))
            db.execute(delete(AuthChallenge).where(challenge_filter))
            db.commit()
        else:
            db.rollback()
    return sessions, challenges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete matching records; default is preview")
    parser.add_argument("--retention-days", type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.retention_days <= 365:
        parser.error("--retention-days must be between 1 and 365")
    sessions, challenges = cleanup(apply=args.apply, retention_days=args.retention_days)
    mode = "deleted" if args.apply else "would delete"
    print(f"{mode}: sessions={sessions} challenges={challenges}")


if __name__ == "__main__":
    main()
