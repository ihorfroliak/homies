"""The compatibility decision (PR-002): pure, graph-aware, fail-closed.

Synthetic graphs whose revision ids sort *against* their ancestry prove the
decision follows lineage, never string order, id length or the order steps are
listed in. The real migration chain is checked too: its new head
`0c4e6a8b2d91` sorts before every older revision. `minimum_schema` /
`maximum_schema` are lineage boundaries, not an interval of strings.
"""

import json
import random
from types import SimpleNamespace

import pytest
from alembic.script import ScriptDirectory

from app.core import release
from app.core.release import (
    AHEAD_COMPATIBLE,
    BEHIND_SUPPORTED,
    DIVERGENT,
    EXACT,
    LINEAGE_MISMATCH,
    LINEAGE_MISSING,
    MULTIPLE_DB_HEADS,
    TOO_NEW,
    TOO_OLD,
    UNKNOWN_SCHEMA,
    UNMIGRATED,
    Step,
)
from app.core.schema import alembic_config

# Ancestry: zzzz… (base) → mmmm… → 0000… (head). Lexically the head is the
# smallest and the base the largest — a string comparison gets every case wrong.
BASE, MIDDLE, HEAD = "zzzzzzzzzzz1", "mmmmmmmmmmm2", "00000000000a"
OLDER_BRANCH = "bbbbbbbbbbbb"
GRAPH = release.Graph([
    Step(BASE, None, "BARRIER", "BLOCKED"),
    Step(MIDDLE, BASE, "EXPAND", "SAFE"),
    Step(HEAD, MIDDLE, "EXPAND", "SAFE"),
])


def manifest(minimum=MIDDLE):
    return release.ReleaseManifest(
        release="test", schema_head=HEAD, minimum_schema=minimum,
        maximum_schema=HEAD, schema_transition="EXPAND", rollback_to_previous="SAFE",
        rollback_note="test", previous_release="prev", previous_schema_head=MIDDLE)


def decide(db, lineage=None, minimum=MIDDLE):
    heads = [] if db is None else (db if isinstance(db, list) else [db])
    return release.evaluate(manifest(minimum), GRAPH, heads, lineage)


def future(*steps):
    """Lineage rows the database recorded for revisions newer than the build."""
    rows = {s.revision: s for s in steps}
    for s in GRAPH.steps.values():
        rows[s.revision] = s
    return rows


# --- revisions the build knows -----------------------------------------------------------------


def test_the_build_head_is_exact():
    assert decide(HEAD).code == EXACT and decide(HEAD).allowed


def test_a_database_within_the_declared_range_is_allowed():
    """minimum = MIDDLE, maximum = HEAD, database at MIDDLE: allowed."""
    assert decide(MIDDLE).code == BEHIND_SUPPORTED and decide(MIDDLE).allowed


def test_a_database_older_than_the_minimum_is_refused():
    d = decide(BASE)
    assert d.code == TOO_OLD and not d.allowed


def test_unmigrated_and_multiple_heads_are_refused():
    assert decide(None).code == UNMIGRATED and not decide(None).allowed
    d = decide([HEAD, MIDDLE])
    assert d.code == MULTIPLE_DB_HEADS and not d.allowed


# --- revisions newer than the build (only the database knows them) ---------------------------


def test_an_expanded_schema_admits_the_older_compatible_build():
    """The database moved two EXPAND/SAFE steps past this build's head: this
    (older) build keeps running — a rolling deploy or a rollback target."""
    lineage = future(Step("ffffffffff01", HEAD, "EXPAND", "SAFE"),
                     Step("111111111102", "ffffffffff01", "EXPAND", "SAFE"))
    d = decide("111111111102", lineage)
    assert d.code == AHEAD_COMPATIBLE and d.allowed and d.steps_ahead == 2


@pytest.mark.parametrize("transition, rollback", [("BARRIER", "BLOCKED"), ("EXPAND", "BLOCKED")])
def test_a_barrier_or_a_rollback_blocked_step_ahead_is_too_new(transition, rollback):
    lineage = future(Step("ffffffffff01", HEAD, "EXPAND", "SAFE"),
                     Step("ffffffffff02", "ffffffffff01", transition, rollback),
                     Step("ffffffffff03", "ffffffffff02", "EXPAND", "SAFE"))
    d = decide("ffffffffff03", lineage)
    assert d.code == TOO_NEW and not d.allowed


def test_an_unknown_revision_without_lineage_is_refused():
    assert decide("ffffffffff01", None).code == UNKNOWN_SCHEMA
    assert decide("ffffffffff01", future()).code == UNKNOWN_SCHEMA


@pytest.mark.parametrize("lineage_steps, db", [
    # leads to a root, never to this build's head
    ([Step("ffffffffff01", None, "EXPAND", "SAFE")], "ffffffffff01"),
    # branches off a revision the build knows, but not its head
    ([Step("ffffffffff01", MIDDLE, "EXPAND", "SAFE")], "ffffffffff01"),
    # a cycle
    ([Step("ffffffffff01", "ffffffffff02", "EXPAND", "SAFE"),
      Step("ffffffffff02", "ffffffffff01", "EXPAND", "SAFE")], "ffffffffff01"),
])
def test_a_divergent_lineage_is_refused(lineage_steps, db):
    d = decide(db, future(*lineage_steps))
    assert d.code == DIVERGENT and not d.allowed


def test_compatibility_follows_lineage_not_string_order():
    """Every decision here would flip under `db >= head` or `db <= head`."""
    assert HEAD < MIDDLE < BASE  # the trap: lexical order is reversed
    assert decide(BASE).code == TOO_OLD           # lexically "newest"
    assert decide(MIDDLE).code == BEHIND_SUPPORTED
    lineage = future(Step("000000000001", HEAD, "BARRIER", "BLOCKED"))
    assert decide("000000000001", lineage).code == TOO_NEW  # lexically "oldest"


# --- the real migration chain ------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    graph = release.graph_from_scripts(ScriptDirectory.from_config(alembic_config()))
    data = release.MANIFEST_PATH.read_text(encoding="utf-8")
    return graph, release.parse_manifest(data, graph)


def test_the_real_chain_is_decided_by_ancestry(real):
    graph, m = real
    assert m.schema_head == "0c4e6a8b2d91" and m.minimum_schema == "f3b5d7e9a1c2"
    assert m.schema_head < m.minimum_schema  # the new head sorts before its parent
    full = {r: graph.steps[r] for r in graph.ancestors(graph.head)}
    assert release.evaluate(m, graph, [m.schema_head], full).code == EXACT
    # bootstrap: an IBB-001 database (no lineage yet) runs this build
    assert release.evaluate(m, graph, ["f3b5d7e9a1c2"], None).code == BEHIND_SUPPORTED
    for older in graph.ancestors("d0f2b4c6e8a1"):
        assert release.evaluate(m, graph, [older], None).code == TOO_OLD, older
    # look-alike ids: b8d0f2a4c6e1 is much older than b8d0f2a4c6e8
    assert graph.is_ancestor_or_equal("b8d0f2a4c6e1", "b8d0f2a4c6e8")


def test_the_manifest_file_is_json_with_no_build_sha_committed():
    data = json.loads(release.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "build_sha" not in data  # the build supplies it; the repository cannot know it


# --- ordering, id shape and merges never decide -----------------------------------------------


def test_step_listing_order_does_not_change_any_decision():
    steps = list(GRAPH.steps.values())
    lineage = future(Step("ffffffffff01", HEAD, "EXPAND", "SAFE"),
                     Step("ffffffffff02", "ffffffffff01", "BARRIER", "BLOCKED"))
    cases = [BASE, MIDDLE, HEAD, "ffffffffff01", "ffffffffff02"]
    expected = [decide(db, lineage).code for db in cases]
    rng = random.Random(2)
    for _ in range(20):
        rng.shuffle(steps)
        graph = release.Graph(steps)
        shuffled = dict(rng.sample(sorted(lineage.items()), len(lineage)))
        got = [release.evaluate(manifest(), graph, [db], shuffled).code for db in cases]
        assert got == expected


def test_revision_id_length_is_meaningless():
    """A long id is not "newer", a short one not "older": ancestry decides."""
    base, mid, head = "9" * 30, "1", "a" * 5
    graph = release.Graph([Step(head, mid, "EXPAND", "SAFE"), Step(base, None, "BARRIER", "BLOCKED"),
                           Step(mid, base, "EXPAND", "SAFE")])
    m = release.ReleaseManifest(
        release="t", schema_head=head, minimum_schema=mid, maximum_schema=head,
        schema_transition="EXPAND", rollback_to_previous="SAFE", rollback_note="t",
        previous_release="p", previous_schema_head=mid)
    assert release.evaluate(m, graph, [base], None).code == TOO_OLD
    assert release.evaluate(m, graph, [mid], None).code == BEHIND_SUPPORTED
    assert release.evaluate(m, graph, [head], None).code == EXACT


def test_a_merge_revision_in_the_build_is_refused():
    """The history is a single chain; a merge node is refused, not guessed across."""
    def script(rev, down):
        return SimpleNamespace(revision=rev, down_revision=down,
                               module=SimpleNamespace(revision=rev, schema_transition="EXPAND",
                                                      rollback_to_previous="SAFE"))

    scripts = SimpleNamespace(walk_revisions=lambda: [
        script("cccccccccccc", ("aaaaaaaaaaaa", "bbbbbbbbbbbb")),
        script("aaaaaaaaaaaa", "000000000000"), script("bbbbbbbbbbbb", "000000000000"),
        script("000000000000", None)])
    with pytest.raises(release.ReleaseManifestError, match="merge revision cccccccccccc"):
        release.graph_from_scripts(scripts)


def test_two_branches_in_the_build_are_refused():
    with pytest.raises(release.ReleaseManifestError, match="2 migration heads"):
        release.Graph(list(GRAPH.steps.values()) + [Step("bbbbbbbbbbb9", BASE, "EXPAND", "SAFE")])


# --- a schema that includes the lineage migration must carry its lineage ----------------------

# The same shape, with MIDDLE as the step that creates schema_lineage.
LGRAPH = release.Graph(GRAPH.steps.values(), lineage_revision=MIDDLE)


def ldecide(db, lineage):
    return release.evaluate(manifest(BASE), LGRAPH, [db], lineage)


def test_before_the_lineage_migration_no_lineage_is_expected():
    assert ldecide(BASE, None).code == BEHIND_SUPPORTED


@pytest.mark.parametrize("db", [MIDDLE, HEAD])
def test_a_missing_lineage_is_refused_never_fabricated(db):
    d = ldecide(db, None)
    assert d.code == LINEAGE_MISSING and not d.allowed


@pytest.mark.parametrize("damage", ["drop_row", "flip_rollback", "reparent"])
def test_a_lineage_that_disagrees_with_the_migrations_is_refused(damage):
    lineage = future()
    if damage == "drop_row":
        del lineage[BASE]
    elif damage == "flip_rollback":
        lineage[MIDDLE] = Step(MIDDLE, BASE, "EXPAND", "BLOCKED")
    else:
        lineage[HEAD] = Step(HEAD, BASE, "EXPAND", "SAFE")
    d = ldecide(HEAD, lineage)
    assert d.code == LINEAGE_MISMATCH and not d.allowed


def test_ahead_requires_the_known_part_of_the_lineage_to_agree():
    lineage = future(Step("ffffffffff01", HEAD, "EXPAND", "SAFE"))
    assert ldecide("ffffffffff01", lineage).code == AHEAD_COMPATIBLE
    lineage[MIDDLE] = Step(MIDDLE, BASE, "BARRIER", "BLOCKED")
    assert ldecide("ffffffffff01", lineage).code == LINEAGE_MISMATCH


def test_the_real_build_expects_lineage_from_its_lineage_migration(real):
    graph, m = real
    assert graph.lineage_revision == release.LINEAGE_REVISION == m.schema_head
    assert release.evaluate(m, graph, [m.schema_head], None).code == LINEAGE_MISSING
    assert not graph.expects_lineage(m.minimum_schema)
