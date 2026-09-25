"""TASK-008 mutation harness — final foundation hardening (TASK-007 N-05…N-10).

Same rules and runner as task002_mutants.py (green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256
verified). Usage from backend/, with a disposable PostgreSQL test database:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task008_mutants.py [MUTANT_ID ...]

Mutants marked "expected equivalent" remove a restriction the schema already
implies; they are run to confirm that, and reported as such.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

REPL = "tests/test_publication_proof_replacement_pg.py"
INV = "tests/test_membership_invite_race_pg.py"
AUTH = "app/modules/properties/authority.py"
ORGS = "app/modules/identity/organizations.py"
REPLACED = REPL + "::test_a_proof_row_replaced_while_its_lock_waits_does_not_carry_the_publication"

harness.MUTANTS = [
    # --- N-05: protection means "returned by the locking statement" ---------------------
    {
        "id": "D01-decision-through-proof-keys",
        "invariant": "decision uses the rows the locks returned, not the pre-lock keys",
        "file": AUTH,
        "old": "today=today, within=locked).where(",
        "new": "today=today, within=proof).where(",
        "tests": [REPLACED],
    },
    {
        "id": "D02-single-rows-recorded-as-expected",
        "invariant": "_lock_proof records what FOR SHARE returned (single-key tables)",
        "file": AUTH,
        "old": ("        ).all()) if ids else []\n"
                '    locked["representation_mandate_scopes"] = ['),
        "new": ("        ).all()) if ids else []\n"
                "        locked[key] = list(ids)\n"
                '    locked["representation_mandate_scopes"] = ['),
        "tests": [REPLACED + "[person_link]", REPLACED + "[org_link]",
                  REPLACED + "[membership]"],
    },
    {
        "id": "D03-mandate-scope-pairs-recorded-as-expected",
        "invariant": "_lock_proof records the mandate-scope rows FOR SHARE returned",
        "file": AUTH,
        "old": ("        ).with_for_update(read=True)).first() is not None\n    ]\n"
                '    ids = proof.get("property_authorities") or []'),
        "new": ("        ).with_for_update(read=True)).first() is not None or True\n    ]\n"
                '    ids = proof.get("property_authorities") or []'),
        "tests": [REPLACED + "[mandate_scope]"],
    },
    {
        "id": "D04-authority-scope-pairs-recorded-as-expected",
        "invariant": "_lock_proof records the authority-scope rows FOR SHARE returned",
        "file": AUTH,
        "old": ("        ).with_for_update(read=True)).first() is not None\n    ]\n"
                "    return locked"),
        "new": ("        ).with_for_update(read=True)).first() is not None or True\n    ]\n"
                "    return locked"),
        "tests": [REPLACED + "[authority_scope]"],
    },
    {
        "id": "D05-retry-after-dropped",
        "invariant": "the retryable 409 is machine-distinguishable (Retry-After)",
        "file": AUTH,
        "old": 'AUTHORITY_CHANGED, headers={"Retry-After": "0"},',
        "new": "AUTHORITY_CHANGED,",
        "tests": [REPLACED + "[person_link]"],
    },
    # --- N-06: every restriction of the protected evaluation -----------------------------
    {
        "id": "D06-personal-restriction-dropped",
        "invariant": "personal link must be a locked row",
        "file": AUTH,
        "old": ("        personal = personal.where(\n"
                '            PersonLegalParty.legal_party_id.in_(within.get("person_legal_parties")'
                " or []))\n"),
        "new": "",
        "tests": [REPLACED + "[person_link]"],
    },
    {
        "id": "D07-membership-restriction-dropped",
        "invariant": "membership must be a locked row",
        "file": AUTH,
        "old": ('            OrganizationMembership.id.in_(within.get("organization_memberships")'
                " or []),\n"),
        "new": "",
        "tests": [REPLACED + "[membership]"],
    },
    {
        "id": "D08-organisation-link-restriction-dropped",
        "invariant": "organisation link must be a locked row",
        "file": AUTH,
        "old": ("            OrganizationLegalParty.legal_party_id.in_(\n"
                '                within.get("organization_legal_parties") or []),\n'),
        "new": "",
        "tests": [REPLACED + "[org_link]"],
    },
    {
        "id": "D09-mandate-scope-pair-restriction-dropped",
        "invariant": "mandate scope must be a locked (mandate, scope) row",
        "file": AUTH,
        "old": ("            or_(false(), *(\n"
                "                and_(RepresentationMandateScope.mandate_id == m,\n"
                "                     RepresentationMandateScope.scope == s) for m, s in pairs)),\n"),
        "new": "",
        "tests": [REPLACED + "[mandate_scope]"],
    },
    {
        "id": "D10-whole-mandate-restriction-dropped",
        "invariant": "a mandate gained during the wait cannot count",
        "file": AUTH,
        "old": ("            RepresentationMandate.id.in_(within.get(\"representation_mandates\")"
                " or []),\n"
                "            or_(false(), *(\n"
                "                and_(RepresentationMandateScope.mandate_id == m,\n"
                "                     RepresentationMandateScope.scope == s) for m, s in pairs)),\n"),
        "new": "",
        "tests": [REPL + "::test_a_second_mandate_from_the_same_principal_gained_during_the_wait"
                         "_does_not_count"],
    },
    {
        "id": "D11-authority-scope-restriction-dropped",
        "invariant": "authority scope must be a locked (authority, scope) row",
        "file": AUTH,
        "old": "            PropertyAuthorityScope.property_authority_id.in_(scoped),\n",
        "new": "",
        "tests": [REPLACED + "[authority_scope]"],
    },
    {
        "id": "D12-whole-authority-restriction-dropped",
        "invariant": "an authority verified during the wait cannot count",
        "file": AUTH,
        "old": ('            PropertyAuthority.id.in_(within.get("property_authorities") or []),\n'
                "            PropertyAuthorityScope.property_authority_id.in_(scoped),\n"),
        "new": "",
        "tests": [REPL + "::test_a_second_authority_of_the_same_holder_gained_during_the_wait"
                         "_does_not_count"],
    },
    # expected equivalent: implied by the schema (see the TASK-008 mutation review)
    {
        "id": "E01-mandate-id-restriction-dropped",
        "invariant": "(expected equivalent) mandate id implied by the locked (mandate, scope) pairs",
        "file": AUTH,
        "old": ('            RepresentationMandate.id.in_(within.get("representation_mandates")'
                " or []),\n"),
        "new": "",
        "tests": [REPL],
    },
    {
        "id": "E02-organisation-id-restriction-dropped",
        "invariant": "(expected equivalent) organisation fixed by the locked membership and link",
        "file": AUTH,
        "old": '            Organization.id.in_(within.get("organizations") or []),\n',
        "new": "",
        "tests": [REPL],
    },
    {
        "id": "E03-legal-party-restriction-dropped",
        "invariant": "(expected equivalent) holder fixed by the locked authority; RESTRICT FK",
        "file": AUTH,
        "old": '            LegalParty.id.in_(within.get("legal_parties") or []),\n',
        "new": "",
        "tests": [REPL],
    },
    {
        "id": "E04-authority-id-restriction-dropped",
        "invariant": "(expected equivalent) implied by the locked (authority, scope) pairs",
        "file": AUTH,
        "old": '            PropertyAuthority.id.in_(within.get("property_authorities") or []),\n',
        "new": "",
        "tests": [REPL],
    },
    # --- N-07: the accept lock is exclusive -------------------------------------------------
    {
        "id": "D13-accept-lock-shared",
        "invariant": "accept takes an exclusive row lock before reading",
        "file": ORGS,
        "old": ("            OrganizationMembership.user_id == user.id,\n"
                "        ).with_for_update().execution_options(populate_existing=True)\n"),
        "new": ("            OrganizationMembership.user_id == user.id,\n"
                "        ).with_for_update(read=True).execution_options(populate_existing=True)\n"),
        "tests": [INV + "::test_two_accepts_of_one_invitation_are_serialised_before_either_reads_it"],
    },
    # --- N-09: an invitation drives only REVOKED -> INVITED -----------------------------------
    {
        "id": "D14-invite-reads-unlocked",
        "invariant": "invite locks the membership row before reading it",
        "file": ORGS,
        "old": ("            OrganizationMembership.user_id == user_id,\n"
                "        ).with_for_update().execution_options(populate_existing=True)\n"),
        "new": ("            OrganizationMembership.user_id == user_id,\n"
                "        )\n"),
        "tests": [INV + "::test_a_reinvitation_racing_a_join_cannot_demote_the_new_member"],
    },
    {
        "id": "D15-invite-demotes-active",
        "invariant": "an invitation never demotes an ACTIVE member",
        "file": ORGS,
        "old": '    if existing.status == "REVOKED":\n',
        "new": '    if existing.status != "INVITED":\n',
        "tests": [INV + "::test_an_invitation_leaves_an_active_member_or_pending_invitation"
                        "_untouched"],
    },
    {
        "id": "D16-invite-rewrites-pending",
        "invariant": "an invitation never changes a pending invitation",
        "file": ORGS,
        "old": '    if existing.status == "REVOKED":\n',
        "new": '    if existing.status != "ACTIVE":\n',
        "tests": [INV + "::test_an_invitation_leaves_an_active_member_or_pending_invitation"
                        "_untouched"],
    },
    # --- N-10: concurrent first invitations -------------------------------------------------
    {
        "id": "D17-first-invite-conflict-unhandled",
        "invariant": "a lost first-invitation INSERT decides on the winner's row",
        "file": ORGS,
        "old": ("        except IntegrityError:\n"
                "            # The concurrent invitation committed first; its row decides.\n"),
        "new": ("        except ArithmeticError:\n"
                "            # The concurrent invitation committed first; its row decides.\n"),
        "tests": [INV + "::test_two_first_invitations_of_one_person_never_fail_with_500"],
    },
]

if __name__ == "__main__":
    harness.main()
