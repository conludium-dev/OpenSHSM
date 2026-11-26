"""Pin reset-store oracle and verify prior IDs, copied bytes and NI state."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_template_copy_dolphin.py'
body = verifier.read_text().replace('dolphin-template-copy', 'dolphin-reset-copy')
body = body.replace('run_template_copy_dolphin.ps1', 'run_reset_copy_dolphin.ps1')
body = body.replace('build_template_copy_dolphin.py', 'build_reset_copy_dolphin.py')
body = body.replace('== 16', '== 32').replace('16 * 736', '32 * 736').replace('length * 16', 'length * 32')
body = body.replace("'cases': 16", "'cases': 32")
body = body.replace("print('PASS original store/memcpy16variants×152bytes=2432byte comparisons; native mutable templates/relocation pending')", '')
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-reset-copy')
generation = json.loads((output / 'generation.json').read_text())
assert generation['baseGeneratorSha256'] == hashlib.sha256((experiment / 'build_template_copy_dolphin.py').read_bytes()).hexdigest()
assert (generation['storeAddress'], generation['storeOpcode'], generation['storeTarget'], generation['exitPatchAddress']) == (0x80211b0c, 0x937c0000, 0x80211c08, 0x80211b10)
assert len({(row['ni'], row['priorValue']) for row in generation['records']}) == 32
capture = json.loads((output / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
for record in generation['records']:
    offset = record['index'] * 736
    assert record['value'] == 0x38600000
    assert struct.unpack_from('>I', data, offset + 36)[0] == record['priorValue'] == 0x38600000 | (record['index'] & 15)
    before = struct.unpack_from('>Q', data, offset + 704)[0] & 0xffffffff
    after = struct.unpack_from('>Q', data, offset + 712)[0] & 0xffffffff
    assert before == after == record['ni'] * 4
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_RESET_STORE_PRIOR_ID0_15_NI0_NI1_COPY_MATCH'
report['baseVerifierSha256'] = hashlib.sha256(verifier.read_bytes()).hexdigest()
report['limits'] = ['32original reset-store fixtures, prior-ID readback, FPSCRpreservation and4864copiedbytes verified inDolphin.',
                    'Synthetic cache/register/ordinary-RAM destinations, not full OS loop, real vectors or relocated dispatch.',
                    'No native reset allowance or physical Wii timing verified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS32originalreset/prior-ID/copycases/4864bytes; FPSCRpreserved')
