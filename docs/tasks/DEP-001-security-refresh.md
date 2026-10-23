# DEP-001 — Bounded dependency security refresh

Founder authorization: direct confirmation on2026-10-23 to update only certifi to2026.10.19 and Pillow to13.0.0, run full tests and independent review, commit/push a separate Draft PR, then include the verified repair in the FE-003 branch. No merge to main or deployment.

Base: main `4ed8fe8ab334a8d8e344b80e266da2be3b661aee`, tree `b29e0ceac644c026ecaa3d3e5dd01cc625b27f27`. Branch: `codex/DEP-001-security-refresh`. RiskR2: dependency/security change affecting untrusted-image decoding; independent exact-SHA review is mandatory. Existing TASK-002 media invariants remain unchanged.

CI39651899776 (FE-003 checkpoint) and39651483013 (documentation branch) failed the required dependency audit. The former completed2099 backend tests with2 skips and10 restore checks before reporting9 advisory rows for the two pinned packages. Earlier green runs are historical evidence, not a current dependency-audit exemption.

Scope: regenerate the constrained set from the tested Python3.12 environment, changing only certifi2026.7.22→2026.10.19 and Pillow12.3.0→13.0.0; raise the declared Pillow minimum to13.0.0. No application behavior changes, migrations, audit suppressions, advisory ignores or unrelated upgrades. Preserve JPEG/PNG validation, pixel/byte budgets, EXIF/ICC/privacy stripping, re-encoding and fixed error behavior. No providers or production systems are used.

Pre-implementation compatibility probe: read-only exact sourceec2bfa9ed8857eccc9551feaa30daa889d6c282c, cached Python3.12.15 runtime. Every original constrained version matched before installation; only the two approved packages changed afterward. Constraints were regenerated from installed metadata and full pip freeze was saved. pip checkPASS;81 media/upload/sanitization testsPASS(46.51s); dependency auditPASS with no known vulnerabilities at execution. These results do not substitute for the new candidate's full CI.

Acceptance: rebuilt supported test runtime with no unexpected pin drift; focused media regression evidence; required CI including full SQLite/PostgreSQL and restore tests, type/lint/contracts and dependency audit; independent exact-SHA compatibility/security review. Retain truthful skips and environment limitations. Push a separate Draft PR against main. Only after review and required CI pass may this exact repair be merged normally into the FE-003 feature branch, followed by combined CI. Main merge remains a founder decision.

Primary references: [Pillow13.0.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html), [certifi2026.10.19 release](https://pypi.org/project/certifi/2026.10.19/). Detailed execution evidence and immutable review will accompany the candidate; `docs/PROJECT-STATUS.md` remains the single volatile project-status owner on the documentation branch.
