# CTX-002 — Context, provider caching and recovery (proposed)

**Distinct concepts:** (1) Claude/OpenAI provider **prompt caches**, internal and platform-specific; (2) a session's live conversation **context and auto-compaction**; (3) local transcript copies; (4) Git/task CHECKPOINT state; (5) build/test caches (pip, uv, Next, CI). These are not interchangeable. No truthful cross-vendor private-memory or provider-cache synchronization is possible via Git files.

## Identified defects and bounded repairs

- Existing Claude `PreCompact` hook copied transcripts up to **300 MB on every compaction** (at most when transcript present), consuming disk I/O and potentially retaining sensitive data. AGENT-001 makes it opt-in (`HOMIES_ARCHIVE_FULL_TRANSCRIPT=1`) with **20 MiB max**. No transcript copy/hash by default. When opted in, hash only the bounded archived copy; oversized transcripts are neither copied nor hashed.
- Existing `PostCompact` stored the whole raw hook event including sensitive `compact_summary`. AGENT-001 removes `hook_input`; summary-file persistence becomes opt-in (`HOMIES_ARCHIVE_COMPACT_SUMMARY=1`, <= 16,384 characters). Only lightweight local metadata is recorded by default.
- Existing `.claude/settings.json` and the 80% `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` remain unchanged: **no cache savings are claimed** without runtime benchmarks, and provider internals remain opaque.
- `HOMIES_CHECKPOINT` and `HOMIES_WORKTREE` are machine-local environment variables; context-session-start.ps1 points to the CHECKPOINT and real Git SHA; verify on local PowerShell. CHECKPOINT is updated after material progress, not only at compaction.
- Historical archives are NOT deleted automatically. Their retention/security must be reviewed separately; avoid copying personal data, private conversations or secrets to Git. Keep local evidence directories private, filesystem-restricted, and outside the tracked repository.

## Shared state contract

For every handoff supply `task / contract / base+exact candidate SHA and tree / changed files + permissions / tests+CI evidence / unresolved decision+next action`. Load the **smallest relevant** repository docs. Git and canon outrank stale summaries. Never use a branch label alone as an immutable audit target. ChatGPT Work, Claude, Codex and Copilot must read the same accepted Git state, but their model contexts, caches and auto-compaction events are separate. If a PR has not merged, its branch remains a candidate and does not silently update `main`.

## Diagnostics / performance

Before declaring cache improvements effective, collect baseline and after measurements: Pre/PostCompact wall time and archive bytes, average prompt context growth, provider cache hit metrics where surfaced, retries after compaction, number of lost decisions, and task cycle time. Avoid automatic full cache clears. Cache invalidation should be limited to a diagnosed specific build/test cache issue.

## Verification that cannot be fabricated

On Windows PowerShell: parse hook scripts; invoke them with synthetic JSON input in a temp directory and fake Git repo, measure archive sizes, confirm no full copies/summary/raw hook data by default, confirm opt-in limits, and verify resume recovers the correct worktree SHA/checkpoint. Manual actual Claude /compact in an isolated session is optional. If PowerShell or runtime unavailable, label runtime check PENDING. Never claim provider prompt caching changed because hooks changed.

**Operational verification:** Run `python docs/engineering/agent001_checks.py` with Python 3.11+, PyYAML and Windows PowerShell. The bounded checks use disposable synthetic Git/transcript fixtures and report actual hook timings and archive sizes. See `AGENT-001-AUDIT.md` for results and remaining runtime gaps. Set a fresh `HOMIES_CONTEXT_ARCHIVE` outside the repository for each task/worktree; the preserved SessionStart hook uses the configured archive and does not infer task ownership from a shared historical archive. CTX-002 does not change provider prompt-cache TTLs, credentials, billing or build caches.
