"""Prometheus metrics for the notification subsystem (OAT-03)."""

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.events.models import Notification

DELIVERED = Counter("homies_notifications_delivered_total", "Notifications delivered", ["channel"])
FAILED = Counter("homies_notifications_failed_total", "Delivery attempts failed", ["channel"])
DEAD = Counter("homies_notifications_dead_total", "Notifications moved to DEAD", ["channel"])
RETRIES = Counter("homies_notifications_retries_total", "Retry attempts", ["channel"])
LATENCY = Histogram("homies_notification_delivery_latency_seconds", "created->delivered latency")
QUEUE_DEPTH = Gauge("homies_notification_queue_depth", "Outbox depth by status", ["status"])


def refresh_queue_depth(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Notification.status, func.count()).group_by(Notification.status)
    ).all()
    counts = {status: int(n) for status, n in rows}
    for status in ("pending", "processing", "delivered", "failed", "dead"):
        QUEUE_DEPTH.labels(status=status).set(counts.get(status, 0))
    return counts
