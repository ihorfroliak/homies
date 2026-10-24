# DEP-001 independent bounded dependency review

Date: 2026-10-24. Reviewer: independent read-only Codex review agent, not the candidate writer.

Exact audited commit: `47b1be51002f6b28764a15cef12cf8d1b4bcec8a`.
Tree: `a7782fcb9e244cc13726e6cff66c579adca1cd01`.
Base: `4ed8fe8ab334a8d8e344b80e266da2be3b661aee`.
Own isolated checkout: `C:/Users/ihorf/.codex/worktrees/dep001-review-recovery/homies`.
PR: https://github.com/ihorfroliak/homies/pull/18 (Draft).

## Disposition

No P0, P1, P2 or P3 defect introduced by the reviewed delta was substantiated. No canonical decision is required for this bounded repair. The review finds the two approved version changes compatible with the inspected sanitizer paths and the tests executed below. This is a narrow compatibility/security review, not supply-chain certification or approval to deploy or merge to main.

The independent focused run was NOT wholly green: 80 passed and one fixture setup error. The failing case passed in a diagnostic targeted repeat. Preserve both results; the first failure has no established cause. Required exact-candidate full CI, including dependency audit and PostgreSQL/restore checks, remains a separate acceptance gate. This report does not grant that gate a pass.

## Authority and bounded delta

Read AGENTS.md, canonical 00, governance 05 (including sections 9/10/14), DEP-001, TASK-002, clarification 04a section 15 and relevant IMPLEMENTATION-CONVERGENCE media dispositions. Canonical 04a section 15 and TASK-002 invariant 3 require maintained decoding, bounded input, re-encoding without original metadata, and verification before publication.

The complete base-to-candidate diff contains only:

- `backend/constraints.txt:15`: certifi 2026.7.22 to 2026.10.19.
- `backend/constraints.txt:43`: pillow 12.3.0 to 13.0.0.
- `backend/pyproject.toml:27-29`: explanatory security comment and Pillow minimum 13.0.0.
- `docs/tasks/DEP-001-security-refresh.md`: bounded authorization, evidence and acceptance record.

No application code, migrations, authorization chains, schemas, CI audit suppressions or unrelated dependency pins changed. Constraints line content matches the earlier regenerated metadata-derived candidate file. The checkout uses different newline representation, so raw file hashes are not asserted identical. Git diff-check passed; final exact SHA/tree unchanged and checkout status clean. Source was mounted read-only for all reviewer test execution. No repository writes, commits, pushes, main merges, deployments, providers, external attacks or production data access were performed.

## Checks actually executed by this reviewer

Disposable network-disabled container, source `/src` read-only, evidence outside checkout, ENV=test, no pytest cache or bytecode writes, temporary media storage, in-memory SQLite fixtures. No PostgreSQL URL or production connection was used.

Image: `homies-dep001-py312@sha256:1e56ae8c7fd60f35cfecfbfbafb3627680bb9d1c3b51f5113f7baea2be2ee354`.

| Check | Actual result |
|---|---|
| Interpreter/package identities | Python 3.12.15; Pillow 13.0.0; certifi 2026.10.19 |
| Installed metadata versus constraints | All 70 constraints exact; no missing or mismatched pin; only extra package pip 25.0.1 |
| pip check | PASS, no broken requirements |
| certifi bundle local SSLContext load | PASS, 120 CA certificates loaded; no external TLS endpoint tested |
| Three media suites | 80 passed, 1 setup error, 34 warnings, pytest duration 54.00 seconds |
| Targeted repeat of the error case with response-only diagnostic hook | 1 passed, 1 warning, 6.50 seconds; classified creation returned HTTP 201 with id |
| Exact source comparison with earlier probe | No differences in media module, three focused test files or media corpus between ec2bfa9ed8857eccc9551feaa30daa889d6c282c and this candidate |
| Git final identity, status, diff whitespace | PASS; exact commit/tree above; no checkout changes |

Executed suite command: `python -m pytest -q -p no:cacheprovider tests/test_media.py tests/test_media_pipeline.py tests/test_media_regressions.py`.

Diagnostic targeted command added an external `diagnostic_plugin` that only records classified-creation HTTP responses; it did not change requests, responses, application source or test assertions.

## NOTE N1: unexplained fixture setup error retained

Location: `backend/tests/test_media_regressions.py:41`, setup for `test_f02_a_hidden_payload_does_not_survive_to_the_public[APP1_after_scan]`.

Invariant: DEP-001 acceptance requires honest test evidence; governance 05 section 10 prohibits conclusions unsupported by execution. No sanitizer or canonical behavior violation was demonstrated by this error.

Evidence: the first focused run raised KeyError for `id` in the classified creation response before uploading any image. The original response status/body was not captured. Eighty other cases passed. A fresh targeted repeat captured HTTP 201 with an id and passed the entire media regression case. The first result remains immutable in `media-tests.txt` and `results.json`.

Expected behavior: fixture creation should return the documented success response and the focused test should reach image publication checks consistently.

Suggested disposition: retain this NOTE and require the exact-SHA complete CI gate. If the setup issue recurs, capture the failing status/body and investigate the listing fixture or its underlying endpoint in a separately authorized context. Do not attribute it to a clock, rate limit or dependency without causal evidence. No source repair was made or justified by the present reproduction.

CANONICAL DECISION REQUIRED: No.

## Compatibility and regression-test assessment

The sanitizer at `backend/app/modules/media/sanitize.py:117-175` opens only JPEG/PNG decoders, checks width/height and total pixels before pixel loading, applies EXIF orientation, handles ICC conversion, normalizes output modes, builds a new image from raw pixels, re-encodes, and re-decodes the result. Exceptions map to fixed refusal messages. These paths are unchanged.

Pillow 13 release notes document removal of Python 3.10 support and saving I-mode directly as PNG, plus removed APIs. This project requires Python >=3.12 and converts non-L/LA/RGB/RGBA PNG modes before saving; inspected production Pillow usage does not invoke the removed APIs. The release also documents relevant JPEG/EXIF/APNG security fixes. This supports the version remediation, but this review does not claim an identifier-by-identifier mapping of all nine historical audit rows. Source: [Pillow 13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).

The approved certifi release exists and declares Python >=3.7; its purpose is the CA root bundle used for TLS validation. Local load compatibility was checked above. Source: [certifi 2026.10.19 on PyPI](https://pypi.org/project/certifi/2026.10.19/).

Tests meaningfully check behavior: real EXIF/GPS/XMP/ICC/text payloads; JPEG segment and PNG chunk checks; independent output re-decoding; EXIF orientation and color modes; APNG first-frame output; malformed and unsupported inputs; pixel-budget boundaries; streaming and false-Content-Length limits; concurrency-slot refusal; authorization, moderation/quarantine, and upload-to-public-GET behavior. The deterministic mutation test exercises 400 modified image inputs and requires either clean output or RejectedImage. This is useful regression coverage, not comprehensive native-decoder fuzzing. No new mutation campaign or sanitizer instrumentation was executed.

## Evidence provenance and limitations

Reviewer-owned evidence directory: `../dep001-47b1be5/`, relative to this report directory. Files include probe.py, installed-versions.json, results.json, pip-check.txt, media-tests.txt, diagnostic_plugin.py, targeted.py, targeted-test.txt, targeted-result.json and targeted-responses.json. A SHA-256 manifest accompanies the report.

Earlier builder probe evidence in `../../dependency-triage/` was inspected, not re-executed by this reviewer: its pip check, 81-test success and no-known-vulnerabilities audit belong to source ec2bfa9ed8857eccc9551feaa30daa889d6c282c. They are distinct from the candidate execution results above.

At report preparation the coordinator reported exact-candidate CI run 40069367584 with five jobs successful and backend full tests still running. This reviewer has not independently verified the final CI outcome. The prior FE-003 2099 tests / 2 skips / 10 restores are not claimed as candidate checks. Ruff, mypy, full SQLite/PostgreSQL, restore, OpenAPI drift and fresh network dependency audit were not executed by this reviewer; the coordinator retains responsibility for verifying the exact-SHA required CI and combined FE-003 CI before authorized branch integration.

Deployment status: NOT DEPLOYED. Main merge: NOT AUTHORIZED by this review.
