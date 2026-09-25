"""TASK-006 mutation harness — authority integrity cleanup (TASK-005 N-01…N-03).

Same rules and runner as task002_mutants.py (green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256
verified). Usage from backend/, with a disposable PostgreSQL test database:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task006_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

RACE = "tests/test_publication_authority_race_pg.py"
GAIN = "tests/test_publication_chain_gain_race_pg.py"
ACCEPT = "tests/test_membership_accept_race_pg.py"
AUTH = "app/modules/properties/authority.py"
ORGS = "app/modules/identity/organizations.py"
WAITS = RACE + "::test_a_loss_arriving_after_the_decision_waits_for_the_publication"

harness.MUTANTS = [
    # N-03: each relationship/scope row protection, killed by the repository suite.
    {
        "id": "B01-person-link-unprotected",
        "invariant": "person_legal_parties row protection",
        "file": AUTH,
        "old": '        ("person_legal_parties", PersonLegalParty.legal_party_id),\n',
        "new": "",
        "tests": [WAITS + "[person_link_sql]"],
    },
    {
        "id": "B02-organization-link-unprotected",
        "invariant": "organization_legal_parties row protection",
        "file": AUTH,
        "old": '        ("organization_legal_parties", OrganizationLegalParty.legal_party_id),\n',
        "new": "",
        "tests": [WAITS + "[org_link_sql]"],
    },
    {
        "id": "B03-mandate-scope-unprotected",
        "invariant": "representation_mandate_scopes row protection",
        "file": AUTH,
        # TASK-008: the lock result is now consumed (.first() is not None).
        "old": ("            RepresentationMandateScope.scope == mandate_scope,\n"
                "        ).with_for_update(read=True)).first() is not None\n"),
        "new": ("            RepresentationMandateScope.scope == mandate_scope,\n"
                "        )).first() is not None\n"),
        "tests": [WAITS + "[mandate_scope_sql]"],
    },
    {
        "id": "B04-authority-scope-unprotected",
        "invariant": "property_authority_scopes row protection",
        "file": AUTH,
        # TASK-008: the lock result is now consumed (.first() is not None).
        "old": ("            PropertyAuthorityScope.scope == authority_scope,\n"
                "        ).with_for_update(read=True)).first() is not None\n"),
        "new": ("            PropertyAuthorityScope.scope == authority_scope,\n"
                "        )).first() is not None\n"),
        "tests": [WAITS + "[authority_scope_sql]"],
    },
    # N-01: the decision may rest only on locked rows.
    {
        "id": "B05-decision-through-unlocked-chains",
        "invariant": "protected decision uses the locked proof only",
        "file": AUTH,
        # TASK-008: the decision is restricted to the rows the locks returned.
        "old": "today=today, within=locked).where(",
        "new": "today=today, within=None).where(",
        "tests": [GAIN],
    },
    # N-02: accept cannot overwrite a revoke.
    {
        "id": "B06-accept-reads-unlocked",
        "invariant": "accept_invitation locks the row before reading it",
        "file": ORGS,
        "old": ("            OrganizationMembership.user_id == user.id,\n"
                "        ).with_for_update().execution_options(populate_existing=True)\n"),
        "new": ("            OrganizationMembership.user_id == user.id,\n"
                "        )\n"),
        "tests": [ACCEPT],
    },
    {
        "id": "B07-accept-without-status-recheck",
        "invariant": "accept only a row that is still INVITED",
        "file": ORGS,
        "old": '    if membership is None or membership.status != "INVITED":\n',
        "new": "    if membership is None:\n",
        "tests": [ACCEPT],
    },
]

if __name__ == "__main__":
    harness.main()
