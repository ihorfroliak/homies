"""Release manifest, schema lineage and the compatibility decision (PR-002).

Two questions are answered here, separately, and always fail closed:

1. **Can this build run against this database schema?** (schema compatibility)
   `evaluate()` compares the database's Alembic revision with this build's
   declared range. Alembic revisions are graph nodes, not versions, so the
   comparison walks ancestry — the build's own migration scripts for
   revisions it knows, and the database's `schema_lineage` table for newer
   revisions it cannot know. Revision ids are never compared as strings, and
   neither their length nor the order in which steps are listed matters.

2. **May the previous release be restored?** (release rollback safety,
   `rollback_to_previous`)
   Declared explicitly per release in the manifest: SAFE or BLOCKED. It is
   *not* inferred from "the migration was additive", "a downgrade exists" or
   "the old image starts". Missing or unknown values are invalid, never SAFE.

Vocabulary (docs/production/RELEASE-AND-MIGRATION.md):

* per migration step — `schema_transition` EXPAND | BARRIER, and
  `rollback_to_previous` SAFE | BLOCKED (may the release before this step keep
  running on / return to the schema after it);
* per release — `schema_transition` EXPAND | BARRIER | NO_SCHEMA_CHANGE
  (aggregate of the steps since the previous release) and
  `rollback_to_previous` SAFE | BLOCKED.

The build's range is a pair of **lineage boundaries**, not a numeric or string
interval: `minimum_schema` (the oldest revision it runs on — an ancestor of or
equal to its head) and `maximum_schema` (its own head — the newest revision it
contains). A database revision is inside the range when minimum_schema is one
of its ancestors and it is one of the head's ancestors. A database *beyond*
the maximum is accepted only through lineage steps each recorded EXPAND
**and** SAFE; anything else is TOO_NEW.

The migration history is a single chain. A merge revision (two parents) is
refused where the build's graph is read (`graph_from_scripts`) and where the
lineage is recorded (alembic/env.py): the decision never guesses across one.

Two kinds of release data, kept apart:

* the **release compatibility policy** — `app/release.json`, committed with the
  code: schema head, lineage boundaries, transition, rollback policy, manifest
  version. It cannot contain the commit id of the commit that contains it
  (changing that field would change the commit), so it does not try;
* the **build identity** — the commit the image was built from, injected by the
  build (`HOMIES_BUILD_SHA`, from the Docker build argument `GIT_SHA`, also the
  OCI label `org.opencontainers.image.revision`). `RuntimeReleaseIdentity`
  combines the two at runtime. It goes to logs and deploy tooling, never to
  the public /metrics endpoint.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "release.json"
MANIFEST_VERSION = 1
BUILD_SHA_ENV = "HOMIES_BUILD_SHA"
# The migration that creates schema_lineage. A database at or beyond it must
# carry a matching lineage; only one before it may lack the table.
LINEAGE_REVISION = "0c4e6a8b2d91"
# Environments that may run without an injected build identity (a developer's
# checkout, the test suite, CI's test jobs). Everywhere else it is required.
DEVELOPMENT_ENVIRONMENTS = frozenset({"local", "test", "ci"})

EXPAND, BARRIER, NO_SCHEMA_CHANGE = "EXPAND", "BARRIER", "NO_SCHEMA_CHANGE"
SAFE, BLOCKED = "SAFE", "BLOCKED"
STEP_TRANSITIONS = frozenset({EXPAND, BARRIER})
RELEASE_TRANSITIONS = frozenset({EXPAND, BARRIER, NO_SCHEMA_CHANGE})
ROLLBACK_VALUES = frozenset({SAFE, BLOCKED})

_REVISION = re.compile(r"[0-9a-f]{12}")
_BUILD_SHA = re.compile(r"[0-9a-f]{40}")
# A lineage walk longer than this is treated as divergent: real releases move a
# handful of revisions at a time; an unbounded walk would hide a cycle.
MAX_LINEAGE_STEPS = 500

# Decisions. ALLOWED ones start the application; every other one refuses.
EXACT = "EXACT"
BEHIND_SUPPORTED = "BEHIND_SUPPORTED"
AHEAD_COMPATIBLE = "AHEAD_COMPATIBLE"
ALLOWED = frozenset({EXACT, BEHIND_SUPPORTED, AHEAD_COMPATIBLE})
UNMIGRATED = "UNMIGRATED"
MULTIPLE_DB_HEADS = "MULTIPLE_DB_HEADS"
TOO_OLD = "TOO_OLD"
TOO_NEW = "TOO_NEW"
UNKNOWN_SCHEMA = "UNKNOWN_SCHEMA"
DIVERGENT = "DIVERGENT"
LINEAGE_MISSING = "LINEAGE_MISSING"
LINEAGE_MISMATCH = "LINEAGE_MISMATCH"


class ReleaseManifestError(ValueError):
    """The release manifest is missing, malformed or inconsistent with the
    migrations this build carries. Never treated as compatible."""


class BuildIdentityError(ReleaseManifestError):
    """The injected build identity is malformed, or missing where it is required."""


@dataclass(frozen=True)
class Step:
    """One migration step: the revision, its parent, and its declarations."""

    revision: str
    down_revision: str | None
    schema_transition: str
    rollback_to_previous: str


@dataclass(frozen=True)
class ReleaseManifest:
    """The committed release compatibility policy (app/release.json)."""

    release: str
    schema_head: str
    minimum_schema: str
    maximum_schema: str
    schema_transition: str
    rollback_to_previous: str
    rollback_note: str
    previous_release: str
    previous_schema_head: str

    def rollback_allowed(self) -> bool:
        """True only for an explicit SAFE; anything else is not a rollback promise."""
        return self.rollback_to_previous == SAFE

    def as_dict(self) -> dict:
        return {
            "manifest_version": MANIFEST_VERSION,
            "release": self.release,
            "schema_head": self.schema_head,
            "minimum_schema": self.minimum_schema,
            "maximum_schema": self.maximum_schema,
            "schema_transition": self.schema_transition,
            "rollback_to_previous": self.rollback_to_previous,
            "rollback_note": self.rollback_note,
            "previous_release": {"id": self.previous_release,
                                 "schema_head": self.previous_schema_head},
        }


@dataclass(frozen=True)
class RuntimeReleaseIdentity:
    """The committed policy plus the build identity injected at build time.

    `build_sha` is None only where identity is not required (development);
    `runtime_identity(required=True)` never returns one without it.
    """

    manifest: ReleaseManifest
    build_sha: str | None

    def as_dict(self) -> dict:
        return {**self.manifest.as_dict(), "build_sha": self.build_sha}


@dataclass(frozen=True)
class Decision:
    code: str
    db_revision: str | None
    detail: str = ""
    steps_ahead: int = 0

    @property
    def allowed(self) -> bool:
        return self.code in ALLOWED


# --- the build's own migration graph ---------------------------------------------------------


class Graph:
    """The migration steps this build carries: revision → Step.

    Built from Alembic's script directory in production code
    (`graph_from_scripts`), or from plain Steps in tests. `lineage_revision`
    is the step that creates schema_lineage, when the graph contains it.
    """

    def __init__(self, steps: Iterable[Step], lineage_revision: str | None = None):
        self.steps: dict[str, Step] = {s.revision: s for s in steps}
        heads = set(self.steps) - {s.down_revision for s in self.steps.values()}
        if len(heads) != 1:
            raise ReleaseManifestError(f"the build carries {len(heads)} migration heads, not 1")
        (self.head,) = heads
        self.lineage_revision = lineage_revision if lineage_revision in self.steps else None

    def knows(self, revision: str) -> bool:
        return revision in self.steps

    def ancestors(self, revision: str) -> list[str]:
        """revision's ancestry, itself first, following parents to the root."""
        chain: list[str] = []
        seen: set[str] = set()
        current: str | None = revision
        while current is not None:
            if current in seen or current not in self.steps:
                raise ReleaseManifestError(f"broken migration ancestry at {current}")
            seen.add(current)
            chain.append(current)
            current = self.steps[current].down_revision
        return chain

    def is_ancestor_or_equal(self, older: str, newer: str) -> bool:
        return older in self.ancestors(newer)

    def between(self, older: str, newer: str) -> list[Step]:
        """The steps applied to go from `older` to `newer` (newer first)."""
        chain = self.ancestors(newer)
        if older not in chain:
            raise ReleaseManifestError(f"{older} is not an ancestor of {newer}")
        return [self.steps[r] for r in chain[: chain.index(older)]]

    def expects_lineage(self, revision: str) -> bool:
        """Must a database at `revision` (known to this build) carry schema_lineage?"""
        return (self.lineage_revision is not None
                and self.is_ancestor_or_equal(self.lineage_revision, revision))


def step_declarations(module, historical: Mapping[str, tuple[str, str]]) -> tuple[str, str]:
    """(schema_transition, rollback_to_previous) of one migration module.

    Migrations written since PR-002 declare both as module attributes;
    earlier ones are classified in the PR-002 lineage migration's registry.
    A migration with neither is an error, never a default.
    """
    transition = getattr(module, "schema_transition", None)
    rollback = getattr(module, "rollback_to_previous", None)
    if transition is None and rollback is None and module.revision in historical:
        transition, rollback = historical[module.revision]
    return validate_step_declaration(module.revision, transition, rollback)


def validate_step_declaration(revision: str, transition, rollback) -> tuple[str, str]:
    if transition not in STEP_TRANSITIONS:
        raise ReleaseManifestError(f"migration {revision}: schema_transition must be "
                                   f"EXPAND or BARRIER, not {transition!r}")
    if rollback not in ROLLBACK_VALUES:
        raise ReleaseManifestError(f"migration {revision}: rollback_to_previous must be "
                                   f"SAFE or BLOCKED, not {rollback!r}")
    if transition == BARRIER and rollback == SAFE:
        raise ReleaseManifestError(f"migration {revision}: a BARRIER cannot be rollback SAFE")
    return transition, rollback


def graph_from_scripts(script_directory) -> Graph:
    """The build's Graph, from an Alembic ScriptDirectory."""
    from app.core.lineage_registry import HISTORICAL

    steps = []
    for script in script_directory.walk_revisions():
        down = script.down_revision
        if isinstance(down, (tuple, list)):
            raise ReleaseManifestError(f"merge revision {script.revision} is not supported")
        transition, rollback = step_declarations(script.module, HISTORICAL)
        steps.append(Step(script.revision, down, transition, rollback))
    return Graph(steps, lineage_revision=LINEAGE_REVISION)


# --- the release manifest (committed policy) --------------------------------------------------

_KEYS = {"manifest_version", "release", "schema_head", "minimum_schema", "maximum_schema",
         "schema_transition", "rollback_to_previous", "rollback_note", "previous_release"}


def parse_manifest(raw: str, graph: Graph) -> ReleaseManifest:
    """Validate the committed manifest against the build's migrations.

    Strict: unknown or missing keys, wrong types, revisions the build does not
    carry, a range that is not an ancestry, or declarations that contradict
    the migrations since the previous release are all errors.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseManifestError(f"the release manifest is not JSON ({exc.msg})") from None
    if not isinstance(data, dict) or set(data) != _KEYS:
        found = sorted(data) if isinstance(data, dict) else type(data).__name__
        raise ReleaseManifestError(f"the release manifest keys must be exactly {sorted(_KEYS)}, "
                                   f"found {found}")
    if data["manifest_version"] != MANIFEST_VERSION:
        raise ReleaseManifestError(f"unsupported manifest_version {data['manifest_version']!r}")
    previous = data["previous_release"]
    if not isinstance(previous, dict) or set(previous) != {"id", "schema_head"}:
        raise ReleaseManifestError("previous_release must be {id, schema_head}")
    for key in ("release", "rollback_note"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ReleaseManifestError(f"{key} must be a non-empty string")
    if not isinstance(previous["id"], str) or not previous["id"].strip():
        raise ReleaseManifestError("previous_release.id must be a non-empty string")
    for key, value in (("schema_head", data["schema_head"]),
                       ("minimum_schema", data["minimum_schema"]),
                       ("maximum_schema", data["maximum_schema"]),
                       ("previous_release.schema_head", previous["schema_head"])):
        if not isinstance(value, str) or not _REVISION.fullmatch(value):
            raise ReleaseManifestError(f"{key} must be a 12-character revision id")
        if not graph.knows(value):
            raise ReleaseManifestError(f"{key} {value} is not a revision this build carries")
    head = data["schema_head"]
    if head != graph.head:
        raise ReleaseManifestError(f"schema_head {head} is not the build's migration head "
                                   f"{graph.head}")
    if data["maximum_schema"] != head:
        raise ReleaseManifestError("maximum_schema must be the build's head: newer revisions "
                                   "are admitted only through EXPAND/SAFE lineage steps")
    if not graph.is_ancestor_or_equal(data["minimum_schema"], head):
        raise ReleaseManifestError("minimum_schema is not an ancestor of schema_head")
    if not graph.is_ancestor_or_equal(previous["schema_head"], head):
        raise ReleaseManifestError("previous_release.schema_head is not an ancestor of "
                                   "schema_head")

    transition, rollback = data["schema_transition"], data["rollback_to_previous"]
    if transition not in RELEASE_TRANSITIONS:
        raise ReleaseManifestError("schema_transition must be EXPAND, BARRIER or "
                                   "NO_SCHEMA_CHANGE")
    if rollback not in ROLLBACK_VALUES:
        raise ReleaseManifestError("rollback_to_previous must be SAFE or BLOCKED")
    steps = graph.between(previous["schema_head"], head)
    expected = (NO_SCHEMA_CHANGE if not steps
                else BARRIER if any(s.schema_transition == BARRIER for s in steps)
                else EXPAND)
    if transition != expected:
        raise ReleaseManifestError(f"schema_transition {transition} contradicts the migrations "
                                   f"since {previous['schema_head']} ({expected})")
    if rollback == SAFE and any(s.rollback_to_previous == BLOCKED for s in steps):
        raise ReleaseManifestError("rollback_to_previous SAFE contradicts a migration since the "
                                   "previous release that declares BLOCKED")
    return ReleaseManifest(
        release=data["release"], schema_head=head,
        minimum_schema=data["minimum_schema"], maximum_schema=data["maximum_schema"],
        schema_transition=transition, rollback_to_previous=rollback,
        rollback_note=data["rollback_note"], previous_release=previous["id"],
        previous_schema_head=previous["schema_head"])


def load_manifest(graph: Graph, path: Path = MANIFEST_PATH) -> ReleaseManifest:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raise ReleaseManifestError("the release manifest is missing from this build") from None
    return parse_manifest(raw, graph)


# --- the build identity (injected, never committed) -------------------------------------------


def identity_required(env: str) -> bool:
    return env not in DEVELOPMENT_ENVIRONMENTS


def build_identity(*, required: bool) -> str | None:
    """The commit this image was built from (HOMIES_BUILD_SHA).

    A present value must be a full 40-character lowercase hex commit id —
    placeholders such as "unknown" or a short id are malformed, always an
    error. Absent: an error when `required`, otherwise None.
    """
    value = os.environ.get(BUILD_SHA_ENV, "").strip()
    if not value:
        if required:
            raise BuildIdentityError(f"{BUILD_SHA_ENV} is required here: build the image with "
                                     "--build-arg GIT_SHA=<commit>")
        return None
    if not _BUILD_SHA.fullmatch(value):
        raise BuildIdentityError(f"{BUILD_SHA_ENV} must be a 40-character hex commit id")
    return value


def runtime_identity(manifest: ReleaseManifest, *, required: bool) -> RuntimeReleaseIdentity:
    return RuntimeReleaseIdentity(manifest, build_identity(required=required))


# --- the compatibility decision ---------------------------------------------------------------


def _lineage_problem(graph: Graph, revision: str,
                     lineage: Mapping[str, Step] | None) -> Decision | None:
    """A database at or beyond the lineage migration must carry the lineage the
    build's own migrations describe. Its absence is never repaired here: the
    application does not fabricate lineage; the migration job records it."""
    if not graph.expects_lineage(revision):
        return None
    if lineage is None:
        return Decision(LINEAGE_MISSING, revision,
                        "schema_lineage is absent but the schema includes its migration")
    for r in graph.ancestors(revision):
        if lineage.get(r) != graph.steps[r]:
            return Decision(LINEAGE_MISMATCH, revision,
                            f"schema_lineage disagrees with migration {r}")
    return None


def evaluate(manifest: ReleaseManifest, graph: Graph, db_heads: Iterable[str],
             lineage: Mapping[str, Step] | None) -> Decision:
    """May this build run against a database at `db_heads`?

    `lineage` is the database's schema_lineage (revision → Step), or None
    when the table does not exist. Pure: no I/O.
    """
    heads = list(db_heads)
    if not heads:
        return Decision(UNMIGRATED, None, "the database has no Alembic revision")
    if len(heads) > 1:
        return Decision(MULTIPLE_DB_HEADS, None, f"{len(heads)} Alembic revisions recorded")
    (db,) = heads
    head = manifest.schema_head

    if graph.knows(db):
        if not graph.is_ancestor_or_equal(db, head):
            return Decision(DIVERGENT, db, "a revision this build carries but does not descend to")
        problem = _lineage_problem(graph, db, lineage)
        if problem is not None:
            return problem
        if db == head:
            return Decision(EXACT, db)
        if graph.is_ancestor_or_equal(manifest.minimum_schema, db):
            return Decision(BEHIND_SUPPORTED, db)
        return Decision(TOO_OLD, db, f"older than minimum_schema {manifest.minimum_schema}")

    # Newer than this build: only the database can describe the way back.
    if lineage is None:
        return Decision(UNKNOWN_SCHEMA, db, "unknown revision and no schema_lineage")
    current, seen, steps = db, set(), 0
    while True:
        step = lineage.get(current)
        if step is None:
            return Decision(UNKNOWN_SCHEMA, db, f"revision {current} is not in schema_lineage")
        if step.schema_transition != EXPAND or step.rollback_to_previous != SAFE:
            return Decision(TOO_NEW, db, f"step {current} is {step.schema_transition}/"
                                         f"{step.rollback_to_previous}")
        steps += 1
        parent = step.down_revision
        if parent == head:
            problem = _lineage_problem(graph, head, lineage)
            if problem is not None:
                return Decision(problem.code, db, problem.detail)
            return Decision(AHEAD_COMPATIBLE, db, steps_ahead=steps)
        if parent is None or graph.knows(parent) or parent in seen or steps >= MAX_LINEAGE_STEPS:
            return Decision(DIVERGENT, db, "the lineage does not lead back to this build's head")
        seen.add(current)
        current = parent
