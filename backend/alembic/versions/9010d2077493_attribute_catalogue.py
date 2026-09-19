"""attribute catalogue

The JSONB tail on `properties` is what lets a new amenity ship without a
migration. It is also what lets `washing_machne` be stored happily, match no
filter for ever, and never raise: the owner believes the flat has a washing
machine and the search disagrees. This table is what turns that into a
rejected write.

The seed maps each code onto the vocabulary external pricing providers already
use (`external_code`, Wheelhouse here). Recording it now costs nothing;
discovering later that all of them need translating costs a layer.

Seeded in the migration rather than at startup so the catalogue is the same on
every machine and in CI, and so a code is never in use before it is defined.


Revision ID: 9010d2077493
Revises: c4d2e77a1b30
Create Date: 2026-09-19 19:05:41.995922

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9010d2077493'
down_revision: Union[str, Sequence[str], None] = 'c4d2e77a1b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



# (code, type, unit, filterable, sortable, allowed, PL, EN, external code)
# External codes come from Wheelhouse's amenity vocabulary where an equivalent
# exists; an empty one means no external counterpart, not an oversight.
CATALOGUE = [
    ("wifi", "bool", "", True, False, "", "Wi-Fi", "Wi-Fi", "internet"),
    ("wifi_mbps", "int", "Mbps", True, True, "", "Prędkość Wi-Fi", "Wi-Fi speed", ""),
    ("washing_machine", "bool", "", True, False, "", "Pralka", "Washing machine", "washing_machine"),
    ("dryer", "bool", "", True, False, "", "Suszarka", "Dryer", "dryer"),
    ("dishwasher", "bool", "", True, False, "", "Zmywarka", "Dishwasher", "dishwasher"),
    ("kitchen", "bool", "", True, False, "", "Kuchnia", "Kitchen", "kitchen"),
    ("oven", "bool", "", True, False, "", "Piekarnik", "Oven", "oven"),
    ("fridge", "bool", "", True, False, "", "Lodówka", "Fridge", "fridge"),
    ("air_conditioning", "bool", "", True, False, "", "Klimatyzacja", "Air conditioning", "air_conditioning"),
    ("heating", "bool", "", True, False, "", "Ogrzewanie", "Heating", "heating"),
    ("balcony", "bool", "", True, False, "", "Balkon", "Balcony", "balcony"),
    ("terrace", "bool", "", True, False, "", "Taras", "Terrace", "patio"),
    ("workspace", "bool", "", True, False, "", "Miejsce do pracy", "Workspace", "laptop_friendly_workspace"),
    ("tv", "bool", "", True, False, "", "Telewizor", "TV", "tv"),
    ("ev_charger", "bool", "", True, False, "", "Ładowarka EV", "EV charger", "ev_charger"),
    ("crib", "bool", "", True, False, "", "Łóżeczko dziecięce", "Crib", "travel_crib"),
    ("sauna", "bool", "", True, False, "", "Sauna", "Sauna", "sauna"),
    ("smoke_detector", "bool", "", True, False, "", "Czujnik dymu", "Smoke detector", "smoke_detector"),
    ("self_check_in", "bool", "", True, False, "", "Samodzielne zameldowanie", "Self check-in", "self_check_in"),
    ("private_entrance", "bool", "", True, False, "", "Osobne wejście", "Private entrance", "private_entrance"),
    ("step_free_access", "bool", "", True, False, "", "Wejście bez schodów", "Step-free access", "step_free_access"),
    (
        "window_view", "enum", "", True, False, "street,courtyard,park,water",
        "Widok z okna", "Window view", "",
    ),
]


def _seed_rows():
    # bulk_insert bypasses the model's Python defaults, so created_at is set
    # here explicitly rather than left to the ORM that is not involved.
    now = datetime.now(timezone.utc)
    return [
        {
            "code": code, "value_type": vtype, "unit": unit,
            "filterable": filterable, "sortable": sortable, "analytic": True,
            "allowed_values": allowed, "label_pl": pl, "label_en": en,
            "external_code": external, "created_at": now,
        }
        for code, vtype, unit, filterable, sortable, allowed, pl, en, external in CATALOGUE
    ]


def upgrade() -> None:
    """Upgrade schema."""
    table = op.create_table('attribute_definitions',
    sa.Column('code', sa.String(length=48), nullable=False),
    sa.Column('value_type', sa.String(length=12), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('filterable', sa.Boolean(), nullable=False),
    sa.Column('sortable', sa.Boolean(), nullable=False),
    sa.Column('analytic', sa.Boolean(), nullable=False),
    sa.Column('allowed_values', sa.String(length=500), nullable=False),
    sa.Column('label_pl', sa.String(length=120), nullable=False),
    sa.Column('label_en', sa.String(length=120), nullable=False),
    sa.Column('external_code', sa.String(length=48), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )

    op.bulk_insert(table, _seed_rows())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('attribute_definitions')
