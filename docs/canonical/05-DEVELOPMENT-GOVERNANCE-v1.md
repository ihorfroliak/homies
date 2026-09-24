# 05 — Development Governance v1

How the founder, ChatGPT, Claude Code and Codex work on one repository without
losing each other's work or deciding things by stealth. Established 2026-09-24
(TASK-000).

## 1. Roles

| Who | Role | Decides | Does not |
|---|---|---|---|
| **Founder** | Owner, final authority | Business-model changes, canonical architecture, merges and releases, production deployment, activating paid providers, legal/compliance choices | — |
| **ChatGPT** | Product & architecture arbiter (advisory) | Recommends on product logic, domain semantics, architecture, strategy, compliance framing; interprets implementation-vs-canon conflicts; prepares Task Contracts | Sees nothing uncommitted; has no access to agents' memory |
| **Claude Code** | Primary builder | Implements approved Task Contracts: code, migrations, tests, adversarial/concurrency/security validation, repository docs, verification evidence; fixes review findings | Silently override canonical product or domain decisions |
| **Codex** | Independent auditor, **read-only by default** | Audits an exact commit: authorisation, security, migrations, concurrency, privacy, data integrity, tests and mutation quality, domain drift | Edit a bounded context another agent is writing; act as a second simultaneous primary developer |

ChatGPT synchronises only through committed canonical documents, exact SHAs,
Claude's reports, Codex's audit reports and what the founder brings.

## 2. Canonical hierarchy

[00-AUTHORITY](00-AUTHORITY.md). Higher wins; conflicts become CANONICAL
DECISION REQUIRED (§8).

## 3. Single-writer rule

**One bounded context has exactly one active writer at a time.**

* Claude writing `engagement/viewings` while Codex audits a frozen commit: fine.
* Two agents editing the pricing service, or the same migrations, at once:
  forbidden.

If the founder explicitly assigns Codex a fix, Claude stops writing that
context; Codex works on its own branch; ownership returns afterwards.

## 4. No shared dirty worktree

Agents never write inside the same dirty checkout. Separate worktrees or
branches:

```text
homies/            main (founder)
homies-claude/     claude/<task-id>-<short-name>
homies-codex/      codex-audit/<task-id>-<sha>
```

`git worktree add ../homies-codex codex-audit/TASK-001-<sha> <sha>` gives
Codex its own tree pinned to the audited commit. Codex normally makes no
commits during an audit; a Codex fix branch needs explicit founder
authorisation.

*Why this rule exists here:* on 2026-09-23 a second agent session worked in
the same checkout as Claude. Its fix to `engagement/router.py::_out()` entered
Claude's commit `62a4add` without attribution, and its uncommitted work had to
be recovered into preservation branches in TASK-000.

## 5. Exact SHA is the handoff contract

A handoff names a full commit SHA. Codex audits exactly that commit — never
"the latest changes" or "the current folder".

## 6. Task Contracts

Every meaningful task has a contract in `docs/tasks/TASK-XXX-<name>.md`
([template](../tasks/TASK-TEMPLATE.md)): status, goal, canonical references,
baseline SHA, in scope, out of scope, hard invariants, acceptance criteria,
required tests, security/privacy considerations, forbidden regressions,
expected report. The founder (with ChatGPT) approves the semantics; Claude
implements; Codex audits when required.

## 7. Merge flow

```text
Task Contract → Claude branch → tests green → SHA frozen
  → Codex audit (if required) → ChatGPT/founder review
  → Claude fixes → re-audit if material → founder approves merge → main
```

Agents do not mutate `main` independently. Claude pushes task branches;
the founder merges.

## 8. CANONICAL DECISION REQUIRED

When implementation reveals a real business/domain contradiction, the
implementer stops that path and records:

```text
CANONICAL DECISION REQUIRED
Canonical rule:        <which source, which section>
Current implementation:<what the code does, file:line>
Alternatives:          <A, B, …>
Recommended:           <one, with reason>
Consequences:          <of each>
```

The founder takes it to ChatGPT; the answer comes back as a committed change
to the canonical documents or a Task Contract.

## 9. High-risk changes need independent audit

Codex audit is mandatory before final acceptance for changes touching:
authentication; authorisation; PropertyAuthority; payment; ledger; migrations
that transform data; private identity data; exact property address; media or
any untrusted-binary parsing; safety; incidents; admin privilege;
concurrency/locking; booking/availability; security controls; backup and
recovery; irreversible data operations. Simple UI or content work does not.

## 10. Codex audit report

Findings classified **P0 CRITICAL · P1 HIGH · P2 MEDIUM · P3 LOW · NOTE**.
Each: file/line or migration; violated invariant; reproduction/evidence;
expected behaviour; suggested repair; whether a canonical decision is needed.
Canonical violations are distinguished from optional improvements. No score
inflation, no "looks good".

## 11. Claude implementation report

```text
TASK · BASELINE SHA · IMPLEMENTATION SHA · FILES CHANGED · DOMAIN IMPACT
MIGRATIONS · TESTS RUN · MUTATION/ADVERSARIAL TESTS · SECURITY/PRIVACY NOTES
DEVIATIONS · KNOWN LIMITATIONS · DEPLOYMENT STATUS · FINAL GIT STATUS
HANDOFF SHA FOR CODEX
```

Only tests actually executed are reported. Mutation runs require a green
baseline first and count a mutant as caught only when a test fails (not when
collection errors).

## 12. Conflict resolution between agents

A Codex finding Claude disagrees with is not argued away in code: Claude
records the disagreement with evidence in its report; the founder decides,
with ChatGPT if needed.

## 13. Hard limits for every agent

No production deployment, no production infrastructure changes, no paid
provider activation, no production data mutation without explicit founder
approval for that action.
