# Context survival (CTX-001)

Context is cache. Durable state, in order of authority:

1. canonical repository (`docs/canonical/`, `CLAUDE.md`, `AGENTS.md`);
2. the current task contract (`docs/tasks/`);
3. Git — the exact branch and SHA;
4. the active task CHECKPOINT (path injected at session start; machine-local);
5. evidence (logs, results) next to the CHECKPOINT;
6. compact summaries and transcript archives;
7. this conversation's ephemeral context.

Rules:
- After a session starts from `compact` or `resume`: read the CHECKPOINT, check
  `git status` and HEAD, compare with its NEXT ACTION, then continue. Do not
  start a project-wide re-audit.
- A compact summary never outranks Git or the canon; if they disagree, the
  repository wins and the CHECKPOINT gets corrected.
- Retrieve what a decision needs (targeted reads), not the whole repository.
- Keep the CHECKPOINT current after every material phase, decision, result or
  blocker — no material decision may exist only in the conversation.
