"""Reuse exact template verification and require observed NI mode preservation."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_template_copy_dolphin.py'
body = verifier.read_text().replace('dolphin-template-copy', 'dolphin-template-modes')
body = body.replace('run_template_copy_dolphin.ps1', 'run_template_modes_dolphin.ps1')
body = body.replace('build_template_copy_dolphin.py', 'build_template_modes_dolphin.py')
body = body.replace('== 16', '== 32').replace('16 * 736', '32 * 736').replace('length * 16', 'length * 32')
body = body.replace("'cases': 16", "'cases': 32")
body = body.replace("print('PASS original store/memcpy16variants×152bytes=2432byte comparisons; native mutable templates/relocation pending')", '')
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-template-modes')
generation = json.loads((output / 'generation.json').read_text())
assert generation['baseGeneratorSha256'] == hashlib.sha256((experiment / 'build_template_copy_dolphin.py').read_bytes()).hexdigest()
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
for record in generation['records']:
    offset = record['index'] * 736
    before = struct.unpack_from('>Q', data, offset + 704)[0] & 0xffffffff
    after = struct.unpack_from('>Q', data, offset + 712)[0] & 0xffffffff
    assert before == after == record['ni'] * 4
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_STORE_MEMCPY_NI0_NI1_32_VARIANTS_BYTE_EXACT_FPSCR_PRESERVED'
report['baseVerifierSha256'] = hashlib.sha256(verifier.read_bytes()).hexdigest()
report['limits'] = ['32 original store/memcpy observations at explicit NI0/NI1; FPSCR preserved and152bytes exact per case.',
                    'Synthetic ordinary-RAM destination/cache/register setup; not full OS loop/vector relocation/dispatch.',
                    'Native NI1 still traps at original lfd; no generic bit-transfer or mutable-code adaptation accepted.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS32original store/memcpy NI0/NI1/4864bytes; FPSCR unchanged; nativeNI1 transfer guards pending')
