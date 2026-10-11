# AGENT-001 — Implementation and bounded verification evidence

Candidate implementation under the founder's Session B authorization; no product
or canonical decision changes. Base: `be150da11b9838409fcf8ee2d8ca4bd8b0311307`.
Contract: `docs/tasks/AGENT-001-agent-foundation.md`. Merge and deployment: NO.

## Source integrity and implementation

ZIP SHA256: `f38d404f752cfb65f20691b41d527ef4ef1d2b921cdfd1427949083d513d62ba`.
All 41 ZIP files matched the supplied unpacked package byte-for-byte; safe relative
paths and no duplicate file entries. All 26 manifest file hashes and the exact
payload inventory verified before installation. This proves package consistency,
not a signature from an independent publisher.

Inspected installer; unmodified Windows dry-run refused backslash manifest paths.
An in-memory normalization of its NEW list to forward slashes retained every
manifest/blob/branch/clean-worktree guard; corrected dry-run declared 24 files,
then applied those files in the dedicated AGENT-001 worktree only. Package and
transport files are not committed. No product runtime, CI workflow or canonical
files changed. The task contract, devlog entry and bounded checks are additional
AGENT-001 evidence paths.

Necessary corrections to the candidate package:
- Quote the micro-cycle YAML description, remove unsupported angle-bracket arrow
  characters, retain risk-proportional verification and higher canonical gates.
- Explicitly retain read-only boundaries when a specialist reads a writing skill.
- Explicit mandatory-review invocation and NOT VERIFIED/open gate on unavailable
  runtime; no silent substitution with parent self-review.
- No hashing oversized, unarchived transcripts; hash the bounded copy only.
- Use .NET SHA256 for Windows PowerShell portability: a real synthetic test found
  Get-FileHash unavailable under the inherited module path. No global settings changed.
- Clarify Codex filesystem-sandbox limits, unaccepted branch status and per-task archives.

## STATIC VERIFIED

- Six Claude YAML definitions: read-only Read/Grep/Glob, plan permission mode,
  distinct scope/description, 12-turn bounds; six corresponding standalone Codex
  TOMLs: name/description/developer_instructions and read-only sandbox.
- Project configuration parses; two concurrent spawned Codex threads by default;
  no parent sandbox/approval overrides. No pre-existing project Codex config existed.
- Root governance text preserved as a prefix, exactly one AGENT-001 block in each
  root guide; routing and Copilot auxiliary role consistent with 00/05/D-106.
- Revised skill YAML, task allowlist, preserved unrelated file identities and diff
  whitespace checked by `docs/engineering/agent001_checks.py`.
- `.claude/settings.json` including 80% compaction and hook wiring, SessionStart,
  context-survival rule and money-invariants remain identical to base Git blobs.
- Official native schemas checked against
  [OpenAI subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
  [OpenAI configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
  and [Claude subagents](https://code.claude.com/docs/en/sub-agents).

## RUNTIME VERIFIED — synthetic Windows hooks

Executed `python docs/engineering/agent001_checks.py` with Python 3.14.3/PyYAML
and Windows PowerShell. All three hook scripts parse. Eight invocations exit 0:
default PreCompact/PostCompact/SessionStart, transcript opt-in (small and >20 MiB),
summary opt-in (short and >16,384 chars), and resume with a second fresh archive.
Correct synthetic HEAD/branch/checkpoint recovered; no default transcript copy/hash,
summary body or raw hook input; valid opt-in copy/hash; oversize data skipped;
no synthetic repo writes or HEAD changes. No actual user transcript was read.

Observed per-call durations: 575–925 ms. Default PreCompact metadata: 881 bytes;
default Pre+Post metadata total: 1,336 bytes. These are single-run fixture measures,
not a before/after benchmark or evidence of provider token/cost savings.

## Native runtime verification

Pending bounded smoke on Claude Code 2.1.228 and codex-cli 0.162.0-alpha.2.
Static presence does not establish native loading, automatic routing or enforcement.

## Remaining limits

Provider cache hit rates, token/cost savings and cross-vendor memory synchronization
are NOT VERIFIED; no synchronization is claimed. Live /compact dispatch and Copilot
UI instruction loading are separate from synthetic scripts/static configuration.
Historical archives remain untouched. Existing global archive fallback requires a
fresh per-task HOMIES_CONTEXT_ARCHIVE for isolation. No product test suite or new
independent audit program is run for this bounded configuration-only task.
