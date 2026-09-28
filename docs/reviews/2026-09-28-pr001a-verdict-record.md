# PR-001A — verdict record (not the audit report)

**Provenance.** Independent audit PR-001A (Codex) of the PR-001 candidate
`4416e2b14b007ba50aab41cad8e23deea32c4678`. The complete audit report was
**not available** to the builder when PR-001R started: it was not in the
repository, in the audit's working directories, or in the prompt. It is
therefore **not archived here**, and nothing below reconstructs it. This file
records only what the founder's PR-001R task contract (2026-09-28) states about
the verdict. When the full report is supplied it is archived verbatim beside
this file, as `2026-09-28-pr001a-codex-pr001-audit.md` (byte-exact, `-text`).

**State.** `PR-001 → PR-001A → TARGETED FIX REQUIRED`. PR-001 is **not
accepted**.

**Verdict as relayed:** `PR_001_REQUIRES_TARGETED_FIXES` — P0 0 · P1 0 · P2 4 · P3 7.

| Id | Finding (as named in the PR-001R contract) | Blocking | Disposition |
|---|---|---|---|
| F1 | unhandled 500 loses request id | yes | PR-001R |
| F2 | CI audits an unpinned dependency resolution | yes | PR-001R |
| F3 | missing ENV fails open as local | yes | PR-001R |
| F11 | readiness can hang on a warm pooled DB connection | yes | PR-001R |
| F4 | development-DATABASE_URL guard is exact-string only | no | PR-001R |
| F5 | Alembic `fileConfig` wipes the application's logging | no | PR-001R |
| F6 | notification backlog alert multiplies by replica count; claims worker-death detection | no | PR-001R |
| F7 | restore drill can skip silently in CI | no | PR-001R |
| F8 | no guard against a Python minor/major runtime bump | no | PR-001R |
| F9 | canonical TASK-012 history heading lost | no | PR-001R |
| F10 | `main` CI runs cancelled by later `main` commits | no | PR-001R |
| N1 | request-id regex accepts a trailing newline | note | PR-001R |
| N5 | README presents Redis/Meilisearch/NATS as current | note | PR-001R |
| N7 | test named for rate limiting did not exercise a 429 | note | PR-001R |

Findings the contract numbers but does not describe here are not listed; see
the full report once archived.
