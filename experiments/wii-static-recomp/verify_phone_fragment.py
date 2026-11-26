"""Compare real phone frames with original PPC callback enabled and disabled."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from PIL import Image

private = Path('work/private-game/static-recomp')
generated = private / 'nwii-current'
exe = generated / 'openshsm-runtime-recomp-phone.exe'
prepared = Path('work/private-game/fresh Wii r86')
base = [str(exe), str(prepared / 'scene/entry_761')]
for option, relative in [('harry', 'harry/entry_114'), ('animations', 'harry/entry_111'),
                         ('audio', 'audio'), ('phone-ui', 'phone-ui/entry_1683'), ('font', 'fonts/font-eur.kft'),
                         ('phone-text', 'phone/wii-english.bin'), ('photos', 'photos')]:
    base += ['--' + option, str(prepared / relative)]
fixtures = [('focus-only', 'dd', []), ('off-right', 'ddr', [0]), ('off-left', 'ddl', [0]),
            ('right-left', 'ddrl', [0, 1]), ('left-right', 'ddlr', [0, 1]),
            ('other-settings', 'rdrdd', []), ('leave-return', 'ddluurddr', [0, 1])]
records = []
for name, keys, expected_values in fixtures:
    frames = []
    outputs = []
    fields_pair = []
    for enabled in (False, True):
        tag = 'ppc' if enabled else 'native'
        shot = private / ('phone-fragment-' + name + '-' + tag + '.ppm')
        command = base + (['--experimental-recomp-phone'] if enabled else [])
        command += ['--phone-screen', 'settings', '--phone-test-keys', keys, '--phone-test-at', '1.5',
                    '--phone-time', str(len(keys) + 3), '--shot', str(shot)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        shot.with_suffix('.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, (name, enabled, result.stdout, result.stderr)
        frame_lines = [line for line in result.stdout.splitlines() if 'gl_error=' in line]
        assert len(frame_lines) == 1, result.stdout
        fields = dict(item.split('=', 1) for item in frame_lines[0].split() if '=' in item)
        assert fields['gl_error'] == '0' and fields['torch_model'] == '0' and fields['ui_mode'] == '6', fields
        calls = re.findall(r'^SHSM_RECOMP_UI action=(\w+) prior=(\d+) result=(\d+) abi=(\d+) callbacks=(\d+)$',
                           result.stdout, re.MULTILINE)
        assert len(calls) == (len(expected_values) if enabled else 0), (name, enabled, calls)
        if enabled:
            assert [int(row[2]) for row in calls] == expected_values, (name, calls)
            assert all(row[3:] == ('1', '3') for row in calls), calls
            assert f'SHSM_RECOMP_SUMMARY calls={len(calls)} exit=0' in result.stdout
        with Image.open(shot) as image:
            assert image.size == (1280, 720)
            image.save(shot.with_suffix('.png'))
        frames.append(hashlib.sha256(shot.read_bytes()).hexdigest())
        outputs.append({'enabled': enabled, 'calls': calls, 'fields': fields})
        fields_pair.append(fields)
    assert frames[0] == frames[1], (name, frames)
    assert fields_pair[0] == fields_pair[1], (name, fields_pair)
    records.append({'fixture': name, 'keys': keys, 'originalValues': expected_values,
                    'frameSha256': frames[0], 'exactNativeFrameMatch': True, 'runs': outputs})
    print(name, 'original callback/state/GL0/exact native frame PASS', flush=True)

for arguments in [[], ['--experimental-recomp-phone'], ['--experimental-recomp-phone', '--experimental-recomp-phone', '--self-test']]:
    result = subprocess.run([str(exe), *arguments], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2, (arguments, result.returncode, result.stdout, result.stderr)

report = {'result': 'PASS', 'records': records, 'invalidInputs': 3,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256(Path('experiments/wii-static-recomp/runtime_phone.cpp').read_bytes()).hexdigest(),
          'generatedSha256': hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest(),
          'scope': 'Existing PhoneUI::key, original layout navigation, recompiled vibrate callback, existing state/bindings and real Windows OpenGL renderer.',
          'limits': ['SDL events injected by existing test timeline; not physical keyboard/controller acceptance.',
                     'Tone/volume retain native implementations; original audio callees not integrated.',
                     'Guest option state is marshalled per call from existing PhoneSettings; no original save service or Wii boot.',
                     'Muted diagnostic rendering does not verify audible audio, physical rumble or full phone completion.']}
(private / 'phone-fragment-frames.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:7paired phone renders,3invalid inputs; production runtime unchanged')
