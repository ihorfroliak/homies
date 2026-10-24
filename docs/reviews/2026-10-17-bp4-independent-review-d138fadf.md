# BP-4 independent exact-SHA review — HOMIES-DELIVERY-002

Date: 2026-10-17. Independent reviewer: `/root/bp9_independent_review`, not the BP-4 implementer.

**Disposition: one bounded P3 contract defect requires disposition; repair recommended before claiming full BP-4 conformance.** No P0, P1 or P2 issue established. Authorization and privacy probes passed. This original-SHA report is not replaced by any subsequent builder repair.

## Immutable identity and boundaries

- Candidate: `d138fadf9d5fdcc245fae31fe7f2515283c979e3`.
- Tree: `3a92fdc3d9c4ed25e37ef26f161669ae592f3030`.
- Baseline: independently reviewed BP-9 `fb5b3e57a6e4881ab14ad378a15e15f49475e682`.
- Own detached managed worktree: `C:/Users/ihorf/.codex/worktrees/bp4-independent-audit/homies`.
- Source identity checked directly before and after testing; final Git status clean. No source edits, commits, pushes, deployments, database migrations or production activity.
- Scope: new display helper, conversation/viewing projection call sites, new BP-4 tests, OpenAPI and generated TypeScript additions. BP-9 authority logic was the reviewed baseline, not reopened as a broad audit.
- Sources: candidate AGENTS.md and 00-AUTHORITY, previously read 05 sections9/14 and 04a section24 OD-3, the BP-4 task contract, and the founder rule conveyed in this assignment. The candidate contract references D-113 in documentation Draft PR10; D-113 itself is not present in this candidate's DECISIONS.md. Its binding projection semantics are expressly represented in the candidate task contract, so no missing semantic rule was invented from memory.

## Findings

P0 CRITICAL: **0**. P1 HIGH: **0**. P2 MEDIUM: **0**. P3 LOW: **1**. NOTE: **0**.

### BP4-IR-01 — P3 LOW: retain Unicode mark characters even when their canonical combining class is zero

- **Location:** `backend/app/modules/engagement/display.py:24` (loop at23–26). Regression gap: `backend/tests/test_bp4_requester_display.py:16`, whose combining-mark example covers only a nonzero-class decomposed Latin accent.
- **Violated requirement:** `docs/tasks/BP-4-requester-display-name.md:14–15`: combining marks belonging to the initial are retained, with Unicode preserved. This is a concrete task-contract violation, not a new canonical identity rule or an optional styling preference.
- **Cause:** `unicodedata.combining(char)` returns a canonical combining-class number. Testing that number for truth does not recognize every Unicode mark. Spacing combining marks such as U+093F DEVANAGARI VOWEL SIGN I and U+09BE BENGALI VOWEL SIGN AA have class0 and are dropped by the loop.
- **Reproduction on the exact candidate:** two independent pure-function tests failed:

| Input | Actual | Expected under the mark-retention rule |
|---|---|---|
| `आशा किरण` | `आशा क.` | `आशा कि.` |
| `মিনা দাস` | `মিনা দ.` | `মিনা দা.` |

- **Impact/severity:** the provider receives a changed/incomplete initial for names using these marks. No authority bypass or private-data exposure was demonstrated; severity is P3 LOW.
- **Expected behavior:** retain the initial code point and following attached mark characters, while preserving the existing first/last whitespace-word rule and spelling. Do not transliterate, normalize into legal identity, or expand to the complete surname.
- **Suggested bounded repair:** recognize following mark categories Mn/Mc/Me, for example via `unicodedata.category(char).startswith("M")`, rather than relying on a nonzero canonical combining class. Add regression examples with class0 marks while retaining the existing decomposed-accent case. This recommendation does not claim a complete extended-grapheme parser or request one.
- **CANONICAL DECISION REQUIRED:** **NO**. The task already specifies mark retention. Repair remains with the authorized builder; the reviewer did not edit application code.
- **Early communication:** finding and reproduction sent to the parent/builder before finalizing this report.

## Verified behavior and privacy evidence

- The new helper reads only scalar `User.id` and `User.full_name` (`display.py:30–36`). No legal-name, email, phone or verification columns are selected by the projection query. It returns the exact agreed fallback for empty names; one word remains unchanged; multipart names use first word and last-word initial; whitespace splitting preserves the remaining word spelling.
- Provider conversation inbox and detail call the projection after the existing BP-9 authorization path. Stage and assignment remain behind their existing current-provider checks. Provider viewing projection follows `_provider_listing`; requester DTOs do not gain the display field.
- An independent multiple-row probe created two requesters and two viewings, then observed SQL for each provider list: exactly one `SELECT users.id, users.full_name ...` query per list, with no email or phone columns and no per-row user load. Expected names appeared on both rows.
- An independent projection-seam probe asserted no nonempty name projection on requester inbox/detail/my-viewings or on unverified-provider inbox/detail/provider-viewings. Requester routes returned200 without the field, provider inbox was empty, and denied detail/viewing reads returned404.
- Permanent HTTP tests exercise provider inbox/detail/stage/assignment/viewing DTOs, requester continuity, stranger/unverified/revoked provider denials, exact exclusion of seeded private email/phone/full surname and identity fields, and the fallback behavior. Those tests passed.
- The API delta is additive only to ProviderConversationOut and ProviderViewingOut; requester models remain unchanged. OpenAPI drift checks passed. Frontend change is generated schema declarations only, with no rendering implementation introduced. The contract correctly identifies display text as unverified and requires plain-text rendering; this review makes no browser rendering/XSS execution claim.

## Checks actually executed

Tests ran on Linux Python **3.12.15**, pytest **9.1.1**, cached `bp10c-test:c385136` image SHA256 `86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a`. Source was mounted read-only; `ENV=test`, `PYTHONDONTWRITEBYTECODE=1`, network disabled. All data was synthetic SQLite data. No PostgreSQL instance was needed or created for this display-only delta, and no other agent's database/container was accessed.

**Repository selection: 134 passed, 3 warnings, 158.79 seconds, exit0.**

```text
python -m pytest -p no:cacheprovider
  tests/test_bp4_requester_display.py
  tests/test_tst01_openapi_contract.py
  tests/test_conversations.py
  tests/test_viewings.py
  tests/test_bp9_verified_engagement.py -q
```

**Independent external probes: 2 passed, 2 failed, 23.22 seconds.** The two failures are the actual Unicode contract defect above. The batching and authorization-before-projection probes passed. There were no collection/setup failures in this review run, and failing assertions are not counted as passes.

```text
ENV=test PYTHONPATH=/src/backend
python -m pytest -p no:cacheprovider /audit/test_bp4_independent.py -v --tb=short
```

External probe file SHA256: `6b91a4edabcc635e79bd2705b568f832ccaae6f432b0b50004f09705ba2281ab`.

Other independently executed checks:

- `python -m ruff check --no-cache app tests/test_bp4_requester_display.py`: **all checks passed**.
- `python -m mypy --cache-dir=/tmp/bp4-mypy app`: **127 source files, no issues**; existing worker untyped-body notes remain.
- Baseline-to-candidate `git diff --check`: **passed**.
- Final HEAD/tree/status check: **exact and clean**.

Warnings were existing dependency deprecations for Starlette/httpx and the older422 status constant name. No product assertion failed in the repository selection. The builder's separately reported126-pass/two-setup-error run and reruns are not substituted for this independent execution.

## Limits and follow-up

No full-suite, browser test, TypeScript compiler rerun, semantic mutation score, independent CI retrieval, production readiness or deployment claim. Remote CI run39029895032 was pending in the parent assignment; this reviewer did not retrieve or certify its result. BP-9's bounded temporal-authorization limitation and all existing project debt remain unchanged.

Suggested next step: the authorized builder repairs BP4-IR-01 and supplies a new exact SHA/tree. A bounded follow-up should rerun the new mark regressions and the BP-4 projection/privacy/OpenAPI selection; the unchanged BP-9 audit need not be repeated. Founder acceptance, branch integration and permanent repository archival remain separate governance steps.

This report and its probes/evidence were saved outside the repository for verbatim parent archival. The report checksum is stored in an adjacent sidecar, avoiding a self-referential embedded hash.
