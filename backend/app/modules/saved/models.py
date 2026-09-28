"""Saved Listings and Saved Searches (TASK-014).

A SavedListing targets the Listing the renter actually saw — the offer, not
the physical Property (04a §22 supersedes Schema v1 §51 for Phase 1A).
Following a Property across its future listings is a different, later concept.

A SavedSearch stores exactly one representation of the search: the TASK-013
canonical query (`SearchQuery.canonical()`), with its schema version and a
fingerprint of both. There is no second search language.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SavedListing(Base):
    __tablename__ = "saved_listings"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_saved_listings_user_listing"),
        Index("ix_saved_listings_user_saved_at", "user_id", "saved_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), index=True
    )
    # The database instant of the save (freshness.db_now), never the client's.
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


SEARCH_STATUSES = ("active", "paused")


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    __table_args__ = (
        # The per-user duplicate rule: the same canonical query (same schema
        # version) can be saved once per account.
        UniqueConstraint("user_id", "query_fingerprint", name="uq_saved_searches_user_fingerprint"),
        CheckConstraint("status IN ('active', 'paused')", name="ck_saved_searches_status"),
        CheckConstraint("query_schema_version >= 1", name="ck_saved_searches_schema_version"),
        CheckConstraint("length(name) BETWEEN 1 AND 80", name="ck_saved_searches_name_length"),
        CheckConstraint("length(query_fingerprint) = 64",
                        name="ck_saved_searches_fingerprint_length"),
        Index("ix_saved_searches_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(80))
    # The market the search is about (Schema v1 §52): the query's country, or
    # the country of the places it names; NULL when it names none.
    market_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    canonical_query: Mapped[str] = mapped_column(Text)
    query_schema_version: Mapped[int] = mapped_column(Integer)
    # SHA-256(version, canonical query): identity for the duplicate rule. Not a
    # secret and never an authentication factor.
    query_fingerprint: Mapped[str] = mapped_column(String(64))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(8), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # The watermark: only listings that became public AFTER this database
    # instant can alert. What already matched when the search was saved (or
    # its query last changed) is shown, never notified.
    baseline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(BigInteger, default=1)

    anchors = relationship("SavedSearchAnchor", cascade="all, delete-orphan",
                           passive_deletes=True, lazy="selectin")


class SavedSearchAnchor(Base):
    """A coarse, indexed necessary condition of a saved search, used only to
    NARROW the candidates when a listing becomes public (TASK-014): the search
    can match a listing only if one of its anchors is among the listing's
    keys. The canonical query stays the only judge of an actual match.

    kinds: L locality · G search area · A administrative area (a listing's
    keys include every ancestor) · C country · * no place constraint.
    """

    __tablename__ = "saved_search_anchors"
    __table_args__ = (
        CheckConstraint("kind IN ('L', 'G', 'A', 'C', '*')", name="ck_saved_search_anchors_kind"),
        Index("ix_saved_search_anchors_key", "kind", "value"),
    )

    saved_search_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(1), primary_key=True)
    value: Mapped[str] = mapped_column(String(36), primary_key=True)
