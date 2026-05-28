from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models import MergedFeature


def get_latest_readings(db: Session) -> list[MergedFeature]:
    """Returns the most recent reading for every corridor."""
    subq = (
        db.query(
            MergedFeature.corridor_name,
            db.query(MergedFeature.timestamp)
            .filter(MergedFeature.corridor_name == MergedFeature.corridor_name)
            .order_by(MergedFeature.timestamp.desc())
            .limit(1)
            .scalar_subquery()
            .label("latest_ts"),
        )
    )
    # Simpler equivalent: get max timestamp per corridor then join back
    from sqlalchemy import func

    latest_ts_subq = (
        db.query(
            MergedFeature.corridor_name,
            func.max(MergedFeature.timestamp).label("latest_ts"),
        )
        .group_by(MergedFeature.corridor_name)
        .subquery()
    )

    return (
        db.query(MergedFeature)
        .join(
            latest_ts_subq,
            (MergedFeature.corridor_name == latest_ts_subq.c.corridor_name)
            & (MergedFeature.timestamp == latest_ts_subq.c.latest_ts),
        )
        .all()
    )


def get_corridor_history(
    db: Session,
    corridor_name: str,
    limit: int = 50,
) -> list[MergedFeature]:
    return (
        db.query(MergedFeature)
        .filter(MergedFeature.corridor_name == corridor_name)
        .order_by(MergedFeature.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_latest_for_corridor(
    db: Session, corridor_name: str
) -> Optional[MergedFeature]:
    return (
        db.query(MergedFeature)
        .filter(MergedFeature.corridor_name == corridor_name)
        .order_by(MergedFeature.timestamp.desc())
        .first()
    )
