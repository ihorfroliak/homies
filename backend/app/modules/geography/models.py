"""Geographic reference data and structured addresses (TASK-010, decisions D-51…D-55).

Identity is always Homies' own (`id`, uuid4). Official identifiers from a
national source live in `geo_external_refs`, unique inside their source
namespace — so a TERYT code can be looked up, re-mapped or retired without
ever becoming a key other tables depend on.

Spatial columns (`boundary`, `centroid`) exist on PostgreSQL/PostGIS only and
are created by the migration, not declared here: the unit suite builds its
schema with create_all on SQLite (the same convention as `exact_geog`).

Invariants enforced in the database (migration e4f6a8b0c2d4):

* country codes are ISO 3166-1 alpha-2, upper case;
* an administrative area's parent is in the same country (composite FK);
* no area is its own parent; `level` is 1 at the top and parent.level + 1
  below — levels strictly increase along parent links, so a cycle is
  impossible, and a trigger keeps it so under concurrent writes;
* a locality, search area and address belong to the country of every area
  they reference (composite FKs);
* an external identifier is unique within its source, and an entity has at
  most one identifier per source.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


GEO_STATUSES = ("ACTIVE", "RETIRED")
# Generic settlement kinds. A country's own vocabulary (miasto, wieś, Stadt,
# Gemeindeteil …) is kept in `source_kind`, not here.
LOCALITY_KINDS = ("CITY", "TOWN", "VILLAGE", "SETTLEMENT", "OTHER")
# Search areas are not official units: a Warsaw district is administrative in
# one source and a search area in the product; a neighbourhood like Kazimierz
# is neither.
GEO_AREA_KINDS = ("DISTRICT", "NEIGHBOURHOOD", "SEARCH_AREA")
ADDRESS_RESOLUTIONS = ("UNSTRUCTURED", "STRUCTURED")
ADDRESS_SOURCES = ("USER_INPUT", "GEOCODER", "REFERENCE", "LEGACY_BACKFILL")
ADDRESS_VERIFICATION = ("UNVERIFIED", "VERIFIED")

# Country-specific type codes: two-letter country prefix, then a name.
KIND_CODE_PATTERN = "^[A-Z]{2}_[A-Z0-9_]{1,36}$"


class Country(Base):
    __tablename__ = "countries"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z]{2}$'", name="ck_countries_code").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint(
            "default_currency ~ '^[A-Z]{3}$'", name="ck_countries_currency"
        ).ddl_if(dialect="postgresql"),
    )

    # ISO 3166-1 alpha-2. A standard, stable, international identity — the one
    # place a code is the key, because it is not any country's own registry id.
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # English short name
    # ISO 4217. A default for new listings in that country, not a constraint:
    # a listing still states its own currency.
    default_currency: Mapped[str] = mapped_column(String(3))
    # Whether Homies operates there. Data for a country may exist before it does.
    is_active_market: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GeoSource(Base):
    """A namespace of external identifiers: one per identifier scheme
    (PL_TERYT_TERC, PL_TERYT_SIMC, PL_TERYT_ULIC, PL_PRG …)."""

    __tablename__ = "geo_sources"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z][A-Z0-9_]{1,39}$'", name="ck_geo_sources_code").ddl_if(
            dialect="postgresql"
        ),
    )

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    authority: Mapped[str] = mapped_column(String(200), default="")
    reference_url: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AdministrativeArea(Base):
    """An official unit at any depth: voivodeship, county, municipality;
    Land, Kreis, Gemeinde; comunidad, provincia, municipio."""

    __tablename__ = "admin_areas"
    __table_args__ = (
        UniqueConstraint("id", "country_code", name="uq_admin_areas_id_country"),
        ForeignKeyConstraint(
            ["parent_id", "country_code"], ["admin_areas.id", "admin_areas.country_code"],
            name="fk_admin_areas_parent_same_country", ondelete="RESTRICT",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_admin_areas_not_own_parent"),
        CheckConstraint("level >= 1", name="ck_admin_areas_level_positive"),
        CheckConstraint(
            "(parent_id IS NULL) = (level = 1)", name="ck_admin_areas_root_level"
        ),
        CheckConstraint(
            f"kind_code ~ '{KIND_CODE_PATTERN}'", name="ck_admin_areas_kind_code"
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(_in("status", GEO_STATUSES), name="ck_admin_areas_status"),
        Index("ix_admin_areas_country_level", "country_code", "level"),
        Index("ix_admin_areas_parent", "parent_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT")
    )
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 1 = highest unit below the country. Generic depth, not a named tier.
    level: Mapped[int] = mapped_column(Integer)
    # The country's own tier name, prefixed: PL_VOIVODESHIP, DE_LAND, ES_PROVINCIA.
    kind_code: Mapped[str] = mapped_column(String(40))
    # The name as the authoritative source writes it (Małopolskie, Kraków).
    official_name: Mapped[str] = mapped_column(String(200))
    # For future human-readable routes. Not identity, not unique.
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Locality(Base):
    """A settlement people name as where they live: a city, town or village.
    Not the same thing as a municipality — a rural municipality holds many
    villages, and a city may be split across several units."""

    __tablename__ = "localities"
    __table_args__ = (
        UniqueConstraint("id", "country_code", name="uq_localities_id_country"),
        ForeignKeyConstraint(
            ["admin_area_id", "country_code"], ["admin_areas.id", "admin_areas.country_code"],
            name="fk_localities_area_same_country", ondelete="RESTRICT",
        ),
        CheckConstraint(_in("kind", LOCALITY_KINDS), name="ck_localities_kind"),
        CheckConstraint(_in("status", GEO_STATUSES), name="ck_localities_status"),
        Index("ix_localities_country_name", "country_code", "official_name"),
        Index("ix_localities_admin_area", "admin_area_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT")
    )
    # The most specific official unit containing it (for Poland, the gmina).
    admin_area_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(12))
    # The source's own settlement type (e.g. TERYT RM code), informational.
    source_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    official_name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    admin_area = relationship("AdministrativeArea", foreign_keys=[admin_area_id],
                              primaryjoin="Locality.admin_area_id == AdministrativeArea.id",
                              viewonly=True, lazy="select")


class GeoArea(Base):
    """A search-relevant area that is not (necessarily) an official unit:
    Kazimierz, Zabłocie, Mokotów as people search for them. The seam for
    neighbourhood search; its boundary lives in PostGIS."""

    __tablename__ = "geo_areas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["locality_id", "country_code"], ["localities.id", "localities.country_code"],
            name="fk_geo_areas_locality_same_country", ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "country_code", name="uq_geo_areas_id_country"),
        CheckConstraint(_in("kind", GEO_AREA_KINDS), name="ck_geo_areas_kind"),
        CheckConstraint(_in("status", GEO_STATUSES), name="ck_geo_areas_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT")
    )
    locality_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GeoExternalRef(Base):
    """An authoritative identifier for one Homies geographic entity, inside
    its source's namespace."""

    __tablename__ = "geo_external_refs"
    __table_args__ = (
        UniqueConstraint("source_code", "external_id", name="uq_geo_external_refs_source_id"),
        CheckConstraint(
            "(admin_area_id IS NOT NULL)::int + (locality_id IS NOT NULL)::int"
            " + (geo_area_id IS NOT NULL)::int + (address_id IS NOT NULL)::int = 1",
            name="ck_geo_external_refs_one_target",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("length(external_id) BETWEEN 1 AND 64",
                        name="ck_geo_external_refs_id_length"),
        Index("uq_geo_external_refs_area", "source_code", "admin_area_id", unique=True,
              postgresql_where=text("admin_area_id IS NOT NULL"),
              sqlite_where=text("admin_area_id IS NOT NULL")),
        Index("uq_geo_external_refs_locality", "source_code", "locality_id", unique=True,
              postgresql_where=text("locality_id IS NOT NULL"),
              sqlite_where=text("locality_id IS NOT NULL")),
        Index("uq_geo_external_refs_geo_area", "source_code", "geo_area_id", unique=True,
              postgresql_where=text("geo_area_id IS NOT NULL"),
              sqlite_where=text("geo_area_id IS NOT NULL")),
        Index("uq_geo_external_refs_address", "source_code", "address_id", unique=True,
              postgresql_where=text("address_id IS NOT NULL"),
              sqlite_where=text("address_id IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_code: Mapped[str] = mapped_column(
        String(40), ForeignKey("geo_sources.code", ondelete="RESTRICT")
    )
    external_id: Mapped[str] = mapped_column(String(64))
    admin_area_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_areas.id", ondelete="CASCADE"), nullable=True
    )
    locality_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("localities.id", ondelete="CASCADE"), nullable=True
    )
    geo_area_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("geo_areas.id", ondelete="CASCADE"), nullable=True
    )
    # An address-point id (e.g. PRG) is PRIVATE: it pinpoints a building.
    address_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("addresses.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Address(Base):
    """A structured, source-aware address at building level (D-53).

    PRIVATE. Only the owner-facing and admin surfaces show it; a public
    listing shows the country, the official areas, the locality and an
    optional search area — never the street, building, unit, postal code or
    an identifier that pinpoints the building.

    Owned by exactly one Property today (`properties.address_id` is UNIQUE).
    It is building-level on purpose — the unit number lives on the Property —
    so one Building shared by many apartment Properties can be introduced
    later without moving these fields. The exact point stays on the Property
    (`properties.latitude/longitude`, `exact_geog`): one exact-location system,
    not two.
    """

    __tablename__ = "addresses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["locality_id", "country_code"], ["localities.id", "localities.country_code"],
            name="fk_addresses_locality_same_country", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["admin_area_id", "country_code"], ["admin_areas.id", "admin_areas.country_code"],
            name="fk_addresses_area_same_country", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["geo_area_id", "country_code"], ["geo_areas.id", "geo_areas.country_code"],
            name="fk_addresses_geo_area_same_country", ondelete="RESTRICT",
        ),
        # A locality already implies its administrative area; an area alone is
        # for addresses resolved no further than that.
        CheckConstraint("locality_id IS NULL OR admin_area_id IS NULL",
                        name="ck_addresses_one_place_level"),
        CheckConstraint(
            "resolution <> 'STRUCTURED' OR locality_id IS NOT NULL OR admin_area_id IS NOT NULL",
            name="ck_addresses_structured_has_place",
        ),
        CheckConstraint(_in("resolution", ADDRESS_RESOLUTIONS), name="ck_addresses_resolution"),
        CheckConstraint(_in("source", ADDRESS_SOURCES), name="ck_addresses_source"),
        CheckConstraint(_in("verification", ADDRESS_VERIFICATION),
                        name="ck_addresses_verification"),
        Index("ix_addresses_locality", "locality_id"),
        Index("ix_addresses_admin_area", "admin_area_id"),
        Index("ix_addresses_country", "country_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT")
    )
    locality_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    admin_area_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    geo_area_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(16), default="")
    # Street, square, avenue … Nullable: many villages number houses without
    # a street ("Zabierzów 123").
    thoroughfare: Mapped[str | None] = mapped_column(String(200), nullable=True)
    building_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # What the person typed, kept as entered; for unstructured addresses it
    # is the only precise description.
    unstructured_text: Mapped[str] = mapped_column(String(255), default="")
    # Place names as typed when no reference entity is linked yet.
    locality_text: Mapped[str] = mapped_column(String(120), default="")
    district_text: Mapped[str] = mapped_column(String(120), default="")
    resolution: Mapped[str] = mapped_column(String(12), default="UNSTRUCTURED")
    source: Mapped[str] = mapped_column(String(16), default="USER_INPUT")
    verification: Mapped[str] = mapped_column(String(12), default="UNVERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    locality = relationship("Locality", foreign_keys=[locality_id],
                            primaryjoin="Address.locality_id == Locality.id",
                            viewonly=True, lazy="select")
    admin_area = relationship("AdministrativeArea", foreign_keys=[admin_area_id],
                              primaryjoin="Address.admin_area_id == AdministrativeArea.id",
                              viewonly=True, lazy="select")
    geo_area = relationship("GeoArea", foreign_keys=[geo_area_id],
                            primaryjoin="Address.geo_area_id == GeoArea.id",
                            viewonly=True, lazy="select")
