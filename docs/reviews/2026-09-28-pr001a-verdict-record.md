# PR-001A — verdict record (not the audit report)

**Provenance.** Independent audit PR-001A (Codex) of the PR-001 candidate
`4416e2b14b007ba50aab41cad8e23deea32c4678`. The complete report was not found
when PR-001R started (not in the repository, the prompt or the Codex working
folders searched first); it was later located in the auditor's evidence
directory `homies-audit-evidence/PR-001A/FINAL-REPORT.md` (outside the repository)
(27 656 bytes, sha256 `2cd3dfe54dd7ffcdf8bce2a8e41fe3b0cae5148acc8b171e48842f877193d061`;
the auditor recorded no hash of its own) and is **archived verbatim** as
[`2026-09-28-pr001a-codex-pr001-audit.md`](2026-09-28-pr001a-codex-pr001-audit.md)
(byte-exact, `-text`). The table below was written from the PR-001R contract
before the report was found and was then checked against it: it matches.

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

Not repaired in PR-001R (not in its contract; see the report): F8's build-isolation
`pip`/`setuptools` and `postgresql-client-16` minor pinning; notes N2, N3, N4, N6, N8.
