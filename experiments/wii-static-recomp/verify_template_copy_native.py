"""Compare full-module original memcpy with retained original Dolphin copy observations."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'template-copy-native'
measurement = private / 'dolphin-template-copy'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_template_copy_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_template_modes_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
exe = output / 'template-copy-probe'
assert build['baseLoweringSha256'] == sha(private / 'mass-code-write-observer/lowering.json')
assert build['executableSha256'] == sha(exe) and build['wrapperSha256'] == sha(output / 'template-wrapper.cpp')
assert build['probeSha256'] == sha(experiment / 'template_copy_probe.h') and build['scriptSha256'] == sha(experiment / 'build_template_copy_probe.py')
assert build['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(private / 'mass-code-write-observer/loader-bat-seed.h')
capture = json.loads((measurement / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
mode_capture = json.loads((private / 'dolphin-template-modes/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
mode_data = base64.b64decode(mode_capture['data'])
records = json.loads((measurement / 'generation.json').read_text())['records']
result = subprocess.run([str(exe), '--template-copy-check'], capture_output=True, text=True, timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout[-1000:], result.stderr[-1000:])
rows = result.stdout.splitlines()
assert len(rows) == 16
for record, line in zip(records, rows):
    index, returned, payload = line.split()
    assert int(index) == record['index'] and int(returned) == record['destination']
    offset = record['index'] * 736 + 192
    assert bytes.fromhex(payload) == data[offset:offset + 152]
    assert bytes.fromhex(payload) == mode_data[offset:offset + 152]
blocked = subprocess.run([str(exe), '--template-copy-ni-check'], capture_output=True, text=True, timeout=30)
(output / 'native-ni1-blocked.log').write_text(blocked.stdout + blocked.stderr)
assert blocked.returncode == 7 and 'NI unsupported FP before instruction address=800060f4 opcode=c824fff8' in blocked.stderr
report = {'result': 'ORIGINAL_MEMCPY_FULL_NATIVE_MODULE_MATCHES_16_DOLPHIN_TEMPLATE_COPIES',
          'cases': 16, 'copiedBytes': 2432, 'niProfile': 0,
          'ni1KnownGuard': '0x800060f4 lfd; no NI1 copy acceptance', 'buildSha256': sha(output / 'build.json'),
          'originalComparisonSha256': sha(measurement / 'comparison.json'), 'verifierSha256': sha(Path(__file__)),
          'modeComparisonSha256': sha(private / 'dolphin-template-modes/comparison.json'),
          'limits': ['Input fixtures patch backing before execution; not permission to mutate compiled code during runtime.',
                     'Original native memcpy return and152CPU-visible bytes match independent original executions at NI0.',
                     'NI1 test refuses original lfd before its effects; double bit-transfer semantics still need independent proof.',
                     'Full original template mutation loop/vector relocation/handler dispatch and post-clock endpoint remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original native memcpy NI0/fullmodule16cases/2432bytes matchDolphin; NI1 lfd guard/template adaptation pending')
