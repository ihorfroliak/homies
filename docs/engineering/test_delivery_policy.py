"""Synthetic AGENT-002 policy checks; no models, credentials or database use."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import delivery_policy as policy

ROOT = Path(__file__).resolve().parents[2]
BASE = '4ed8fe8ab334a8d8e344b80e266da2be3b661aee'
A, B = 'a' * 40, 'b' * 40


def task(**kwargs):
    data = dict(id='TEST-001', context='synthetic', contract='docs/tasks/TEST.md',
                authorization='Synthetic founder authorization', base_sha=A,
                base_branch='main', branch='codex/TEST-001', risk='R2',
                changes=['backend'], state='READY', priority=10, dependencies=[])
    data.update(kwargs)
    return data


def verified_task(**kwargs):
    data = task(state='CI_GREEN', writer='writer-1', candidate_sha=B)
    data.update(kwargs)
    data['evidence'] = {key: dict(sha=data['candidate_sha'], result='PASS', reference='synthetic:'+key)
                        for key in ('tests', 'review', 'ci', 'operational')}
    data['evidence']['review'].update(reviewer='reviewer-2', separate_context=True)
    return data


class PolicyTests(unittest.TestCase):
    def test_routing_deterministic_bounded(self):
        changes = list(policy.ROUTES)
        expected = {'R0': [], 'R1': ['security-auditor'],
                    'R2': ['security-auditor', 'postgres-auditor'],
                    'R3': ['security-auditor', 'postgres-auditor']}
        for risk in expected:
            self.assertEqual(policy.specialists(task(risk=risk, changes=changes)), expected[risk])
            self.assertEqual(policy.specialists(task(risk=risk, changes=changes[::-1])), expected[risk])
        self.assertEqual(policy.specialists(task(changes=['frontend', 'testing'])),
                         ['frontend-reviewer', 'test-engineer'])
        self.assertEqual(policy.specialists(task(risk='R1', changes=['docs'])), [])

    def test_unknown_inputs_fail(self):
        for override in ({'risk': 'R9'}, {'changes': ['guess']}, {'state': 'DONE'},
                         {'branch': 'main'}, {'base_sha': 'latest'}, {'context': '../escape'}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                policy.validate(task(**override))

    def test_section9_not_optional(self):
        for surface in policy.MANDATORY:
            current = verified_task(risk='R0', changes=[surface])
            del current['evidence']['review']
            with self.subTest(surface=surface), self.assertRaisesRegex(ValueError, 'review'):
                policy.delivery_gates(current)

    def test_r3_operational_gate(self):
        current = verified_task(risk='R3')
        current['evidence']['operational']['sha'] = A
        with self.assertRaisesRegex(ValueError, 'operational'):
            policy.delivery_gates(current)

    def test_no_self_review_or_stale_review(self):
        for changes in ({'reviewer': 'writer-1'}, {'separate_context': False}, {'sha': A}):
            current = verified_task(changes=['privacy'])
            current['evidence']['review'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                policy.delivery_gates(current)

    def test_stale_tests_ci_and_blockers(self):
        for key in ('tests', 'ci'):
            current = verified_task()
            current['evidence'][key]['sha'] = A
            with self.assertRaises(ValueError):
                policy.delivery_gates(current)
        with self.assertRaises(ValueError):
            policy.delivery_gates(verified_task(blockers=['unresolved']))

    def test_selection_does_not_duplicate_or_restart(self):
        skipped = [task(id='UNAUTHORIZED', authorization=''), task(id='DONE', state='BUILDER_VERIFIED'),
                   task(id='OWNED', writer='other'), task(id='BLOCKED', blockers=['pending']),
                   task(id='CANDIDATE', candidate_sha=B), task(id='CONTEXT', context='active')]
        selected = task(id='NEXT', priority=20)
        self.assertEqual(policy.select([selected, *skipped], ['active']), selected)
        self.assertIsNone(policy.select(skipped, ['active']))
        self.assertEqual(policy.select([task(id='Z'), task(id='A')])['id'], 'A')

    def test_dependency_identity_and_stack(self):
        upstream = verified_task(id='UP', state='DRAFT_PR_READY')
        dependent = task(id='DOWN', context='next', base_sha=B,
                         base_branch=upstream['branch'], branch='codex/DOWN',
                         dependencies=[dict(id='UP', mode='stacked', sha=B)])
        self.assertEqual(policy.select([upstream, dependent]), dependent)
        for key, value in [('base_sha', A), ('base_branch', 'main')]:
            changed = deepcopy(dependent)
            changed[key] = value
            self.assertIsNone(policy.select([upstream, changed]))
        upstream['evidence']['ci']['sha'] = A
        self.assertIsNone(policy.select([upstream, dependent]))
        dependent['dependencies'][0]['mode'] = 'integrated'
        self.assertIsNone(policy.select([upstream, dependent]))
        upstream.update(state='INTEGRATED', integrated_sha=B)
        self.assertEqual(policy.select([upstream, dependent]), dependent)
        upstream['integrated_sha'] = A
        self.assertIsNone(policy.select([upstream, dependent]))



class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='homies-agent002-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        policy.git(self.root, 'init', '-q', '-b', 'codex/TEST-001')
        contract = self.root / 'docs/tasks/TEST.md'
        contract.parent.mkdir(parents=True)
        contract.write_text('Synthetic contract\n', encoding='utf-8')
        policy.git(self.root, 'add', '.')
        policy.git(self.root, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                   '-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic fixture')
        self.current = task(base_sha=policy.git(self.root, 'rev-parse', 'HEAD'))

    def claim(self):
        return policy.acquire(self.root, self.current, 'writer-1')

    def checkpoint_task(self):
        return verified_task(base_sha=self.current['base_sha'], candidate_sha=self.current['base_sha'],
                             blockers=[], next='Await founder decision', metrics={'agent_calls': 0})

    def test_one_writer_across_worktrees(self):
        second = Path(self.temp.name) / 'other'
        policy.git(self.root, 'worktree', 'add', '-q', '-b', 'codex/OTHER', str(second))
        other = task(branch='codex/OTHER', base_sha=self.current['base_sha'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(policy.acquire, root, record, owner)
                        for root, record, owner in [(self.root, self.current, 'writer-1'),
                                                    (second, other, 'writer-2')]]
        self.assertEqual(sum(f.exception() is None for f in outcomes), 1)
        self.assertTrue(all(f.exception() is None or isinstance(f.exception(), (ValueError, FileExistsError))
                            for f in outcomes))
        self.assertEqual(policy.ownership_dir(self.root), policy.ownership_dir(second))

    def test_resume_preserves_evidence_and_blockers(self):
        self.claim()
        current = self.checkpoint_task()
        current.update(state='BLOCKED', blockers=['synthetic dependency unavailable'])
        policy.checkpoint(self.root, current, 'writer-1')
        restored = policy.resume(self.root, self.current, 'writer-1')
        self.assertEqual(restored['checkpoint']['blockers'], current['blockers'])
        self.assertEqual(restored['checkpoint']['evidence'], current['evidence'])
        self.assertEqual(restored['checkpoint']['next'], current['next'])
        self.assertGreaterEqual(restored['recovery_ms'], 0)
        with self.assertRaises(ValueError):
            policy.resume(self.root, self.current, 'writer-2')

    def test_interrupted_claim_is_not_stolen(self):
        path = policy.claim_path(self.root, self.current)
        path.parent.mkdir(parents=True)
        path.write_text('{partial', encoding='utf-8')
        with self.assertRaises((ValueError, FileExistsError)):
            self.claim()
        self.assertEqual(path.read_text(), '{partial')

    def test_resume_rejects_changed_head_contract_or_dirty_tree(self):
        self.claim()
        current = self.checkpoint_task()
        policy.checkpoint(self.root, current, 'writer-1')
        (self.root / 'other.txt').write_text('preserve me')
        with self.assertRaisesRegex(ValueError, 'dirty'):
            policy.resume(self.root, self.current, 'writer-1')
        policy.git(self.root, 'add', '.')
        policy.git(self.root, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                   '-c', 'commit.gpgsign=false', 'commit', '-qm', 'new work')
        with self.assertRaisesRegex(ValueError, 'HEAD changed'):
            policy.resume(self.root, self.current, 'writer-1')
        (self.root / 'docs/tasks/TEST.md').write_text('changed contract')
        with self.assertRaisesRegex(ValueError, 'contract changed'):
            policy.resume(self.root, self.current, 'writer-1')

    def test_checkpoint_merge_authorization_cannot_be_skipped(self):
        self.claim()
        current = self.checkpoint_task()
        for state in ('MERGE_AUTHORIZED', 'INTEGRATED'):
            current.update(state=state, integrated_sha=current['candidate_sha'],
                           integration_reference='synthetic merge')
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'authorization'):
                policy.checkpoint(self.root, current, 'writer-1')
        current['merge_authorization'] = dict(sha=current['candidate_sha'], reference='founder approval')
        self.assertEqual(policy.checkpoint(self.root, current, 'writer-1')['state'], 'INTEGRATED')

    def test_checkpoint_reviewed_state_requires_review(self):
        self.claim()
        current = self.checkpoint_task()
        current.update(changes=['privacy'], state='REVIEWED')
        current['evidence']['review']['reviewer'] = 'writer-1'
        with self.assertRaises(ValueError):
            policy.checkpoint(self.root, current, 'writer-1')

    def test_unknown_metrics_and_large_checkpoint_refused(self):
        self.claim()
        current = self.checkpoint_task()
        current['metrics']['raw_hook_event'] = 'not allowed'
        with self.assertRaises(ValueError):
            policy.checkpoint(self.root, current, 'writer-1')
        current['metrics'] = {}
        current['next'] = 'x' * 33000
        with self.assertRaises(ValueError):
            policy.checkpoint(self.root, current, 'writer-1')

    def test_checkpoint_is_task_isolated(self):
        first = policy.checkpoint_path(self.root, self.current)
        second = policy.checkpoint_path(self.root, task(id="TEST-002"))
        self.assertNotEqual(first, second)

    def test_claim_checks_dependencies(self):
        self.current['dependencies'] = [dict(id='missing', mode='integrated', sha=A)]
        with self.assertRaisesRegex(ValueError, 'unblocked'):
            self.claim()

    def test_orphan_busy_blocks_plan_and_acquire(self):
        marker = policy.claim_path(self.root, self.current).with_suffix('.busy')
        marker.parent.mkdir(parents=True)
        marker.write_text('', encoding='utf-8')
        self.assertIsNone(policy.select([self.current], policy.active_contexts(self.root)))
        with self.assertRaises(ValueError):
            self.claim()
        self.assertFalse(policy.claim_path(self.root, self.current).exists())
        self.assertTrue(marker.exists())
        backlog = Path(self.temp.name) / 'backlog.json'
        backlog.write_text(json.dumps([self.current]), encoding='utf-8')
        result = subprocess.run(['python', str(ROOT / 'docs/engineering/delivery_policy.py'),
                                 'plan', str(backlog), '--root', str(self.root)],
                                check=True, capture_output=True, text=True)
        self.assertIsNone(json.loads(result.stdout)['task'])

    def test_acquire_waits_for_release_operation_to_finish(self):
        self.claim()
        # Pause release precisely after deleting its claim, before clearing .busy.
        with policy.owner_operation(self.root, self.current, 'writer-1'):
            policy.claim_path(self.root, self.current).unlink()
            with ThreadPoolExecutor(max_workers=1) as pool:
                contender = pool.submit(policy.acquire, self.root, self.current, 'writer-2')
                with self.assertRaises((ValueError, FileExistsError)):
                    contender.result(timeout=10)
            self.assertFalse(policy.claim_path(self.root, self.current).exists())
        self.assertEqual(policy.acquire(self.root, self.current, 'writer-2')['owner'], 'writer-2')

    def test_acquire_checks_operation_marker_after_stale_selection(self):
        marker = policy.claim_path(self.root, self.current).with_suffix('.busy')
        marker.parent.mkdir(parents=True)
        marker.write_text('', encoding='utf-8')
        # Simulate a selection snapshot taken before another operation acquired
        # the marker. Atomic marker creation must still exclude this claimant.
        with patch.object(policy, 'active_contexts', return_value=set()):
            with self.assertRaises(FileExistsError):
                self.claim()
        self.assertTrue(marker.exists())
        self.assertFalse(policy.claim_path(self.root, self.current).exists())

    def test_changed_input_branch_rejected_without_replacing_checkpoint(self):
        self.claim()
        current = self.checkpoint_task()
        policy.checkpoint(self.root, current, 'writer-1')
        path = policy.checkpoint_path(self.root, current)
        previous = path.read_bytes()
        changed = dict(current, branch='codex/DIFFERENT-NONEXISTENT')
        for action in (policy.checkpoint, policy.resume):
            with self.subTest(action=action.__name__), self.assertRaisesRegex(ValueError, 'branch'):
                action(self.root, changed, 'writer-1')
        with self.assertRaisesRegex(ValueError, 'branch'):
            policy.draft_payload(changed, self.root, 'writer-1')
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(policy.resume(self.root, current, 'writer-1')['checkpoint']['branch'], current['branch'])

    def test_changed_saved_branch_rejected_on_resume(self):
        self.claim()
        current = self.checkpoint_task()
        saved = policy.checkpoint(self.root, current, 'writer-1')
        saved['branch'] = 'codex/DIFFERENT-NONEXISTENT'
        path = policy.checkpoint_path(self.root, current)
        path.write_text(json.dumps(saved), encoding='utf-8')
        previous = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'branch'):
            policy.resume(self.root, current, 'writer-1')
        self.assertEqual(path.read_bytes(), previous)

    def test_draft_is_always_draft_and_can_trigger_ci(self):
        self.claim()
        current = self.checkpoint_task()
        current.update(state='REVIEWED', changes=['privacy'])
        del current['evidence']['ci']
        payload = policy.draft_payload(current, self.root, 'writer-1')
        self.assertIs(payload['draft'], True)
        self.assertEqual(payload['head'], policy.git(self.root, 'branch', '--show-current'))
        self.assertIn('CI pending', payload['body'])
        self.assertNotIn('merge', payload)
        current['state'] = 'MERGE_AUTHORIZED'
        with self.assertRaises(ValueError):
            policy.draft_payload(current, self.root, 'writer-1')

    def test_cli_draft_smoke(self):
        self.claim()
        path = Path(self.temp.name) / 'task.json'
        path.write_text(json.dumps(self.checkpoint_task()), encoding='utf-8')
        result = subprocess.run(['python', str(ROOT / 'docs/engineering/delivery_policy.py'),
                                 'draft', str(path), '--root', str(self.root), '--owner', 'writer-1'],
                                check=True, capture_output=True, text=True)
        self.assertIs(json.loads(result.stdout)['draft'], True)



class ConfigurationTests(unittest.TestCase):
    def test_six_specialists_unchanged_plus_one_orchestrator(self):
        for directory, extension in [('.claude/agents', '*.md'), ('.codex/agents', '*.toml')]:
            paths = list((ROOT / directory).glob(extension))
            self.assertEqual(len(paths), 7)
            for path in paths:
                if path.stem == 'implementation-orchestrator':
                    continue
                rel = path.relative_to(ROOT).as_posix()
                self.assertEqual(policy.git(ROOT, 'hash-object', '--path', rel, rel),
                                 policy.git(ROOT, 'rev-parse', BASE + ':' + rel))
        cfg = tomllib.loads((ROOT / '.codex/agents/implementation-orchestrator.toml').read_text(encoding='utf-8-sig'))
        self.assertEqual(set(cfg), {'name', 'description', 'developer_instructions'})
        self.assertEqual(cfg['name'], 'implementation_orchestrator')

    def test_unchanged_agent001_privacy_hooks(self):
        for rel in ('.claude/settings.json', '.claude/hooks/context-pre-compact.ps1',
                    '.claude/hooks/context-post-compact.ps1', '.claude/hooks/context-session-start.ps1',
                    '.claude/rules/context-survival.md', '.codex/config.toml',
                    'docs/engineering/agent001_checks.py'):
            self.assertEqual(policy.git(ROOT, 'hash-object', '--path', rel, rel),
                             policy.git(ROOT, 'rev-parse', BASE + ':' + rel))



if __name__ == '__main__':
    unittest.main()
