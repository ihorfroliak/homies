"""Geography, structured addresses and canonical property classification (TASK-010).

Revision ID: e4f6a8b0c2d4
Revises: d3f5b7a9c1e4
Create Date: 2026-09-25

Additive and backfilled. Nothing existing is dropped or rewritten:

* new tables: countries, geo_sources, admin_areas (any depth, with a
  hierarchy trigger), localities, geo_areas, addresses, geo_external_refs;
  PostGIS `boundary`/`centroid` columns with GiST indexes, empty for now;
* properties gain `category`, `subtype`, `unit_number` and `address_id`.

Backfill:

* **country** — every existing property is Polish. Poland is the only market
  Homies has operated in, and every property row was created through an API
  that required a Polish gmina. That is a fact about the existing rows, not an
  assumption the model makes: `country_code` is a column like any other.
* **address** — one UNSTRUCTURED address per property, carrying the legacy
  free text as typed (`address`, `city`, `district`, `postcode`), source
  LEGACY_BACKFILL. No locality is guessed from text: resolving it against
  reference data is a later, reviewable step.
* **classification** — legacy `property_type` maps to category/subtype as in
  app/modules/properties/classification.py; a legacy "room" (or NULL) row
  gets no category rather than an invented one. `property_type` is kept.

Operational note: the backfill touches every property row once and adds a
UNIQUE index and FK on `properties.address_id` — plan with
docs/database/MIGRATION-ROLLOUT.md.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "e4f6a8b0c2d4"
down_revision = "d3f5b7a9c1e4"
branch_labels = None
depends_on = None


def _seed_countries() -> list[dict]:
    # Only the current market. Other countries are rows, added when needed.
    return [{"code": "PL", "name": "Poland", "default_currency": "PLN",
             "is_active_market": True}]


def _seed_sources() -> list[dict]:
    # Identifier namespaces for Polish official registers. Seeding a
    # namespace imports no data; it lets data be imported and looked up.
    stat = "Główny Urząd Statystyczny (GUS)"
    gugik = "Główny Urząd Geodezji i Kartografii (GUGiK)"
    return [
        {"code": "PL_TERYT_TERC", "country_code": "PL", "authority": stat,
         "name": "TERYT TERC — territorial division identifiers",
         "reference_url": "https://eteryt.stat.gov.pl"},
        {"code": "PL_TERYT_SIMC", "country_code": "PL", "authority": stat,
         "name": "TERYT SIMC — locality identifiers",
         "reference_url": "https://eteryt.stat.gov.pl"},
        {"code": "PL_TERYT_ULIC", "country_code": "PL", "authority": stat,
         "name": "TERYT ULIC — street identifiers",
         "reference_url": "https://eteryt.stat.gov.pl"},
        {"code": "PL_PRG", "country_code": "PL", "authority": gugik,
         "name": "PRG — national register of boundaries (areas)", "reference_url": ""},
        {"code": "PL_PRG_ADDRESS", "country_code": "PL", "authority": gugik,
         "name": "PRG — address points", "reference_url": ""},
    ]


# Mirrors classification.LEGACY_MAP; a migration keeps its own copy so it
# means what it meant when written.
_LEGACY = {
    "apartment": ("APARTMENT", None),
    "studio": ("APARTMENT", "STUDIO"),
    "loft": ("APARTMENT", "LOFT"),
    "aparthotel_unit": ("APARTMENT", "APARTHOTEL_UNIT"),
    "house": ("HOUSE", None),
    "townhouse": ("HOUSE", "TERRACED_HOUSE"),
}
_SUBTYPES = {
    "APARTMENT": ("STUDIO", "LOFT", "APARTHOTEL_UNIT"),
    "HOUSE": ("DETACHED_HOUSE", "SEMI_DETACHED_HOUSE", "TERRACED_HOUSE"),
}


def _subtype_check() -> str:
    parts = [f"(category = '{c}' AND subtype IN ({', '.join(repr(s) for s in subs)}))"
             for c, subs in _SUBTYPES.items()]
    return "subtype IS NULL OR " + " OR ".join(parts)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False),
        sa.Column("is_active_market", sa.Boolean, nullable=False, server_default=sa.false()),
        _ts("created_at"),
        sa.CheckConstraint("code ~ '^[A-Z]{2}$'", name="ck_countries_code"),
        sa.CheckConstraint("default_currency ~ '^[A-Z]{3}$'", name="ck_countries_currency"),
    )
    op.create_table(
        "geo_sources",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("country_code", sa.String(2),
                  sa.ForeignKey("countries.code", ondelete="RESTRICT"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("authority", sa.String(200), nullable=False, server_default=""),
        sa.Column("reference_url", sa.String(300), nullable=False, server_default=""),
        _ts("created_at"),
        sa.CheckConstraint("code ~ '^[A-Z][A-Z0-9_]{1,39}$'", name="ck_geo_sources_code"),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(sa.table("countries", sa.column("code"), sa.column("name"),
                            sa.column("default_currency"), sa.column("is_active_market"),
                            sa.column("created_at")),
                   [{**c, "created_at": now} for c in _seed_countries()])
    op.bulk_insert(sa.table("geo_sources", sa.column("code"), sa.column("country_code"),
                            sa.column("name"), sa.column("authority"),
                            sa.column("reference_url"), sa.column("created_at")),
                   [{**s, "created_at": now} for s in _seed_sources()])

    op.create_table(
        "admin_areas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("country_code", sa.String(2),
                  sa.ForeignKey("countries.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("kind_code", sa.String(40), nullable=False),
        sa.Column("official_name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="ACTIVE"),
        _ts("retired_at", nullable=True), _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("id", "country_code", name="uq_admin_areas_id_country"),
        sa.ForeignKeyConstraint(["parent_id", "country_code"],
                                ["admin_areas.id", "admin_areas.country_code"],
                                name="fk_admin_areas_parent_same_country", ondelete="RESTRICT"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id",
                           name="ck_admin_areas_not_own_parent"),
        sa.CheckConstraint("level >= 1", name="ck_admin_areas_level_positive"),
        sa.CheckConstraint("(parent_id IS NULL) = (level = 1)", name="ck_admin_areas_root_level"),
        sa.CheckConstraint("kind_code ~ '^[A-Z]{2}_[A-Z0-9_]{1,36}$'",
                           name="ck_admin_areas_kind_code"),
        sa.CheckConstraint(_in("status", ("ACTIVE", "RETIRED")), name="ck_admin_areas_status"),
    )
    op.create_index("ix_admin_areas_country_level", "admin_areas", ["country_code", "level"])
    op.create_index("ix_admin_areas_parent", "admin_areas", ["parent_id"])
    op.execute("ALTER TABLE admin_areas ADD COLUMN boundary geography(MultiPolygon, 4326)")
    op.execute("CREATE INDEX ix_admin_areas_boundary ON admin_areas USING gist (boundary)")
    # Levels strictly increase along parent links, so a cycle cannot exist.
    # The parent row is read FOR SHARE: a concurrent change to the parent's
    # level or parent waits, and two transactions cannot each re-parent the
    # other's ancestor into a loop.
    op.execute("""
        CREATE FUNCTION admin_areas_hierarchy() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_level integer;
        BEGIN
            IF NEW.parent_id IS NOT NULL THEN
                SELECT level INTO parent_level FROM admin_areas
                 WHERE id = NEW.parent_id FOR SHARE;
                IF parent_level IS NULL OR NEW.level <> parent_level + 1 THEN
                    RAISE EXCEPTION 'administrative area level % does not follow its parent',
                        NEW.level USING ERRCODE = '23514', CONSTRAINT = 'ck_admin_areas_hierarchy';
                END IF;
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.level <> OLD.level
               AND EXISTS (SELECT 1 FROM admin_areas WHERE parent_id = NEW.id) THEN
                RAISE EXCEPTION 'cannot change the level of an area that has children'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_admin_areas_hierarchy';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER admin_areas_hierarchy
        BEFORE INSERT OR UPDATE OF parent_id, level ON admin_areas
        FOR EACH ROW EXECUTE FUNCTION admin_areas_hierarchy()
    """)

    op.create_table(
        "localities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("country_code", sa.String(2),
                  sa.ForeignKey("countries.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("admin_area_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=True),
        sa.Column("official_name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="ACTIVE"),
        _ts("retired_at", nullable=True), _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("id", "country_code", name="uq_localities_id_country"),
        sa.ForeignKeyConstraint(["admin_area_id", "country_code"],
                                ["admin_areas.id", "admin_areas.country_code"],
                                name="fk_localities_area_same_country", ondelete="RESTRICT"),
        sa.CheckConstraint(_in("kind", ("CITY", "TOWN", "VILLAGE", "SETTLEMENT", "OTHER")),
                           name="ck_localities_kind"),
        sa.CheckConstraint(_in("status", ("ACTIVE", "RETIRED")), name="ck_localities_status"),
    )
    op.create_index("ix_localities_country_name", "localities", ["country_code", "official_name"])
    op.create_index("ix_localities_admin_area", "localities", ["admin_area_id"])
    op.execute("ALTER TABLE localities ADD COLUMN centroid geography(Point, 4326)")
    op.execute("CREATE INDEX ix_localities_centroid ON localities USING gist (centroid)")

    op.create_table(
        "geo_areas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("country_code", sa.String(2),
                  sa.ForeignKey("countries.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("locality_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="ACTIVE"),
        _ts("created_at"),
        sa.UniqueConstraint("id", "country_code", name="uq_geo_areas_id_country"),
        sa.ForeignKeyConstraint(["locality_id", "country_code"],
                                ["localities.id", "localities.country_code"],
                                name="fk_geo_areas_locality_same_country", ondelete="RESTRICT"),
        sa.CheckConstraint(_in("kind", ("DISTRICT", "NEIGHBOURHOOD", "SEARCH_AREA")),
                           name="ck_geo_areas_kind"),
        sa.CheckConstraint(_in("status", ("ACTIVE", "RETIRED")), name="ck_geo_areas_status"),
    )
    op.execute("ALTER TABLE geo_areas ADD COLUMN boundary geography(MultiPolygon, 4326)")
    op.execute("CREATE INDEX ix_geo_areas_boundary ON geo_areas USING gist (boundary)")

    op.create_table(
        "addresses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("country_code", sa.String(2),
                  sa.ForeignKey("countries.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("locality_id", sa.String(36), nullable=True),
        sa.Column("admin_area_id", sa.String(36), nullable=True),
        sa.Column("geo_area_id", sa.String(36), nullable=True),
        sa.Column("postal_code", sa.String(16), nullable=False, server_default=""),
        sa.Column("thoroughfare", sa.String(200), nullable=True),
        sa.Column("building_number", sa.String(20), nullable=True),
        sa.Column("unstructured_text", sa.String(255), nullable=False, server_default=""),
        sa.Column("locality_text", sa.String(120), nullable=False, server_default=""),
        sa.Column("district_text", sa.String(120), nullable=False, server_default=""),
        sa.Column("resolution", sa.String(12), nullable=False, server_default="UNSTRUCTURED"),
        sa.Column("source", sa.String(16), nullable=False, server_default="USER_INPUT"),
        sa.Column("verification", sa.String(12), nullable=False, server_default="UNVERIFIED"),
        _ts("created_at"), _ts("updated_at"),
        sa.ForeignKeyConstraint(["locality_id", "country_code"],
                                ["localities.id", "localities.country_code"],
                                name="fk_addresses_locality_same_country", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["admin_area_id", "country_code"],
                                ["admin_areas.id", "admin_areas.country_code"],
                                name="fk_addresses_area_same_country", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["geo_area_id", "country_code"],
                                ["geo_areas.id", "geo_areas.country_code"],
                                name="fk_addresses_geo_area_same_country", ondelete="RESTRICT"),
        sa.CheckConstraint("locality_id IS NULL OR admin_area_id IS NULL",
                           name="ck_addresses_one_place_level"),
        sa.CheckConstraint(
            "resolution <> 'STRUCTURED' OR locality_id IS NOT NULL OR admin_area_id IS NOT NULL",
            name="ck_addresses_structured_has_place"),
        sa.CheckConstraint(_in("resolution", ("UNSTRUCTURED", "STRUCTURED")),
                           name="ck_addresses_resolution"),
        sa.CheckConstraint(_in("source", ("USER_INPUT", "GEOCODER", "REFERENCE",
                                          "LEGACY_BACKFILL")), name="ck_addresses_source"),
        sa.CheckConstraint(_in("verification", ("UNVERIFIED", "VERIFIED")),
                           name="ck_addresses_verification"),
    )
    op.create_index("ix_addresses_locality", "addresses", ["locality_id"])
    op.create_index("ix_addresses_admin_area", "addresses", ["admin_area_id"])
    op.create_index("ix_addresses_country", "addresses", ["country_code"])

    op.create_table(
        "geo_external_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_code", sa.String(40),
                  sa.ForeignKey("geo_sources.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("admin_area_id", sa.String(36),
                  sa.ForeignKey("admin_areas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("locality_id", sa.String(36),
                  sa.ForeignKey("localities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("geo_area_id", sa.String(36),
                  sa.ForeignKey("geo_areas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("address_id", sa.String(36),
                  sa.ForeignKey("addresses.id", ondelete="CASCADE"), nullable=True),
        _ts("created_at"),
        sa.UniqueConstraint("source_code", "external_id", name="uq_geo_external_refs_source_id"),
        sa.CheckConstraint(
            "(admin_area_id IS NOT NULL)::int + (locality_id IS NOT NULL)::int"
            " + (geo_area_id IS NOT NULL)::int + (address_id IS NOT NULL)::int = 1",
            name="ck_geo_external_refs_one_target"),
        sa.CheckConstraint("length(external_id) BETWEEN 1 AND 64",
                           name="ck_geo_external_refs_id_length"),
    )
    for target in ("admin_area", "locality", "geo_area", "address"):
        op.create_index(f"uq_geo_external_refs_{target}", "geo_external_refs",
                        ["source_code", f"{target}_id"], unique=True,
                        postgresql_where=sa.text(f"{target}_id IS NOT NULL"))

    # --- properties -----------------------------------------------------------
    op.add_column("properties", sa.Column("category", sa.String(16), nullable=True))
    op.add_column("properties", sa.Column("subtype", sa.String(32), nullable=True))
    op.add_column("properties", sa.Column("unit_number", sa.String(32), nullable=True))
    op.add_column("properties", sa.Column("address_id", sa.String(36), nullable=True))

    bind = op.get_bind()
    for legacy, (category, subtype) in _LEGACY.items():
        bind.execute(sa.text(
            "UPDATE properties SET category = :c, subtype = :s WHERE property_type = :t"),
            {"c": category, "s": subtype, "t": legacy})

    bind.execute(sa.text("""
        WITH src AS MATERIALIZED (
            SELECT id AS property_id, gen_random_uuid()::text AS address_id,
                   coalesce(postcode, '') AS postcode, coalesce(address, '') AS address,
                   coalesce(city, '') AS city, coalesce(district, '') AS district,
                   created_at
              FROM properties
        ), inserted AS (
            INSERT INTO addresses (id, country_code, postal_code, unstructured_text,
                                   locality_text, district_text, resolution, source,
                                   verification, created_at, updated_at)
            SELECT address_id, 'PL', left(postcode, 16), left(address, 255), left(city, 120),
                   left(district, 120), 'UNSTRUCTURED', 'LEGACY_BACKFILL', 'UNVERIFIED',
                   coalesce(created_at, now()), now()
              FROM src
            RETURNING id
        )
        UPDATE properties p SET address_id = src.address_id
          FROM src WHERE p.id = src.property_id
    """))
    missing = bind.scalar(sa.text("SELECT count(*) FROM properties WHERE address_id IS NULL"))
    if missing:
        raise RuntimeError(f"{missing} properties were not given an address")

    op.alter_column("properties", "address_id", nullable=False)
    op.create_unique_constraint("uq_properties_address_id", "properties", ["address_id"])
    op.create_foreign_key("fk_properties_address", "properties", "addresses",
                          ["address_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_properties_category", "properties", ["category"])
    op.create_check_constraint("ck_properties_category", "properties",
                               "category IS NULL OR category IN ('APARTMENT', 'HOUSE')")
    op.create_check_constraint("ck_properties_subtype_needs_category", "properties",
                               "subtype IS NULL OR category IS NOT NULL")
    op.create_check_constraint("ck_properties_subtype_in_category", "properties",
                               _subtype_check())


def downgrade() -> None:
    # Drops everything this revision added, including any geography and
    # structured-address data entered since. Legacy columns were never touched,
    # so properties keep their free-text location and property_type.
    for name in ("ck_properties_subtype_in_category", "ck_properties_subtype_needs_category",
                 "ck_properties_category"):
        op.drop_constraint(name, "properties", type_="check")
    op.drop_index("ix_properties_category", table_name="properties")
    op.drop_constraint("fk_properties_address", "properties", type_="foreignkey")
    op.drop_constraint("uq_properties_address_id", "properties", type_="unique")
    for column in ("address_id", "unit_number", "subtype", "category"):
        op.drop_column("properties", column)
    op.drop_table("geo_external_refs")
    op.drop_table("addresses")
    op.drop_table("geo_areas")
    op.drop_table("localities")
    op.execute("DROP TRIGGER IF EXISTS admin_areas_hierarchy ON admin_areas")
    op.execute("DROP FUNCTION IF EXISTS admin_areas_hierarchy()")
    op.drop_table("admin_areas")
    op.drop_table("geo_sources")
    op.drop_table("countries")
