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

Tested implementation commit `d53454aa38eea08ee4ef17e46328c57bffe9d4b2`, tree
`086f2016cb3b8a47a684c68f77589c241258e7f2`. The subsequent evidence-only commit
changes this report; agent, hook, skill and configuration blobs remain those tested.

### Claude Code 2.1.228

RUNTIME VERIFIED: native initialization enumerated all six project specialists:
backend-reviewer, postgres-auditor, security-auditor, frontend-reviewer,
test-engineer, devops-reviewer. Initialization reported plan permission mode and
only Task/Glob/Grep/Read tools for this restricted smoke session. Native invocation
attempt exited 1 after 2.9 s: `Failed to authenticate: OAuth session expired and
could not be refreshed`. Therefore automatic selection, actual specialist execution
and adversarial runtime permission enforcement remain NOT VERIFIED. No login or
account settings were changed. The founder can renew Claude authentication before
same-SHA parity; this does not block publishing the explicitly requested Draft PR.

Invocation: `claude -p --output-format stream-json --verbose
--no-session-persistence --permission-mode plan --tools Read,Grep,Glob,Agent
--allowedTools Read,Grep,Glob,Agent --strict-mcp-config
--mcp-config '{"mcpServers":{}}' --setting-sources project
--settings '{"disableAllHooks":true,"autoMemoryEnabled":false}'
--max-budget-usd 1.50`, synthetic prompt via stdin. Hook lifecycle dispatch was
intentionally excluded here; the actual scripts were tested separately above.

### codex-cli 0.162.0-alpha.2

An initial CLI-only `projects.<path>.trust_level` override was rejected by strict
config parsing before a model turn. Retried without that unsupported override;
no persisted trust or global settings changed.

`codex -a never exec --strict-config --ignore-user-config --ephemeral
--sandbox read-only -C <AGENT-001 worktree> --json -` completed successfully in
21.4 s. Runtime exposed generic collaboration tools without a project-role selector.
The model explicitly reported the six native roles unavailable, with zero specialist
calls. Project-role loading/effective trust and native specialist dispatch therefore
remain NOT VERIFIED; do not equate this successful parent turn with native-role
acceptance. No workaround that merely names a generic agent was counted.

| Synthetic case | Observed result | Status |
|---|---|---|
| T1 locks A then B; T2 locks B then A | Parent selected postgres_auditor by policy; described deadlock and common lock order; no specialist call | Routing policy understood; native dispatch NOT VERIFIED |
| Clickable React div replaces button, no keyboard support | Parent selected frontend_reviewer by policy; described keyboard failure and native button repair; no specialist call | Routing policy understood; native dispatch NOT VERIFIED |
| README missing comma | Zero specialist calls and no edit | RUNTIME VERIFIED for this one no-delegation case |

The prompt supplied only these hypothetical inputs, required exact candidate scope,
prohibited shell/network/DB/Git/external mutations, bounded reviews to two total and
asked for actual dispatch evidence. Both runtimes were invoked from the dedicated
worktree. The worktree remained clean after the native attempts. No product audit
was performed. Automatic dispatch is not guaranteed by natural-language descriptions.

The Codex usage event exposed one sample: 34,086 input tokens, 28,288 cached input
tokens, 424 output tokens (41 reasoning output tokens). This is one native CLI usage
observation, not a measured cache improvement, cost saving or shared-memory result.

### Additional completed validation

- Package `verify.py <worktree>`: STATIC PASS (six plus six, config and skills).
- Skill Creator `quick_validate.py` for micro-cycle and security-probe: both valid.
- `python -m ruff check docs/engineering/agent001_checks.py`: all checks passed.
- `git diff --check <base>` and declared 27-file allowlist: pass.
- No backend/frontend suite, production services or databases were run.

## Remaining limits

Provider cache improvement, token/cost savings and cross-vendor memory synchronization
are NOT VERIFIED; no synchronization is claimed. The one observed usage sample above
is not a before/after comparison. Live /compact dispatch and Copilot
UI instruction loading are separate from synthetic scripts/static configuration.
Historical archives remain untouched. Existing global archive fallback requires a
fresh per-task HOMIES_CONTEXT_ARCHIVE for isolation. No product test suite or new
independent audit program is run for this bounded configuration-only task.


## Handoff and next owner action

Deliver this candidate as a Draft PR targeting main. The final full commit and tree
are supplied in the PR/handoff, not embedded self-referentially here. Claude parity
must fetch that exact commit into its own clean detached worktree, confirm the tree,
inspect this report and the AGENT-001 task contract, verify all six Claude agents,
re-run bounded synthetic routing after authentication is restored, and report any
remaining runtime gaps. It must not reimplement AGENT-001, restart BP-10, edit,
push, merge or deploy. Founder/GPT then decides the PR disposition.

AGENT-001 MERGE AUTHORIZED: NO. BP-10 MERGE AUTHORIZED: NO. DEPLOYMENT: NO.
