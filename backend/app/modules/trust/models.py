"""Reports and moderation decisions — Phase 1A (TASK-015; 04 §64–§65, 04a §23).

    reports                       a user's signal about a target; never changes it
    moderation_decisions          immutable; one chain per target; the head is the
                                  target's current moderation state
    moderation_review_requests    the owner's reconsideration seam (Slice 5)

Every "exactly one" here is a database guarantee, not a check in code:

* one live report per (reporter, target) — partial UNIQUE;
* a decision is superseded at most once — UNIQUE(supersedes_decision_id);
* a target has at most one first decision — partial UNIQUE on
  (target_type, target_id) WHERE supersedes_decision_id IS NULL;
* a decision supersedes only a decision on the same target — composite
  foreign key (supersedes_decision_id, target_type, target_id).

Together: each target's decisions form a single line, so it has at most one
head (the decision nobody supersedes). Decisions are append-only: the ORM
refuses UPDATE/DELETE, a database trigger refuses them, and the application
role holds no UPDATE/DELETE/TRUNCATE on the table (app/core/sql/app_grants.sql;
verified at startup).

Privacy (Phase A §9): reporter identity and report text are moderator-only;
they never appear in a decision's event, audit data, metrics or logs.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 04 §64 — the canonical sets (stored values; the 1A UI offers subsets, §5.3).
REPORT_TARGET_TYPES = ("LISTING", "USER", "MESSAGE", "MEDIA", "PROPERTY")
REPORT_CATEGORIES = (
    "FAKE", "DUPLICATE", "SCAM", "DISCRIMINATION", "ILLEGAL_CONTENT", "STOLEN_MEDIA",
    "HARASSMENT", "SAFETY", "MISLEADING_PRICE", "IMPERSONATION", "SPAM", "OTHER",
)
SEVERITIES = ("NORMAL", "HIGH", "URGENT")
REPORT_STATUSES = ("OPEN", "TRIAGED", "IN_REVIEW", "RESOLVED", "CLOSED")
LIVE_REPORT_STATUSES = ("OPEN", "IN_REVIEW")

# 04 §65 actions; the targets decisions act on in Phase 1A (Phase A §6.2).
DECISION_TARGET_TYPES = ("LISTING", "MEDIA", "MESSAGE", "CONVERSATION")
DECISION_ACTIONS = (
    "NO_ACTION", "WARNING", "CONTENT_EDIT_REQUIRED", "VISIBILITY_LIMITED",
    "CONTENT_REMOVED", "FEATURE_RESTRICTED", "ACCOUNT_LIMITED", "ACCOUNT_SUSPENDED",
    "ACCOUNT_TERMINATED",
)
HOLD_ACTIONS = ("CONTENT_EDIT_REQUIRED", "VISIBILITY_LIMITED")
NOT_A_VIOLATION = "NOT_A_VIOLATION"
REINSTATED_REMEDIED = "REINSTATED_REMEDIED"
REINSTATED_DECISION_ERROR = "REINSTATED_DECISION_ERROR"
RELEASE_REASONS = (REINSTATED_REMEDIED, REINSTATED_DECISION_ERROR)
DECISION_REASON_CODES = (*REPORT_CATEGORIES, NOT_A_VIOLATION, *RELEASE_REASONS)

REVIEW_REQUEST_STATUSES = ("OPEN", "ANSWERED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _uuid() -> str:
    return str(uuid4())


class Report(Base):
    """A signal, never an action: creating or resolving a report changes
    nothing about its target (04 invariant 23)."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(_in("target_type", REPORT_TARGET_TYPES), name="ck_reports_target_type"),
        CheckConstraint(_in("category", REPORT_CATEGORIES), name="ck_reports_category"),
        CheckConstraint(_in("severity", SEVERITIES), name="ck_reports_severity"),
        CheckConstraint(_in("status", REPORT_STATUSES), name="ck_reports_status"),
        CheckConstraint("target_type <> 'MESSAGE' OR conversation_id IS NOT NULL",
                        name="ck_reports_message_has_conversation"),
        # One live report per reporter and target: a retry after an unknown
        # COMMIT finds the existing one instead of creating a second.
        Index("uq_reports_live_per_reporter_target", "reporter_user_id", "target_type",
              "target_id", unique=True,
              postgresql_where=text("status IN ('OPEN', 'IN_REVIEW')"),
              sqlite_where=text("status IN ('OPEN', 'IN_REVIEW')")),
        Index("ix_reports_queue", "status", "severity", "created_at"),
        Index("ix_reports_live_target", "target_type", "target_id",
              postgresql_where=text("status IN ('OPEN', 'IN_REVIEW')"),
              sqlite_where=text("status IN ('OPEN', 'IN_REVIEW')")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Nullable per canon (a future non-registered notice, L1); 1A requires it.
    reporter_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(24))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(8), default="NORMAL")
    status: Mapped[str] = mapped_column(String(12), default="OPEN")
    external_ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    listing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=True)
    # Public fields of the listing at report time (ids and public values only).
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    listing_public_generation_at_report: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    first_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_decision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("moderation_decisions.id", use_alter=True,
                   name="fk_reports_resolution_decision"),
        nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ModerationDecision(Base):
    """Immutable (04 §65): a later decision supersedes, it never edits."""

    __tablename__ = "moderation_decisions"
    __table_args__ = (
        CheckConstraint(_in("target_type", DECISION_TARGET_TYPES),
                        name="ck_moderation_decisions_target_type"),
        CheckConstraint(_in("action", DECISION_ACTIONS), name="ck_moderation_decisions_action"),
        CheckConstraint(_in("reason_code", DECISION_REASON_CODES),
                        name="ck_moderation_decisions_reason_code"),
        CheckConstraint(f"reclassified_category IS NULL OR "
                        f"{_in('reclassified_category', REPORT_CATEGORIES)}",
                        name="ck_moderation_decisions_reclassified_category"),
        CheckConstraint("supersedes_decision_id IS NULL OR supersedes_decision_id <> id",
                        name="ck_moderation_decisions_not_self"),
        # The chain: superseded at most once; one first decision per target;
        # only a decision on the same target can be superseded.
        UniqueConstraint("supersedes_decision_id", name="uq_moderation_decisions_supersedes"),
        UniqueConstraint("id", "target_type", "target_id",
                         name="uq_moderation_decisions_id_target"),
        ForeignKeyConstraint(
            ["supersedes_decision_id", "target_type", "target_id"],
            ["moderation_decisions.id", "moderation_decisions.target_type",
             "moderation_decisions.target_id"],
            name="fk_moderation_decisions_supersedes_same_target"),
        Index("uq_moderation_decisions_first_per_target", "target_type", "target_id",
              unique=True,
              postgresql_where=text("supersedes_decision_id IS NULL"),
              sqlite_where=text("supersedes_decision_id IS NULL")),
        Index("ix_moderation_decisions_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36))
    listing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(24))
    reason_code: Mapped[str] = mapped_column(String(32))
    # Moderator-internal; never in events, notices, audit data or logs.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    supersedes_decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reclassified_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    close_engagement: Mapped[bool] = mapped_column(Boolean, default=False)
    listing_public_generation_at_decision: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    appeal_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


def _immutable(mapper, connection, target):  # noqa: ARG001
    raise RuntimeError("moderation_decisions is append-only")


event.listen(ModerationDecision, "before_update", _immutable)
event.listen(ModerationDecision, "before_delete", _immutable)


class ModerationReviewRequest(Base):
    """The owner asks for a held listing to be reconsidered (Slice 5 API).
    One open request per decision; the answer is a new decision."""

    __tablename__ = "moderation_review_requests"
    __table_args__ = (
        CheckConstraint(_in("status", REVIEW_REQUEST_STATUSES),
                        name="ck_moderation_review_requests_status"),
        Index("uq_moderation_review_requests_open_per_decision", "decision_id", unique=True,
              postgresql_where=text("status = 'OPEN'"),
              sqlite_where=text("status = 'OPEN'")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("moderation_decisions.id"))
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")
    answered_by_decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("moderation_decisions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
