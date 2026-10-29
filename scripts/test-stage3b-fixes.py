"""Regression checks for the stage-3b script fixes.

Covers: fresh-clone checkout ordering, loader name vs repository path, and the
completed/failed/incomplete response handling of run-workflow.
"""

import json
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import importlib.util

def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

patch_module = load('patch-workflow-w6a8')
run_module = load('run-workflow')


def test_patch_uses_bare_loader_name_and_pinned_url():
    workflow = {
        'nodes': [{
            'id': 7,
            'type': 'UNETLoader',
            'widgets_values': ['minimax_h3_fl2va_pruned_int8_convrot.safetensors', 'default'],
            'widgets_values_named': {'unet_name': 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'},
            'properties': {'models': [{
                'name': 'minimax_h3_fl2va_pruned_int8_convrot.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/x.safetensors',
                'directory': 'diffusion_models',
            }]},
        }],
    }
    changed = []
    patch_module.patch(workflow, changed)
    node = workflow['nodes'][0]
    assert changed == [7]
    assert node['widgets_values'][0] == 'minimax_h3_fl2va_pruned_w6a8.safetensors'
    assert node['widgets_values_named']['unet_name'] == 'minimax_h3_fl2va_pruned_w6a8.safetensors'
    model = node['properties']['models'][0]
    assert model['name'] == 'minimax_h3_fl2va_pruned_w6a8.safetensors'
    assert '/diffusion_models/' in model['url']
    assert model['url'].endswith('/diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors')
    assert patch_module.REVISION in model['url']
    assert '/resolve/main/' not in model['url']
    assert patch_module.verify(workflow) == []


def test_patch_verify_rejects_path_in_loader_and_floating_url():
    bad = {'nodes': [{
        'type': 'UNETLoader',
        'widgets_values': ['diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors'],
        'properties': {'models': [{
            'name': 'x',
            'url': 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/x.safetensors',
        }]},
    }]}
    problems = patch_module.verify(bad)
    assert any('path' in p for p in problems)
    assert any('not pinned' in p for p in problems)


def test_patch_script_runs_end_to_end():
    source = ROOT / 'workflows' / 'video_minimax_h3_t2v.json'
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'patched.json'
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'patch-workflow-w6a8.py'), str(source), str(target)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(target.read_text(encoding='utf-8'))
        assert patch_module.verify(data) == []


def test_install_script_checks_out_before_verifying():
    """The HEAD assertion must not run before the checkout step."""
    text = (SCRIPTS / 'install-runtime.ps1').read_text(encoding='utf-8')
    checkout_pos = text.index('checkout --detach')
    verify_pos = text.index('HEAD verification failed')
    assert checkout_pos < verify_pos
    assert '--no-deps' not in text, 'dependency installation must not rely on --no-deps'
    assert 'requirements.lock.txt' in text
    # A re-resolve must be an explicit, opt-in action, not the default path.
    assert '$Relock' in text
    assert text.index('$Relock -or -not (Test-Path $verifiedLock)') > 0


def test_install_script_refuses_dirty_existing_checkout():
    text = (SCRIPTS / 'install-runtime.ps1').read_text(encoding='utf-8')
    assert 'refusing to reset' in text.lower()
    assert 'Refusing to change it automatically' in text


def _history_case(status):
    return {'p1': {'status': status, 'outputs': {}}}


def test_patch_rewrites_url_file_name_to_w6a8():
    """A loader renamed to W6A8 must not keep an INT8 URL (review finding)."""
    workflow = {
        'nodes': [{
            'id': 9,
            'type': 'UNETLoader',
            'widgets_values': ['minimax_h3_fl2va_pruned_int8_convrot.safetensors', 'default'],
            'widgets_values_named': {'unet_name': 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'},
            'properties': {'models': [{
                'name': 'minimax_h3_fl2va_pruned_int8_convrot.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors',
                'directory': 'diffusion_models',
            }]},
        }],
    }
    changed = []
    patch_module.patch(workflow, changed)
    model = workflow['nodes'][0]['properties']['models'][0]
    assert model['name'] == patch_module.LOADER_NAME
    assert model['url'].endswith('/diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors')
    assert 'int8_convrot' not in model['url']
    assert patch_module.REVISION in model['url']
    assert model['directory'] == 'diffusion_models'
    assert patch_module.verify(workflow) == []


def test_verify_detects_name_url_mismatch():
    bad = {'nodes': [{
        'type': 'UNETLoader',
        'widgets_values': ['minimax_h3_fl2va_pruned_w6a8.safetensors'],
        'properties': {'models': [{
            'name': 'minimax_h3_fl2va_pruned_w6a8.safetensors',
            'url': 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/e5eb578a89295337b8ff433a035929ce0279e0b6/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors',
            'directory': 'diffusion_models',
        }]},
    }]}
    problems = patch_module.verify(bad)
    assert any('mismatch' in p or 'INT8' in p for p in problems), problems


def test_committed_workflows_are_consistent():
    for name in ('video_minimax_h3_t2v_w6a8.json', 'video_minimax_h3_i2v_w6a8.json'):
        data = json.loads((ROOT / 'workflows' / name).read_text(encoding='utf-8'))
        assert patch_module.verify(data) == [], name


def test_run_workflow_rejects_incomplete_then_accepts_success():
    calls = {'n': 0}
    history_calls = {'n': 0}

    def fake_urlopen(url, timeout=0):
        calls['n'] += 1
        if 'history' in str(url):
            history_calls['n'] += 1
            if history_calls['n'] < 3:
                return _Ctx(_history_case({'completed': False, 'status_str': 'running'}))
            return _Ctx({'p1': {'status': {'completed': True, 'status_str': 'success'},
                                'outputs': {'14': {'images': [{'filename': 'clip.mp4',
                                                               'subfolder': ''}]}}}})
        return _Ctx({'prompt_id': 'p1'})

    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / 'rec.json'
        out_root = Path(tmp) / 'out'
        out_root.mkdir()
        (out_root / 'clip.mp4').write_bytes(b'x' * 10)
        argv = ['run-workflow.py', '--workflow', str(ROOT / 'workflows' / 't2v_smoke_api.json'),
                '--record', str(record), '--output-root', str(out_root),
                '--poll-interval', '0', '--label', 'unit']
        try:
            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(run_module.urllib.request, 'urlopen', fake_urlopen):
                run_module.main()
        except SystemExit as exit_error:
            raise AssertionError(f'main() exited early: {exit_error.code}') from None
        data = json.loads(record.read_text(encoding='utf-8'))
        assert history_calls['n'] == 3, 'must poll past incomplete responses'
        assert data['completed'] is True
        assert data['status_str'] == 'success'
        assert data['task_completed'] is True
        assert data['video_present'] is True
        assert data['artifacts'][0]['exists'] is True
        assert data['workflow_sha256']


def test_run_workflow_exits_nonzero_on_failure():
    def fake_urlopen(url, timeout=0):
        if 'history' in str(url):
            return _Ctx(_history_case({'completed': False, 'status_str': 'error'}))
        return _Ctx({'prompt_id': 'p1'})

    with tempfile.TemporaryDirectory() as tmp:
        argv = ['run-workflow.py', '--workflow', str(ROOT / 'workflows' / 't2v_smoke_api.json'),
                '--record', str(Path(tmp) / 'r.json'), '--poll-interval', '0']
        with mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(run_module.urllib.request, 'urlopen', fake_urlopen):
            try:
                run_module.main()
            except SystemExit as exit_error:
                assert exit_error.code == 1
            else:
                raise AssertionError('expected a non-zero exit on failure')


def test_run_workflow_success_without_file_is_distinct():
    def fake_urlopen(url, timeout=0):
        if 'history' in str(url):
            return _Ctx({'p1': {'status': {'completed': True, 'status_str': 'success'},
                                'outputs': {}}})
        return _Ctx({'prompt_id': 'p1'})

    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / 'rec.json'
        argv = ['run-workflow.py', '--workflow', str(ROOT / 'workflows' / 't2v_smoke_api.json'),
                '--record', str(record), '--output-root', tmp, '--poll-interval', '0']
        with mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(run_module.urllib.request, 'urlopen', fake_urlopen):
            try:
                run_module.main()
            except SystemExit as exit_error:
                assert exit_error.code == 4
            else:
                raise AssertionError('expected exit 4 when no artifact exists')
        data = json.loads(record.read_text(encoding='utf-8'))
        assert data['result'] == 'success_without_output_file'
        assert data['video_present'] is False


class _Ctx:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self._payload


if __name__ == '__main__':
    tests = [(name, obj) for name, obj in sorted(globals().items()) if name.startswith('test_')]
    failures = []
    for name, func in tests:
        try:
            func()
            print(f'PASS {name}')
        except SystemExit as exit_error:
            # run_module.main() is exercised in-process; an expected exit code
            # must not abort the rest of the suite.
            if name.startswith('test_run_workflow'):
                failures.append((name, f'unexpected exit {exit_error.code}'))
                print(f'FAIL {name}: unexpected exit {exit_error.code}')
            else:
                print(f'PASS {name}')
        except Exception as error:  # noqa: BLE001
            failures.append((name, repr(error)))
            print(f'FAIL {name}: {error!r}')
    if failures:
        raise SystemExit(f'{len(failures)} failure(s)')
    print(f'{len(tests)} checks passed')
