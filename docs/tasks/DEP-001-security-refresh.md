# DEP-001 — Bounded dependency security refresh

Founder authorization: direct confirmation on2026-10-23 to update only certifi to2026.10.19 and Pillow to13.0.0, run full tests and independent review, commit/push a separate Draft PR, then include the verified repair in the FE-003 branch. No merge to main or deployment.

Base: main `4ed8fe8ab334a8d8e344b80e266da2be3b661aee`, tree `b29e0ceac644c026ecaa3d3e5dd01cc625b27f27`. Branch: `codex/DEP-001-security-refresh`. RiskR2: dependency/security change affecting untrusted-image decoding; independent exact-SHA review is mandatory. Existing TASK-002 media invariants remain unchanged.

CI39651899776 (FE-003 checkpoint) and39651483013 (documentation branch) failed the required dependency audit. The former completed2099 backend tests with2 skips and10 restore checks before reporting9 advisory rows for the two pinned packages. Earlier green runs are historical evidence, not a current dependency-audit exemption.

Scope: regenerate the constrained set from the tested Python3.12 environment, changing only certifi2026.7.22→2026.10.19 and Pillow12.3.0→13.0.0; raise the declared Pillow minimum to13.0.0. No application behavior changes, migrations, audit suppressions, advisory ignores or unrelated upgrades. Preserve JPEG/PNG validation, pixel/byte budgets, EXIF/ICC/privacy stripping, re-encoding and fixed error behavior. No providers or production systems are used.

Pre-implementation compatibility probe: read-only exact sourceec2bfa9ed8857eccc9551feaa30daa889d6c282c, cached Python3.12.15 runtime. Every original constrained version matched before installation; only the two approved packages changed afterward. Constraints were regenerated from installed metadata and full pip freeze was saved. pip checkPASS;81 media/upload/sanitization testsPASS(46.51s); dependency auditPASS with no known vulnerabilities at execution. These results do not substitute for the new candidate's full CI.

Acceptance: rebuilt supported test runtime with no unexpected pin drift; focused media regression evidence; required CI including full SQLite/PostgreSQL and restore tests, type/lint/contracts and dependency audit; independent exact-SHA compatibility/security review. Retain truthful skips and environment limitations. Push a separate Draft PR against main. Only after review and required CI pass may this exact repair be merged normally into the FE-003 feature branch, followed by combined CI. Main merge remains a founder decision.

Primary references: [Pillow13.0.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html), [certifi2026.10.19 release](https://pypi.org/project/certifi/2026.10.19/). Detailed execution evidence and immutable review will accompany the candidate; `docs/PROJECT-STATUS.md` remains the single volatile project-status owner on the documentation branch.

## Authorized extension — 2026-10-24

Founder explicitly approved adding filelock4.0.5 to4.2.1 to this same Draft PR, independent verification and required CI, then the verified repair's normal integration into FE-003. Main merge and deployment remain prohibited. This narrowly supersedes the original two-package scope; no other dependency update is authorized.

The initial exact candidate47b1be51002f6b28764a15cef12cf8d1b4bcec8a CI40069367584 completed1992 backend tests with1 skip,10 restore tests, mypy126 files,92.2% coverage and the other five jobs successfully. Its dependency audit failed on three filelock4.0.5 advisories (GHSA-v4x8-3wr5-3wq8, GHSA-9vhv-jxww-xfm5, GHSA-567q-5qvw-pf92), each identifying4.2.1 as a fix. The certifi/Pillow failures were removed. No audit suppression is introduced.

A disposable Python3.12.15 probe matched all70 original candidate pins, installed only filelock4.2.1 and regenerated constraints from installed metadata. No other version changed. pip check, FileLock contention/release, CacheControl FileCache set/get/delete and the full candidate dependency audit all passed. CacheControl's optional filecache is the installed consumer; the repository has no direct application import of filelock. These focused results do not substitute for the extended candidate's full CI or independent delta review.

The original independent47b1be5 report remains valid for unchanged certifi/Pillow code: no introduced P0-P3 findings;80 media tests passed plus one fixture setup error, followed by the unchanged isolated case passing. Its unknown-cause environment NOTE is retained without attributing the error to the clock or dependencies. Final integration still requires the extended exact candidate's independent delta closure and required CI.
