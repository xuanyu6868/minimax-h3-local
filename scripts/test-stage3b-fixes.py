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


def test_install_script_uses_repo_lock_and_refuses_implicit_resolve():
    """The lock file belongs to this repo, and only -Relock may re-resolve."""
    text = (SCRIPTS / 'install-runtime.ps1').read_text(encoding='utf-8')
    # Located from the script, not from the runtime root, which is elsewhere.
    assert '$PSCommandPath' in text
    assert "Split-Path -Parent (Split-Path -Parent $PSCommandPath)" in text
    assert "'requirements.lock.txt'" in text
    # Missing lock file must be a hard failure rather than a silent re-resolve.
    assert 'Refusing to resolve dependencies implicitly' in text
    assert 'pass -Relock to create it' in text
    # Re-resolving requires the explicit switch and the constraint file.
    assert 'if ($Relock) {' in text
    assert 'Cannot relock: constraint file is missing' in text
    # The removed implicit branch must not come back.
    assert '$Relock -or -not (Test-Path $verifiedLock)' not in text


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


def test_ui_converter_keeps_autogrow_group_path():
    """Autogrow sockets must stay 'group.field', not a bare field name.

    Renaming them to 'ref_image_0' makes the frontend submit a flat key and the
    backend rejects it with "unexpected keyword argument".
    """
    ui_module = load('build-ui-workflow')
    api = {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': 'a.png'}},
        '5': {'class_type': 'MiniMaxH3ReferenceToVideo',
              'inputs': {'clip': ['2', 0], 'vae': ['3', 0], 'audio_vae': ['4', 0],
                         'prompt': 'x', 'width': 736, 'height': 416, 'length': 124,
                         'ref_image_size': 'match',
                         'ref_images.ref_image_0': ['1', 0],
                         'ref_audios.ref_audio_0': ['6', 0]}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'c', 'type': 'minimax'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'v'}},
        '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'a'}},
        '6': {'class_type': 'LoadAudio', 'inputs': {'audio': 't.wav'}},
    }
    ui = ui_module.build(api)
    assert ui_module.verify(ui) is True
    node = next(n for n in ui['nodes'] if n['type'] == 'MiniMaxH3ReferenceToVideo')
    names = [i['name'] for i in node['inputs']]
    assert 'ref_images.ref_image_0' in names
    assert 'ref_audios.ref_audio_0' in names
    assert 'ref_image_0' not in names, 'group path was stripped'
    assert 'ref_audio_0' not in names, 'group path was stripped'
    for entry in node['inputs']:
        if '.' in entry['name']:
            assert entry.get('shape') == 7, 'dynamic socket must be marked as a grid input'


def test_ui_verify_rejects_stripped_group_path():
    ui_module = load('build-ui-workflow')
    broken = {'nodes': [{'id': 5, 'type': 'MiniMaxH3ReferenceToVideo',
                         'inputs': [{'name': 'ref_image_0', 'type': 'IMAGE', 'link': 1}],
                         'outputs': [], 'widgets_values': []}], 'links': []}
    try:
        ui_module.verify(broken)
    except SystemExit:
        return
    raise AssertionError('verify() must reject a stripped Autogrow group path')


def test_api_builder_uses_zero_based_autogrow_slots():
    """The schema advertises range(max); the official template starts at 0."""
    api_module = load('build-h3-api-workflow')
    data = api_module.build(736, 416, 124, 20, 'p', 'u.safetensors', 'x',
                            ref_images=['a.png', 'b.png'], ref_audios=['t.wav'])
    keys = data['5']['inputs'].keys()
    assert 'ref_images.ref_image_0' in keys
    assert 'ref_images.ref_image_1' in keys
    assert 'ref_images.ref_image_1' in keys and 'ref_images.ref_image_2' not in keys
    assert 'ref_audios.ref_audio_0' in keys
    assert not any(k in keys for k in ('ref_image_0', 'ref_image_1')), 'flat key leaked into the API form'


def test_start_script_defaults_to_low_memory_preset():
    text = (SCRIPTS / 'start-comfyui.ps1').read_text(encoding='utf-8')
    assert '[switch]$EnablePinnedMemory' in text
    assert "if ($EnablePinnedMemory) { @() } else { @('--disable-pinned-memory') }" in text
    assert 'pinned_memory' in text
    # A pre-existing listener must never be adopted silently.
    assert 'Port 8188 is already in use' in text
    assert 'Get-NetTCPConnection' in text


def test_guard_rule_thresholds():
    guard = load('guard-memory')
    # Below the headroom floor interrupts immediately.
    decision = guard.evaluate({'committed_MiB': 40800.0, 'commit_limit_MiB': 41179.0},
                              0, 0.97, 512.0)
    assert decision['action'] == 'interrupt'
    # One high ratio sample is not enough; the second consecutive one is.
    first = guard.evaluate({'committed_MiB': 40100.0, 'commit_limit_MiB': 41179.0},
                           0, 0.97, 512.0)
    assert first['action'] == 'hold' and first['streak'] == 1
    second = guard.evaluate({'committed_MiB': 40200.0, 'commit_limit_MiB': 41179.0},
                            first['streak'], 0.97, 512.0)
    assert second['action'] == 'interrupt'
    # A dropped sample must never count as healthy headroom.
    missing = guard.evaluate(None, 1, 0.97, 512.0)
    assert missing['action'] == 'hold' and missing['streak'] == 0
    assert 'no usable sample' in missing['reason']


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
