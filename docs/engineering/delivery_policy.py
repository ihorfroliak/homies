"""Small, local delivery policy; no network, model calls, merge or deploy executor.

Use --help. Trusted operator attestations are checked for identity and completeness,
not cryptographic truth. Canonical contracts and live GitHub evidence remain authority.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

STATES = (
    "PLANNED", "AUTHORIZED", "READY", "IN_PROGRESS", "BUILDER_VERIFIED",
    "REVIEW_REQUIRED", "REVIEWED", "CI_GREEN", "DRAFT_PR_READY",
    "MERGE_AUTHORIZED", "INTEGRATED", "BLOCKED",
)
# Order breaks ties deterministically, prioritizing privacy and database hazards.
ROUTES = {
    "security": "security-auditor", "privacy": "security-auditor",
    "identity": "security-auditor", "authorization": "security-auditor",
    "authentication": "security-auditor", "property-authority": "security-auditor",
    "address": "security-auditor", "media": "security-auditor",
    "safety": "security-auditor", "incidents": "security-auditor",
    "admin": "security-auditor", "payment": "backend-reviewer",
    "ledger": "backend-reviewer", "irreversible": "postgres-auditor",
    "backup": "devops-reviewer",
    "postgres": "postgres-auditor", "migration": "postgres-auditor",
    "locking": "postgres-auditor", "availability": "postgres-auditor",
    "backend": "backend-reviewer", "frontend": "frontend-reviewer",
    "testing": "test-engineer", "ci": "devops-reviewer",
    "recovery": "devops-reviewer", "docs": None,
}
# Governance 05 section 9; callers must classify every affected surface honestly.
MANDATORY = {
    "security", "privacy", "identity", "authorization", "migration", "locking",
    "availability", "recovery", "authentication", "property-authority", "address",
    "media", "safety", "incidents", "admin", "payment", "ledger", "irreversible", "backup",
}
METRICS = {"compaction_ms", "recovery_ms", "duplicate_context_reads", "agent_calls",
           "input_tokens", "output_tokens", "cycle_ms"}
SHA = re.compile(r"[0-9a-f]{40}")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   encoding="utf-8", timeout=20).strip()


def validate(task):
    for key in ("id", "context", "contract", "authorization", "base_sha", "base_branch",
                "branch", "risk", "changes", "state", "priority", "dependencies"):
        require(key in task, "missing task field: " + key)
    for key in ("id", "context"):
        require(isinstance(task[key], str) and NAME.fullmatch(task[key]), "invalid " + key)
    require(task["risk"] in ("R0", "R1", "R2", "R3"), "invalid risk")
    require(task["state"] in STATES, "invalid state")
    require(isinstance(task["priority"], int), "priority must be integer")
    require(SHA.fullmatch(task["base_sha"]), "full base SHA required")
    require(task["branch"].startswith(("codex/", "claude/")), "feature branch required")
    require(task["branch"] != task["base_branch"], "distinct feature/base branches required")
    require(task["contract"].startswith("docs/tasks/") and ".." not in task["contract"],
            "repository task contract required")
    require(isinstance(task["changes"], list) and task["changes"], "changes required")
    require(set(task["changes"]) <= ROUTES.keys(), "unknown change surface")
    for dep in task["dependencies"]:
        require(set(dep) == {"id", "mode", "sha"}, "dependency identity required")
        require(dep["mode"] in ("integrated", "stacked"), "invalid dependency mode")
        require(SHA.fullmatch(dep["sha"]), "exact dependency SHA required")
    return task


def specialists(task):
    validate(task)
    limit = {"R0": 0, "R1": 1, "R2": 2, "R3": 2}[task["risk"]]
    priority = ("security-auditor", "postgres-auditor", "backend-reviewer",
                "frontend-reviewer", "test-engineer", "devops-reviewer")
    relevant = {ROUTES[k] for k in task["changes"] if ROUTES[k]}
    roles = [role for role in priority if role in relevant]
    return roles[:limit]


def review_required(task):
    return task["risk"] == "R3" or bool(set(task["changes"]) & MANDATORY)


def verified(task, kind):
    evidence = task.get("evidence", {}).get(kind, {})
    return (bool(task.get("candidate_sha")) and evidence.get("sha") == task["candidate_sha"]
            and evidence.get("result") == "PASS" and bool(evidence.get("reference")))


def delivery_gates(task, include_ci=True):
    validate(task)
    require(SHA.fullmatch(task.get("candidate_sha", "")), "candidate SHA required")
    require(not task.get("blockers"), "unresolved blockers")
    require(bool(task.get("writer")), "writer identity required")
    require(verified(task, "tests"), "focused test evidence missing or stale")
    if review_required(task):
        require(verified(task, "review"), "mandatory independent review missing or stale")
        review = task["evidence"]["review"]
        require(review.get("reviewer") and review["reviewer"] != task["writer"],
                "writer cannot independently review itself")
        require(review.get("separate_context") is True, "separate review context required")
    if task["risk"] == "R3":
        require(verified(task, "operational"), "R3 operational evidence missing or stale")
    if include_ci:
        require(verified(task, "ci"), "CI evidence missing or stale")


def select(backlog, active_contexts=()):
    tasks = [validate(t) for t in backlog]
    by_id = {t["id"]: t for t in tasks}
    require(len(by_id) == len(tasks), "duplicate task id")
    eligible = []
    for task in tasks:
        if (not task["authorization"] or task["state"] not in ("AUTHORIZED", "READY")
                or task.get("writer") or task["context"] in active_contexts
                or task.get("candidate_sha") or task.get("blockers")):
            continue
        ready = True
        for dep in task["dependencies"]:
            previous = by_id.get(dep["id"])
            if not previous:
                ready = False
                break
            if dep["mode"] == "integrated":
                ready &= (previous["state"] == "INTEGRATED"
                          and previous.get("integrated_sha") == dep["sha"])
            else:
                try:
                    delivery_gates(previous)
                except ValueError:
                    ready = False
                ready &= (previous["state"] in ("DRAFT_PR_READY", "MERGE_AUTHORIZED")
                          and previous.get("candidate_sha") == dep["sha"]
                          and task["base_sha"] == dep["sha"]
                          and task["base_branch"] == previous["branch"])
        if ready:
            eligible.append(task)
    return min(eligible, key=lambda t: (t["priority"], t["id"])) if eligible else None


def ownership_dir(root):
    # All worktrees sharing this Git common directory see the same claims.
    return Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "homies-delivery"


def claim_path(root, task):
    validate(task)
    return ownership_dir(root) / (task["context"] + ".json")


def checkpoint_path(root, task):
    return ownership_dir(root) / (task["context"] + "." + task["id"] + ".checkpoint.json")


def acquire(root, task, owner, backlog=None):
    validate(task)
    active = [p.stem for p in ownership_dir(root).glob("*.json")
              if not p.name.endswith(".checkpoint.json")]
    selected = select(backlog if backlog is not None else [task], active)
    require(selected == task, "task is not next authorized unblocked work")
    require(task["authorization"], "explicit authorization required")
    require(task["state"] in ("AUTHORIZED", "READY"), "task not ready for new writer")
    require(not task.get("writer") and not task.get("candidate_sha"), "resume existing work")
    require(not task.get("blockers"), "unresolved blockers")
    require(owner and NAME.fullmatch(owner), "named owner required")
    require(git(root, "branch", "--show-current") == task["branch"], "wrong writer branch")
    require(git(root, "rev-parse", "HEAD") == task["base_sha"], "writer must start at exact base")
    require(not git(root, "status", "--porcelain"), "writer worktree must start clean")
    contract = Path(root) / task["contract"]
    require(contract.is_file(), "contract unavailable")
    path = claim_path(root, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"task": task["id"], "context": task["context"], "owner": owner,
              "worktree": str(Path(root).resolve()), "branch": task["branch"],
              "base_sha": task["base_sha"], "contract": task["contract"],
              "contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest()}
    # O_EXCL arbitrates contenders, including separate processes/worktrees. A partial
    # write left by interruption remains a blocking claim; never auto-steal or expire.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    return record


def owned(root, task, owner):
    record = json.loads(claim_path(root, task).read_text(encoding="utf-8"))
    require(record["owner"] == owner and record["task"] == task["id"], "different active owner/task")
    require(record["worktree"] == str(Path(root).resolve()), "different writer worktree")
    require(record["branch"] == git(root, "branch", "--show-current"), "writer branch changed")
    require(record["base_sha"] == task["base_sha"], "base changed")
    contract = Path(root) / record["contract"]
    require(record["contract"] == task["contract"] and
            record["contract_sha256"] == hashlib.sha256(contract.read_bytes()).hexdigest(),
            "contract changed; explicit owner reconciliation required")
    return record


@contextmanager
def owner_operation(root, task, owner):
    path = claim_path(root, task).with_suffix(".busy")
    with path.open("x", encoding="utf-8"):
        pass
    try:
        owned(root, task, owner)
        yield
    finally:
        path.unlink()


def checkpoint(root, task, owner):
    validate(task)
    require(task.get("writer") == owner, "checkpoint writer differs from owner")
    head = git(root, "rev-parse", "HEAD")
    require(task.get("candidate_sha", head) == head, "candidate differs from worktree HEAD")
    require(not git(root, "status", "--porcelain"), "commit changes before durable checkpoint")
    if task["state"] in ("BUILDER_VERIFIED", "REVIEW_REQUIRED", "REVIEWED"):
        require(verified(task, "tests"), "focused test evidence missing or stale")
    if task["state"] == "REVIEWED":
        delivery_gates(task, include_ci=False)
    if task["state"] in ("CI_GREEN", "DRAFT_PR_READY", "MERGE_AUTHORIZED", "INTEGRATED"):
        delivery_gates(task)
    if task["state"] in ("MERGE_AUTHORIZED", "INTEGRATED"):
        require(task.get("merge_authorization", {}).get("sha") == head and
                task["merge_authorization"].get("reference"), "exact founder merge authorization required")
    if task["state"] == "INTEGRATED":
        require(task.get("integrated_sha") and task.get("integration_reference"), "integration evidence required")
    require(set(task.get("metrics", {})) <= METRICS, "unknown metric; no transcript payloads")
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
                for v in task.get("metrics", {}).values()), "metrics must be measured nonnegative numbers")
    # Explicit field allowlist excludes arbitrary hook events and transcripts.
    keys = {"id", "context", "contract", "authorization", "base_sha", "base_branch", "branch",
            "risk", "changes", "state", "priority", "dependencies", "writer", "candidate_sha",
            "evidence", "blockers", "next", "metrics", "merge_authorization", "integrated_sha",
            "integration_reference"}
    data = {k: v for k, v in task.items() if k in keys}
    data.update(head=head, tree=git(root, "rev-parse", "HEAD^{tree}"))
    content = json.dumps(data, indent=2)
    require(len(content.encode()) <= 32768, "checkpoint exceeds 32 KiB; use evidence references")
    with owner_operation(root, task, owner):
        path = checkpoint_path(root, task)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = stream.name
        os.replace(temporary, path)
    return data


def resume(root, task, owner):
    start = time.perf_counter()
    with owner_operation(root, task, owner):
        data = json.loads(checkpoint_path(root, task).read_text(encoding="utf-8"))
        require(data["head"] == git(root, "rev-parse", "HEAD"), "HEAD changed; reconcile, do not restart")
        require(data["tree"] == git(root, "rev-parse", "HEAD^{tree}"), "tree changed")
        require(not git(root, "status", "--porcelain"), "dirty worktree; preserve and reconcile")
    require(data["id"] == task["id"] and data["writer"] == owner, "checkpoint identity differs")
    return {"checkpoint": data, "recovery_ms": round((time.perf_counter() - start) * 1000, 2)}


def draft_payload(task):
    delivery_gates(task, include_ci=task["state"] in ("CI_GREEN", "DRAFT_PR_READY"))
    require(task["state"] in ("BUILDER_VERIFIED", "REVIEWED", "CI_GREEN", "DRAFT_PR_READY"), "not ready for Draft preparation")
    return {"title": task["id"] + ": " + task["context"], "head": task["branch"],
            "base": task["base_branch"], "draft": True,
            "body": "Contract: " + task["contract"] + "\nCandidate: " + task["candidate_sha"] +
                    "\nBase: " + task["base_sha"] + "\nFounder merge decision required. No deployment.\n" +
                    ("CI pending: Draft opened to trigger pull_request checks.\n"
                     if not verified(task, "ci") else "CI: " + task["evidence"]["ci"]["reference"] + "\n") +
                    ("Stacked dependency; not independently mergeable to main.\n"
                     if task["base_branch"] != "main" else "")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "claim", "checkpoint", "resume", "release", "draft"))
    parser.add_argument("input", type=Path, help="JSON backlog (plan) or task record")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--owner", default="")
    parser.add_argument("--backlog", type=Path, help="approved full backlog when claiming a dependent task")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if args.action == "plan":
        directory = ownership_dir(args.root)
        active = [p.stem for p in directory.glob("*.json") if not p.name.endswith(".checkpoint.json")]
        task = select(data, active)
        result = {"task": task, "specialists": specialists(task) if task else [],
                  "independent_review_required": review_required(task) if task else False}
    elif args.action == "claim":
        backlog = json.loads(args.backlog.read_text(encoding="utf-8-sig")) if args.backlog else None
        result = acquire(args.root, data, args.owner, backlog)
    elif args.action == "checkpoint":
        result = checkpoint(args.root, data, args.owner)
    elif args.action == "resume":
        result = resume(args.root, data, args.owner)
    elif args.action == "draft":
        result = draft_payload(data)
    else:
        with owner_operation(args.root, data, args.owner):
            claim_path(args.root, data).unlink()
        result = {"released": data["id"]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
