# BP-10 — post-audit acceptance staging receipt

**Disposition date:** 2026-10-11. **Status:** CANDIDATE — documentation/evidence
staged for founder review; no approved merge or final implementation acceptance
is claimed. Founder-approved bounded dispositions are recorded in
[D-109](../DECISIONS.md). [PROJECT-STATUS](../PROJECT-STATUS.md) owns current status.

## Immutable implementation and evidence

| Identity | Value |
|---|---|
| Repository | ihorfroliak/homies |
| Observed main at staging | `be150da11b9838409fcf8ee2d8ca4bd8b0311307` |
| Frozen implementation branch | `claude/BP-10-idempotent-message-send` |
| Independently audited implementation SHA | `c385136c93826879b41509f1e30533ef46eee64c` |
| Implementation tree | `15c26d7aedd525e2b5ea4beef8383e313a1473fd` |
| Alembic head / parent | `11d778ab87a3` / `a3c5e7f9b1d4` |
| Implementation CI | [38047352161](https://github.com/ihorfroliak/homies/actions/runs/38047352161), exact candidate, six successful jobs |
| Independent Codex verdict | `PASS_WITH_NONBLOCKING_NOTES`; P0/P1/P2 = 0, P3 = 4, NOTE = 5 |
| Archived original report | [2026-10-11-bp10-codex-final-audit.md](2026-10-11-bp10-codex-final-audit.md), copied byte-identically |
| Original report SHA256 | `5b289d02391b7f049df65c71c2e4e6cb4a2fa6d48241100e4520d36678a9461a` |
| Documentation integration branch | `codex/BP-10-acceptance-integration` |

The first documentation child commit has the frozen implementation as its only
parent. Its SHA/tree and new CI are resolved from Git/PR evidence, not embedded
in their own commit ([TRACEABILITY](../engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit)).
A documentation child is **not a new independently audited implementation**.

Original bytes were inspected before archival: no real service credentials,
real customer data or private transcripts were identified. The original includes
explicitly synthetic disposable fixture credentials and machine-path provenance;
the founder authorized preserving these original bytes without reformatting or
redaction. This receipt adds no machine paths or raw archives.

## Secondary provenance and evidence limits

The following locally accessible artifacts were hash-checked against the prior
handoff; they remain secondary evidence. They are not reconstructed or
reformatted here.

| Artifact | SHA256 |
|---|---|
| Builder Phase B report | `181b18ffea3128895671e78b839376728db10d82bd454c2265d47875846aeccd` |
| Combined Phase C handoff | `3e44ca7fff73904253a179a4f97376c0704502846cefee6215d6f498bd99b3e2` |
| C1 preliminary | `07a0e7c50a322478443be0e84a2becb5a4d51794237826b72a084f49647fbd7e` |
| C1 final | `71f19c9eb7dfc66e7ac76d4bfc87f20a2718bb319548fb1da50836405da8cdf4` |
| C2 preliminary | `0b0133230168b0b57a8b5f4b8676f9b464d6e04f98ed06cd6bafa293ce129feb` |
| C2 final | `f24909828cbde82fff86f095945aebd1c5a49eba3463871ad8f9176f78ff4528` |
| Codex pre-trace hypothesis plan | `192016e470316bcf349d8a5b46804b35e4ef17b5e1efffb4414d5f655ff85ac0` |
| Codex frozen preliminary | `19b9cb03f8cfb01d151e4cb07e50c43e193a3913aa3f9e714c4e1181adf35892` |

C1/C2 both reported PASS_WITH_NONBLOCKING_NOTES. Codex froze findings before
reading separate conclusions, with summary/contract-count exposure disclosed.
Post-freeze corroboration is labeled in the original report. This staging
records completed reviews and approved finding dispositions; it does not
invent separate final C1/C2 acceptance decisions.

CI logs corroborated 1964 passed / one live-Stripe skip and 10/10 restore cases
on the implementation SHA. Local targeted checks, causal PostgreSQL/HTTP T22
controls, rollback and migration-lock proofs are listed separately in the
original report. The full suite was not rerun locally. Nine selected original
mutants reported kills, some structurally or through unsafe cleanup; **all 28
semantic kills are not independently certified**. C1's 15/24 controls are its
secondary counts, not Codex's. No production or long-term clock certification.

## Founder-approved P3 dispositions — narrow exceptions/debt

These are binding bounded dispositions from the 2026-10-11 founder instruction,
not a blanket waiver. Closure criteria and owners are in
[BP-10 §8](../tasks/BP-10-idempotent-message-send.md#8-founder-dispositions-and-bounded-debt-2026-10-11).

| Finding | Approved disposition |
|---|---|
| CX-01 | Only the submitting caller's own **rejected** `client_message_id` may appear in `detail[].input` of HTTP 422 for a send. Stored keys, other users' keys, message bodies and private fields are not permitted by this exception in success/GET/moderation/metrics/logging outputs. FD-8 / INV-12 otherwise stand; no runtime change. |
| CX-02 | Observed stale provider access during row/advisory waits is temporal authorization debt. Do not claim unchanged frequency or no amplification. Track a bounded post-wait current-side recheck; strict commit-time proof semantics require a separate founder/canonical decision if proposed. |
| CX-03 | Inherited NUL/unpaired-surrogate HTTP500 is bounded malformed-input debt. Later NUL rejection and safe validation/error rendering need negative tests; robust Unicode support is not certified. |
| CX-04 | Permanent T22 original-start/append coverage, unsafe cleanup and mutation oracle quality are debt. Own causal PG proofs support this candidate; they do not certify all 28 semantic kills. Track safe worker joins/cleanup and final-outcome assertions. |

The BP-10 contract's §3 and INV-12 row carry the exact CX-01 exception.
FD-1…FD-9, sender/key uniqueness, replay201, mismatch409, no replay domain writes,
UUIDv4 and release invariants remain unchanged. No product/test repair is
authorized by these dispositions.

## All five NOTEs retained

| Note | Remaining boundary / action |
|---|---|
| CX-N1 | Generic actual `commit_unknown`503 says check before repeating; keyed retry guarantee is documented. Optional operation-specific wording remains debt. |
| CX-N2 | `hide_parameters` is not server-log/driver DETAIL redaction. Sender/key in unique DETAIL was observed. Production log policy/retention remains unverified and required before launch; no new logging permission is granted. |
| CX-N3 | Physical old SQL compatibility does not admit the previous build: its actual lineage policy returns TOO_NEW. EXPAND does not authorize mixed-old rollout; rollback-to-previous BLOCKED remains. |
| CX-N4 | Structural/unit/semantic mutation evidence is distinguished; B09/B08 and cleanup qualifications remain visible. |
| CX-N5 | This archive/receipt represents the binding audit and scope/disposition semantics under 05 §14. It is a candidate record until founder-approved integration; unarchived raw evidence remains reference, not a substitute for this binding handoff. |

## Six Phase-B scope extensions

The founder explicitly confirmed these extensions in the final audit
authorization and reconfirmed recording them in this staging instruction.
The task contract already notes scope expansion. This records those permissions,
not hypothetical older transcript quotes:

1. `backend/app/core/business_metrics.py`
2. `backend/tests/test_obs02_03_metrics.py`
3. `backend/tests/test_moderation_core.py`
4. `backend/tests/test_schema_compat.py`
5. `backend/tests/test_release_pg.py`
6. `docs/production/RELEASE-AND-MIGRATION.md`

## Release and acceptance boundaries

- Schema EXPAND, rollback-to-previous BLOCKED, migration first; no automatic DB downgrade.
- Keyed frontend sends remain off until every serving backend runs BP-10 (BB-11).
  Source integration is not live rollout or beta-gate verification.
- IBB-001 remains the last formal backend baseline; no IBB-002 or acceptance
  of unrelated D-88 milestone scope is created.
- On this branch, BP-10 is reviewed and staged, not already merged into main.
  The proposed status transition becomes effective only after an explicit
  founder-approved merge containing the audited code and these records.
  BP-5 + BP-6 become next only after that merge and require their own authorization.
- Codex is the sole writer of this isolated BP-10 documentation context during
  staging; no work in the builder or AGENT-001 context is performed. Ownership
  returns when this bounded pass is handed off.

## Separate AGENT-001 disposition and suggested order

[AGENT-001 Draft PR #5](https://github.com/ihorfroliak/homies/pull/5) was rechecked:
open draft, candidate `bde0e0ef8b8b72f353aad95737cc9385ec7fa1fa`,
tree `529c818197d31ec8e9ecfb2ddfbddc3a0135acee`, exact-head
[CI38108566395](https://github.com/ihorfroliak/homies/actions/runs/38108566395)
six successful jobs.

Founder approves AGENT-001 as a permanent project-wide configuration foundation:
six Claude specialists plus six corresponding Codex roles, shared accepted
repository state, risk-based selection, and explicitly open native-dispatch
verification. It may be recommended for merge despite that open operational
check. No synchronized vendor caches/memories or native-routing guarantee is
asserted. AGENT-001 merge is still **not authorized**; its branch/PR is unchanged.

Suggested decisions: BP-10 documentation integration first, then reconcile and
review AGENT-001 against the resulting main. Both branches append
`docs/DEVLOG.md` from the same base; a textual conflict is possible and both
entries must be preserved. Recheck refs/conflicts/CI at the founder merge step;
do not silently rebase, amend the audited implementation, resolve the separate
AGENT-001 branch, or treat it as an FE-003 prerequisite.

BP-10 MERGE AUTHORIZED: NO
AGENT-001 MERGE AUTHORIZED: NO
FE-003 IMPLEMENTATION AUTHORIZED: NO
FE-VIS-001 IMPLEMENTATION AUTHORIZED: NO
PRODUCTION READY: NO
DEPLOYMENT: NO
