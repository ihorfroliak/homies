"""Bounded AGENT-001 checks. Requires Python 3.11+, PyYAML and Windows PowerShell.

Run: python docs/engineering/agent001_checks.py [--static-only]
Uses only temporary synthetic Git/transcript fixtures; never reads real archives.
No provider calls, installs, production databases or repository writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = "be150da11b9838409fcf8ee2d8ca4bd8b0311307"
ROLES = ("backend-reviewer", "postgres-auditor", "security-auditor",
         "frontend-reviewer", "test-engineer", "devops-reviewer")


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          encoding="utf-8", timeout=30, **kwargs).stdout.strip()


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---", 2)[1])


def static_checks():
    cfg = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    assert cfg["agents"]["enabled"] is True
    assert cfg["agents"]["max_concurrent_threads_per_session"] == 2
    assert len(list((ROOT / ".claude/agents").glob("*.md"))) == 6
    assert len(list((ROOT / ".codex/agents").glob("*.toml"))) == 6
    for role in ROLES:
        fm = frontmatter(ROOT / f".claude/agents/{role}.md")
        assert fm["name"] == role and isinstance(fm["description"], str)
        assert {x.strip() for x in fm["tools"].split(",")} == {"Read", "Grep", "Glob"}
        assert fm["permissionMode"] == "plan" and fm["maxTurns"] == 12
        cfg = tomllib.loads((ROOT / f".codex/agents/{role}.toml").read_text(encoding="utf-8"))
        assert cfg["name"] == role.replace("-", "_")
        assert cfg["sandbox_mode"] == "read-only"
        assert len(cfg["description"]) > 30 and len(cfg["developer_instructions"]) > 150
    for role in ("micro-cycle", "security-probe", "money-invariants"):
        fm = frontmatter(ROOT / f".claude/skills/{role}/SKILL.md")
        assert fm["name"] == role and isinstance(fm["description"], str)
    for rel in (".claude/settings.json", ".claude/hooks/context-session-start.ps1",
                ".claude/rules/context-survival.md", ".claude/skills/money-invariants/SKILL.md"):
        current = run(["git", "-C", str(ROOT), "hash-object", "--path", rel, rel])
        baseline = run(["git", "-C", str(ROOT), "rev-parse", BASE + ":" + rel])
        assert current == baseline, "unrelated file changed: " + rel
    for name in ("AGENTS.md", "CLAUDE.md"):
        old = run(["git", "-C", str(ROOT), "show", BASE + ":" + name])
        new = (ROOT / name).read_text(encoding="utf-8")
        assert new.startswith(old), "original governance changed: " + name
        assert new.count("<!-- AGENT-001:BEGIN -->") == new.count("<!-- AGENT-001:END -->") == 1
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "80"
    assert (ROOT / ".github/copilot-instructions.md").is_file()
    allowed = {"AGENTS.md", "CLAUDE.md", ".codex/config.toml", ".github/copilot-instructions.md",
               ".claude/skills/micro-cycle/SKILL.md", ".claude/skills/security-probe/SKILL.md",
               ".claude/hooks/context-pre-compact.ps1", ".claude/hooks/context-post-compact.ps1",
               "docs/DEVLOG.md", "docs/tasks/AGENT-001-agent-foundation.md",
               "docs/engineering/agent001_checks.py"}
    allowed.update(f".claude/agents/{role}.md" for role in ROLES)
    allowed.update(f".codex/agents/{role}.toml" for role in ROLES)
    allowed.update("docs/engineering/" + f + ".md" for f in
                   ("AGENT-001-AUDIT", "AGENT-OPERATING-MODEL", "CHATGPT-COPILOT-INTEROP", "CONTEXT-AND-CACHE"))
    changed = set(run(["git", "-C", str(ROOT), "diff", "--name-only", BASE]).splitlines())
    changed.update(run(["git", "-C", str(ROOT), "ls-files", "--others", "--exclude-standard"]).splitlines())
    assert changed <= allowed, "out-of-scope paths: " + repr(changed - allowed)
    run(["git", "-C", str(ROOT), "diff", "--check", BASE])
    print("STATIC VERIFIED: 6 Claude + 6 Codex; YAML/TOML; preserved governance/settings; allowed diff")


def hook_checks():
    powershell = shutil.which("powershell.exe")
    assert powershell, "Windows PowerShell required; use --static-only elsewhere"
    hooks = ROOT / ".claude/hooks"
    # Parse every existing hook using the same engine configured in settings.json.
    for script in hooks.glob("*.ps1"):
        command = "$e=$null; $t=$null; [System.Management.Automation.Language.Parser]::ParseFile('" + str(script).replace("'", "''") + "',[ref]$t,[ref]$e) | Out-Null; if ($e.Count) { $e | Out-String | Write-Output; exit 1 }"
        run([powershell, "-NoProfile", "-Command", command])
    metrics = []
    with tempfile.TemporaryDirectory(prefix="homies-agent001-synthetic-") as td:
        temp = Path(td)
        repo = temp / "repo"
        repo.mkdir()
        run(["git", "init", "-q", str(repo)])
        run(["git", "-C", str(repo), "-c", "user.name=Synthetic AGENT-001", "-c",
             "user.email=agent001@example.invalid", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "synthetic fixture"])
        head = run(["git", "-C", str(repo), "rev-parse", "HEAD"])
        branch = run(["git", "-C", str(repo), "branch", "--show-current"])
        checkpoint = temp / "CHECKPOINT.md"
        checkpoint.write_text("TASK: SYNTHETIC\nHEAD: " + head + "\nNEXT: finish synthetic probe\n", encoding="utf-8")
        transcript = temp / "synthetic.jsonl"
        transcript.write_text(json.dumps({"fake_transcript_marker": "SYNTHETIC_PRIVATE_" + "x" * 2048}), encoding="utf-8")
        large = temp / "large.jsonl"
        with large.open("wb") as f:
            f.truncate(20 * 1024 * 1024 + 1)
        env = os.environ.copy()
        for key in ("HOMIES_ARCHIVE_FULL_TRANSCRIPT", "HOMIES_ARCHIVE_COMPACT_SUMMARY"):
            env.pop(key, None)
        env.update(HOMIES_WORKTREE=str(repo), HOMIES_CHECKPOINT=str(checkpoint))
        payload = {"session_id": "synthetic-agent001", "cwd": str(temp / "wrong-cwd"),
                   "transcript_path": str(transcript), "trigger": "manual", "source": "compact",
                   "compact_summary": "SYNTHETIC_PRIVATE_SUMMARY", "extra_private_field": "SYNTHETIC_EXTRA"}

        def invoke(name, scenario, data, options=None):
            archive = temp / scenario
            archive.mkdir(exist_ok=True)
            e = dict(env, HOMIES_CONTEXT_ARCHIVE=str(archive), **(options or {}))
            start = time.perf_counter()
            output = run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(hooks / name)], input=json.dumps(data), env=e)
            elapsed = round((time.perf_counter() - start) * 1000)
            metrics.append({"case": scenario + ":" + name, "ms": elapsed,
                            "archive_bytes": sum(p.stat().st_size for p in archive.iterdir() if p.is_file())})
            return archive, output

        archive, _ = invoke("context-pre-compact.ps1", "default", payload)
        record = json.loads(next(archive.glob("*-precompact.json")).read_text(encoding="utf-8-sig"))
        assert record["head"] == head and record["branch"] == branch, record
        assert record["checkpoint_path"] == str(checkpoint)
        assert not record["transcript_copy"] and not record["transcript_sha256"]
        assert not list(archive.glob("*-transcript.jsonl"))
        archive, _ = invoke("context-post-compact.ps1", "default", payload)
        record = json.loads(next(archive.glob("*-postcompact.json")).read_text(encoding="utf-8-sig"))
        assert "hook_input" not in record and not record["summary_file"]
        assert not list(archive.glob("*-summary.md"))
        assert all("SYNTHETIC_PRIVATE" not in p.read_text(encoding="utf-8-sig") and
                   "SYNTHETIC_EXTRA" not in p.read_text(encoding="utf-8-sig") for p in archive.iterdir())
        _, output = invoke("context-session-start.ps1", "default", payload)
        context = json.loads(output.lstrip("\ufeff"))["hookSpecificOutput"]["additionalContext"]
        assert head in context and str(checkpoint) in context and "wrong-cwd" not in context
        archive, _ = invoke("context-pre-compact.ps1", "opt-in-small", payload, {"HOMIES_ARCHIVE_FULL_TRANSCRIPT": "1"})
        record = json.loads(next(archive.glob("*-precompact.json")).read_text(encoding="utf-8-sig"))
        assert Path(record["transcript_copy"]).read_bytes() == transcript.read_bytes()
        assert record["transcript_sha256"] == hashlib.sha256(transcript.read_bytes()).hexdigest(), record
        archive, _ = invoke("context-pre-compact.ps1", "opt-in-too-large", dict(payload, transcript_path=str(large)), {"HOMIES_ARCHIVE_FULL_TRANSCRIPT": "1"})
        record = json.loads(next(archive.glob("*-precompact.json")).read_text(encoding="utf-8-sig"))
        assert not record["transcript_copy"] and not record["transcript_sha256"]
        assert not list(archive.glob("*-transcript.jsonl"))
        archive, _ = invoke("context-post-compact.ps1", "opt-in-summary", payload, {"HOMIES_ARCHIVE_COMPACT_SUMMARY": "1"})
        assert "SYNTHETIC_PRIVATE_SUMMARY" in next(archive.glob("*-summary.md")).read_text(encoding="utf-8-sig")
        archive, _ = invoke("context-post-compact.ps1", "opt-in-summary-limit", dict(payload, compact_summary="x" * 16385), {"HOMIES_ARCHIVE_COMPACT_SUMMARY": "1"})
        assert not list(archive.glob("*-summary.md"))
        assert "x" * 100 not in next(archive.glob("*-postcompact.json")).read_text(encoding="utf-8-sig")
        # A distinct task's fresh archive must not inherit the first task's pointer.
        _, output = invoke("context-session-start.ps1", "second-task-empty", dict(payload, source="resume"))
        context = json.loads(output.lstrip("\ufeff"))["hookSpecificOutput"]["additionalContext"]
        assert "Latest compact archive: (none)" in context and head in context
        assert not run(["git", "-C", str(repo), "status", "--porcelain"])
        assert run(["git", "-C", str(repo), "rev-parse", "HEAD"]) == head
    print("RUNTIME VERIFIED: Windows synthetic hook privacy, bounds, correct SHA/checkpoint, isolated archive")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    static_checks()
    if not args.static_only:
        hook_checks()
