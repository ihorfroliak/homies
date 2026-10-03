"""The release manifest and the migration declarations (PR-002), no database.

The manifest is strict and cross-checked against the migrations this build
carries; a malformed or contradictory one is never treated as compatible.
Rollback is SAFE only when declared SAFE — never by default.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

from app.core import release
from app.core.lineage_registry import HISTORICAL, REGISTRY
from app.core.schema import alembic_config

BACKEND = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(release.MANIFEST_PATH.read_text(encoding="utf-8"))
SHA = "5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98"
LINEAGE_MIGRATION = "0c4e6a8b2d91"


@pytest.fixture(scope="module")
def graph():
    return release.graph_from_scripts(ScriptDirectory.from_config(alembic_config()))


def _parse(graph, data=None):
    return release.parse_manifest(json.dumps(MANIFEST if data is None else data), graph)


# A previous release before the Slice 1 migration (EXPAND, rollback BLOCKED).
PR_003 = {"id": "PR-003", "schema_head": "0c4e6a8b2d91"}


def _with(**changes):
    data = copy.deepcopy(MANIFEST)
    for key, value in changes.items():
        if value is ...:
            del data[key]
        else:
            data[key] = value
    return data


# --- the committed manifest --------------------------------------------------------------------


def test_the_committed_manifest_is_valid_for_this_build(graph):
    manifest = _parse(graph)
    assert manifest.schema_head == graph.head == manifest.maximum_schema
    assert graph.is_ancestor_or_equal(manifest.minimum_schema, manifest.schema_head)
    assert "build_sha" not in manifest.as_dict()  # policy only; identity is injected


# --- build identity: injected by the build, never committed -----------------------------------


def test_the_committed_policy_cannot_carry_its_own_commit(graph):
    """A file cannot hold the id of the commit that contains it: the policy
    rejects a build_sha key rather than tolerating a stale one."""
    with pytest.raises(release.ReleaseManifestError, match="keys"):
        _parse(graph, _with(build_sha=SHA))


def test_runtime_identity_combines_policy_and_injected_build(graph, monkeypatch):
    monkeypatch.setenv(release.BUILD_SHA_ENV, SHA)
    identity = release.runtime_identity(_parse(graph), required=True)
    assert identity.build_sha == SHA
    assert identity.as_dict() == {**MANIFEST, "build_sha": SHA}


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_build_identity_fails_closed_where_required(graph, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(release.BUILD_SHA_ENV, raising=False)
    else:
        monkeypatch.setenv(release.BUILD_SHA_ENV, value)
    with pytest.raises(release.BuildIdentityError, match="required"):
        release.runtime_identity(_parse(graph), required=True)
    assert release.runtime_identity(_parse(graph), required=False).build_sha is None


@pytest.mark.parametrize("value", ["unknown", SHA[:12], SHA.upper(), SHA + "0", "g" * 40,
                                   SHA + "\nx"])
def test_a_malformed_build_identity_is_refused_everywhere(graph, monkeypatch, value):
    monkeypatch.setenv(release.BUILD_SHA_ENV, value)
    for required in (True, False):
        with pytest.raises(release.BuildIdentityError, match="40-character"):
            release.runtime_identity(_parse(graph), required=required)


def test_identity_is_required_outside_development():
    from app.core.config import DEV_ENVIRONMENTS

    assert release.DEVELOPMENT_ENVIRONMENTS == DEV_ENVIRONMENTS
    assert not any(release.identity_required(env) for env in ("local", "test", "ci"))
    assert all(release.identity_required(env) for env in ("production", "staging", "prod", ""))


def _compatible(monkeypatch, graph):
    from app.core import schema

    manifest = _parse(graph)
    monkeypatch.setattr(schema, "check_compatibility",
                        lambda: (release.Decision(release.EXACT, graph.head), manifest))
    return schema


def test_production_startup_refuses_a_build_without_identity(graph, monkeypatch):
    schema = _compatible(monkeypatch, graph)
    monkeypatch.setattr(schema.settings, "env", "production")
    monkeypatch.delenv(release.BUILD_SHA_ENV, raising=False)
    with pytest.raises(release.BuildIdentityError):
        schema.ensure_schema()
    monkeypatch.setenv(release.BUILD_SHA_ENV, "unknown")
    with pytest.raises(release.BuildIdentityError):
        schema.ensure_schema()
    monkeypatch.setenv(release.BUILD_SHA_ENV, SHA)
    schema.ensure_schema()


def test_the_image_has_no_placeholder_build_identity():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "\nARG GIT_SHA\n" in dockerfile
    assert "GIT_SHA=unknown" not in dockerfile
    assert "ENV HOMIES_BUILD_SHA=$GIT_SHA" in dockerfile
    assert "org.opencontainers.image.revision=$GIT_SHA" in dockerfile


def test_this_release_declares_its_rollback_honestly(graph):
    """TASK-015 Slice 4a changes no schema (message redaction columns and
    MESSAGE decisions exist since the Slice 1 head a3c5e7f9b1d4), yet
    rollback to Slice 5 is BLOCKED — a security/privacy barrier: that build
    serialises messages.body without looking at redacted_at and would show
    removed messages to participants again. The build still reads
    moderation_decisions on every publication, so its minimum schema stays
    its own head."""
    manifest = _parse(graph)
    assert manifest.schema_transition == release.NO_SCHEMA_CHANGE
    assert manifest.rollback_to_previous == release.BLOCKED
    assert manifest.rollback_allowed() is False
    assert manifest.previous_schema_head == manifest.schema_head == "a3c5e7f9b1d4"
    assert manifest.minimum_schema == manifest.schema_head
    # The barrier is a privacy one and names the build it protects against.
    assert MANIFEST["previous_release"]["id"] == "TASK-015-S5"
    assert "SECURITY/PRIVACY BARRIER" in MANIFEST["rollback_note"]


# --- malformed manifests are errors, never compatible -----------------------------------------


@pytest.mark.parametrize("data, message", [
    (_with(rollback_to_previous=...), "keys"),
    (_with(extra="x"), "keys"),
    (_with(manifest_version=2), "manifest_version"),
    (_with(rollback_to_previous="MAYBE"), "rollback_to_previous"),
    (_with(rollback_to_previous=None), "rollback_to_previous"),
    (_with(schema_transition="SAFE"), "schema_transition"),
    (_with(schema_head="F3B5D7E9A1C2"), "12-character"),
    (_with(minimum_schema="aaaaaaaaaaaa"), "not a revision this build carries"),
    (_with(schema_head="f3b5d7e9a1c2"), "not the build's migration head"),
    (_with(maximum_schema="f3b5d7e9a1c2"), "maximum_schema"),
    (_with(release=""), "release"),
    (_with(previous_release={"id": "IBB-001"}), "previous_release"),
    # the declared transition must match the migrations since the previous release
    (_with(schema_transition="EXPAND"), "contradicts"),
    (_with(schema_transition="BARRIER"), "contradicts"),
    (_with(schema_transition="NO_SCHEMA_CHANGE", previous_release=PR_003), "contradicts"),
    # a release cannot promise SAFE across a step that declares BLOCKED
    (_with(schema_transition="EXPAND", rollback_to_previous="SAFE",
           previous_release=PR_003), "contradicts a migration"),
])
def test_a_malformed_or_contradictory_manifest_is_refused(graph, data, message):
    with pytest.raises(release.ReleaseManifestError, match=message):
        _parse(graph, data)


SMALL = [release.Step("aaaaaaaaaaa1", None, "BARRIER", "BLOCKED"),
         release.Step("aaaaaaaaaaa2", "aaaaaaaaaaa1", "EXPAND", "SAFE")]


def test_an_explicit_safe_code_only_release_is_honoured():
    data = _with(schema_head="aaaaaaaaaaa2", maximum_schema="aaaaaaaaaaa2",
                 minimum_schema="aaaaaaaaaaa1",
                 previous_release={"id": "x", "schema_head": "aaaaaaaaaaa2"},
                 schema_transition="NO_SCHEMA_CHANGE", rollback_to_previous="SAFE")
    manifest = _parse(release.Graph(SMALL), data)
    assert manifest.schema_transition == release.NO_SCHEMA_CHANGE
    assert manifest.rollback_allowed() is True


def test_missing_rollback_metadata_is_never_safe():
    """Even where SAFE would be consistent (a code-only release), a manifest
    without rollback_to_previous is invalid — it never becomes a rollback promise."""
    data = _with(schema_head="aaaaaaaaaaa2", maximum_schema="aaaaaaaaaaa2",
                 minimum_schema="aaaaaaaaaaa1",
                 previous_release={"id": "x", "schema_head": "aaaaaaaaaaa2"},
                 schema_transition="NO_SCHEMA_CHANGE", rollback_to_previous=...)
    with pytest.raises(release.ReleaseManifestError, match="keys"):
        _parse(release.Graph(SMALL), data)


def test_a_build_with_two_migration_heads_is_refused():
    with pytest.raises(release.ReleaseManifestError, match="2 migration heads"):
        release.Graph(SMALL + [release.Step("aaaaaaaaaaa3", "aaaaaaaaaaa1", "EXPAND", "SAFE")])


def test_rollback_is_safe_only_when_declared_safe(graph):
    for value in ("BLOCKED",):
        assert _parse(graph, _with(rollback_to_previous=value)).rollback_allowed() is False
    manifest = _parse(graph)
    object.__setattr__(manifest, "rollback_to_previous", "")  # a corrupted in-memory value
    assert manifest.rollback_allowed() is False


def _code_only(**changes):
    """A release with no schema change since its predecessor: SAFE is consistent here."""
    base = dict(schema_head="aaaaaaaaaaa2", maximum_schema="aaaaaaaaaaa2",
                minimum_schema="aaaaaaaaaaa1",
                previous_release={"id": "x", "schema_head": "aaaaaaaaaaa2"},
                schema_transition="NO_SCHEMA_CHANGE", rollback_to_previous="SAFE")
    base.update(changes)
    return _with(**base)


@pytest.mark.parametrize("case, data, allowed", [
    ("explicit SAFE", _code_only(), True),
    ("explicit BLOCKED", _code_only(rollback_to_previous="BLOCKED"), False),
    ("missing", _code_only(rollback_to_previous=...), None),
    ("null", _code_only(rollback_to_previous=None), None),
    ("lower-case", _code_only(rollback_to_previous="safe"), None),
    ("empty", _code_only(rollback_to_previous=""), None),
    ("boolean", _code_only(rollback_to_previous=True), None),
    ("unknown previous schema",
     _code_only(previous_release={"id": "x", "schema_head": "ffffffffffff"}), None),
    ("malformed previous schema",
     _code_only(previous_release={"id": "x", "schema_head": "SAFE"}), None),
])
def test_rollback_metadata_fails_closed(case, data, allowed):
    """SAFE -> SAFE; BLOCKED -> BLOCKED; missing / malformed / unknown schema ->
    an invalid release (None here), never SAFE. Schema compatibility is a
    separate dimension: a SAFE rollback promise makes no schema compatible."""
    graph = release.Graph(SMALL)
    if allowed is None:
        with pytest.raises(release.ReleaseManifestError):
            release.parse_manifest(json.dumps(data), graph)
        return
    assert release.parse_manifest(json.dumps(data), graph).rollback_allowed() is allowed


# --- migration declarations --------------------------------------------------------------------


def test_every_migration_has_valid_declarations(graph):
    # REGISTRY classifies the 26 steps before PR-002; every later step
    # (PR-002's lineage, TASK-015 S1's moderation core, …) declares itself.
    assert len(graph.steps) == len(REGISTRY) + 2
    for step in graph.steps.values():
        assert step.schema_transition in release.STEP_TRANSITIONS
        assert step.rollback_to_previous in release.ROLLBACK_VALUES
        assert not (step.schema_transition == release.BARRIER
                    and step.rollback_to_previous == release.SAFE)


def test_migrations_from_pr002_on_declare_their_own_compatibility():
    scripts = ScriptDirectory.from_config(alembic_config())
    for script in scripts.walk_revisions():
        if script.revision in REGISTRY:
            assert not hasattr(script.module, "schema_transition"), script.revision
            continue
        assert script.module.schema_transition in release.STEP_TRANSITIONS, script.revision
        assert script.module.rollback_to_previous in release.ROLLBACK_VALUES, script.revision


def test_a_migration_without_declarations_is_an_error_not_a_default():
    class Undeclared:
        revision = "abcdefabcdef"

    with pytest.raises(release.ReleaseManifestError, match="schema_transition"):
        release.step_declarations(Undeclared, HISTORICAL)
    Undeclared.schema_transition = "BARRIER"  # type: ignore[attr-defined]
    Undeclared.rollback_to_previous = "SAFE"  # type: ignore[attr-defined]
    with pytest.raises(release.ReleaseManifestError, match="BARRIER cannot be rollback SAFE"):
        release.step_declarations(Undeclared, HISTORICAL)


def test_the_lineage_backfill_is_exactly_the_registry():
    path = next((BACKEND / "alembic/versions").glob(f"{LINEAGE_MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("lineage_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    backfill = {rev: (t, r) for rev, _down, t, r in module.HISTORY}
    assert backfill == HISTORICAL
    scripts = ScriptDirectory.from_config(alembic_config())
    for rev, down, _t, _r in module.HISTORY:
        assert scripts.get_revision(rev).down_revision == down


def test_additive_is_not_rollback_safe_in_the_history():
    """Phase A's evidence, kept: schema-compatible steps that still block rollback."""
    expand_blocked = {r for r, (t, rb) in HISTORICAL.items() if (t, rb) == ("EXPAND", "BLOCKED")}
    assert {"d3f81ba0c47e", "b7e4f19a2c60", "f1a7c3d9e2b4", "c1e3a5b7d9f2", "b8d0f2a4c6e8",
            "f3b5d7e9a1c2"} == expand_blocked
    barriers = {r for r, (t, _) in HISTORICAL.items() if t == "BARRIER"}
    assert barriers == {"2d9d18df4688", "b910997aa651", "c4d2e77a1b30", "c9d3a5e71f28",
                        "d4e8b2c61a95", "e4f6a8b0c2d4"}


def test_the_migration_template_forces_a_fail_closed_declaration():
    template = (BACKEND / "alembic/script.py.mako").read_text(encoding="utf-8")
    assert 'schema_transition = "BARRIER"' in template
    assert 'rollback_to_previous = "BLOCKED"' in template


# --- build identity stays off the public surface ----------------------------------------------


def test_the_build_sha_is_not_exposed_on_public_metrics(client, monkeypatch):
    monkeypatch.setenv(release.BUILD_SHA_ENV, SHA)
    body = client.get("/metrics").text
    assert SHA not in body and "build_info" not in body


def test_the_rollback_cli_refuses_a_blocked_release(capsys):
    from app.scripts import release as cli

    assert cli.main(["rollback-allowed"]) == 1
    assert json.loads(capsys.readouterr().out)["rollback_to_previous"] == "BLOCKED"


def test_the_manifest_cli_prints_the_runtime_identity(capsys, monkeypatch):
    from app.core.config import settings
    from app.scripts import release as cli

    monkeypatch.setenv(release.BUILD_SHA_ENV, SHA)
    monkeypatch.setattr(settings, "env", "production")
    assert cli.main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out) == {**MANIFEST, "build_sha": SHA}
    monkeypatch.delenv(release.BUILD_SHA_ENV)
    assert cli.main(["manifest"]) == 1  # production-like without identity
    assert json.loads(capsys.readouterr().out)["error"] == "INVALID_RELEASE"
    monkeypatch.setattr(settings, "env", "local")
    assert cli.main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["build_sha"] is None
