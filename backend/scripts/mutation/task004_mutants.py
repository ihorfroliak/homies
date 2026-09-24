"""TASK-004 mutation harness — atomic publication authorisation.

Same rules and runner as task002_mutants.py (green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256
verified). Usage from backend/, with a disposable PostgreSQL test database:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task004_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

T = "tests/test_publication_authority_race_pg.py"
AUTH = "app/modules/properties/authority.py"

harness.MUTANTS = [
    {
        "id": "A01-membership-row-unprotected",
        "invariant": "membership row protection",
        "file": AUTH,
        "old": '        ("organization_memberships", OrganizationMembership.id),\n',
        "new": "",
        "tests": [T + "::test_a_loss_arriving_after_the_decision_waits_for_the_publication"
                      "[membership]"],
    },
    {
        "id": "A02-mandate-row-unprotected",
        "invariant": "mandate row protection",
        "file": AUTH,
        "old": '        ("representation_mandates", RepresentationMandate.id),\n',
        "new": "",
        "tests": [T + "::test_a_loss_arriving_after_the_decision_waits_for_the_publication"
                      "[mandate]"],
    },
    {
        "id": "A03-organization-row-unprotected",
        "invariant": "organisation row protection",
        "file": AUTH,
        "old": '        ("organizations", Organization.id),\n',
        "new": "",
        "tests": [T + "::test_a_loss_arriving_after_the_decision_waits_for_the_publication"
                      "[organization_sql]"],
    },
    {
        "id": "A04-legal-party-row-unprotected",
        "invariant": "legal party row protection",
        "file": AUTH,
        "old": '        ("legal_parties", LegalParty.id),\n',
        "new": "",
        "tests": [T + "::test_a_loss_arriving_after_the_decision_waits_for_the_publication"
                      "[party_sql]"],
    },
    {
        "id": "A05-no-protected-decision",
        "invariant": "final authorisation guard",
        "file": AUTH,
        # TASK-006 split the call into `proof = _proof(...)` / `_lock_proof`.
        "old": ("    proof = _proof(db, user.id, property_id, scope, verified=verified)\n"
                "    _lock_proof(db, proof)\n"),
        "new": "    return\n",
        "tests": [T + "::test_a_loss_committed_before_the_decision_refuses_the_publication"],
    },
    {
        "id": "A06-organization-status-ignored",
        "invariant": "organisation status is part of the chain",
        "file": AUTH,
        "old": '            Organization.status == "ACTIVE",\n        )\n    )\n    mandate_scopes',
        "new": "        )\n    )\n    mandate_scopes",
        # Since TASK-006 the proof query checks the status too, and the
        # decision only sees proof rows: removing one copy alone refuses with
        # 409 instead of publishing. Both copies go (the invariant is "status
        # is part of the chain" wherever it is evaluated). The test observes
        # the publication itself, not can_act (which shares the mutated code).
        "extra": [(
            '            Organization.status == "ACTIVE",\n'
            "            OrganizationLegalParty.legal_party_id.in_(holders),\n",
            "            OrganizationLegalParty.legal_party_id.in_(holders),\n",
        )],
        "tests": [T + "::test_no_invalid_chain_passes_the_protected_decision[suspended_org]"],
    },
    {
        "id": "A07-legal-party-status-ignored",
        "invariant": "legal party status is part of the chain",
        "file": AUTH,
        # TASK-006 reformatted _chains; compound with the proof query for the
        # same reason as A06.
        "old": ("                _holder_parties(user_id, scope, today, within)),\n"
                '            LegalParty.status == "ACTIVE",\n'
                "            _in_force(today),\n"),
        "new": ("                _holder_parties(user_id, scope, today, within)),\n"
                "            _in_force(today),\n"),
        "extra": [(
            "        PropertyAuthority.holder_legal_party_id.in_("
            "_holder_parties(user_id, scope, today)),\n"
            '        LegalParty.status == "ACTIVE",\n',
            "        PropertyAuthority.holder_legal_party_id.in_("
            "_holder_parties(user_id, scope, today)),\n",
        )],
        "tests": [T + "::test_no_invalid_chain_passes_the_protected_decision[inactive_party]"],
    },
    {
        "id": "A08-expiry-on-request-clock",
        "invariant": "validity dates read at the decision (database clock)",
        "file": AUTH,
        # TASK-006: the decision is now the `protected` evaluation.
        "old": "    today = decision_date(db)\n    protected = _chains(",
        "new": "    today = _today()\n    protected = _chains(",
        "extra": [(
            "    today = decision_date(db)\n    authorities = select(",
            "    today = _today()\n    authorities = select(",
        )],
        "tests": [T + "::test_a_mandate_expiring_before_the_decision_refuses_the_publication"],
    },
    {
        "id": "A09-mandate-expiry-ignored",
        "invariant": "mandate effective_until is enforced",
        "file": AUTH,
        "old": ("            or_(\n                RepresentationMandate.effective_until.is_(None),\n"
                "                RepresentationMandate.effective_until >= today,\n            ),\n"),
        "new": "",
        "tests": [T + "::test_a_mandate_expiring_before_the_decision_refuses_the_publication",
                  T + "::test_no_invalid_chain_passes_the_protected_decision[expired_mandate]"],
    },
]

if __name__ == "__main__":
    harness.main()
