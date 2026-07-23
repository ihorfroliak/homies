# Recovered from an early draft — review before use

These files come from a **different, unrelated git repository** that was found in the
Recycle Bin on 2026-07-23 (original location `C:\Users\ihorf\Documents\homies`).
Its single commit `32be020 "docs: add OpenAPI contracts, AsyncAPI events, ADR, diagrams"`
does not exist in this repository's history — it was a parallel first attempt, not an ancestor.

**Nothing here is authoritative.** Read it, decide, then either promote a document into
`docs/adr/` with the next free number, or delete this folder.

## Why only these six

The draft carried 9 ADRs. Five of them cover decisions this repository already records
under different numbers (modular monolith, money as minor units, event-driven integration,
monorepo, contract-first APIs), so they were left behind. The four kept here argue
decisions the current ADR set does **not** cover:

| File | Decision |
|---|---|
| `0003-python-fastapi.md` | choice of Python + FastAPI |
| `0005-cqrs-search.md` | CQRS read model for search |
| `0006-identity-jwt-mvp.md` | JWT identity for the MVP |
| `0007-stateless-jwt-roles.md` | stateless JWT role handling |

The two PNGs are rendered diagrams; `docs/diagrams/` currently holds only
`bounded-contexts.md`, so they have no counterpart here.

The numbers in the filenames are the **draft's** numbering and collide with the current
`docs/adr/0003`–`0007`. Renumber on promotion.

## Not copied

Still in the Recycle Bin if wanted: the five overlapping ADRs, `docs/adr/README.md`,
and `docs/api/spectral.yaml` (this repository has `.spectral.yaml` at its root).
The draft's `docs/api/*.yaml` are **older** than the tracked versions here — do not restore those.
