"""Pin original NOP-store/copy data and NI state without enabling native writes."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_template_modes_dolphin.py'
body = verifier.read_text().replace('dolphin-template-modes', 'dolphin-nop-copy')
body = body.replace('run_template_modes_dolphin.ps1', 'run_nop_copy_dolphin.ps1')
body = body.replace('build_template_modes_dolphin.py', 'build_nop_copy_dolphin.py')
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-nop-copy')
generation = json.loads((output / 'generation.json').read_text())
assert generation['modeGeneratorSha256'] == hashlib.sha256((experiment / 'build_template_modes_dolphin.py').read_bytes()).hexdigest()
assert generation['storeAddress'] == 0x80211a30 and generation['storeTarget'] == 0x80211bf8
assert {row['value'] for row in generation['records']} == {0x60000000}
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_NOP_STORE_AND_TEMPLATE_COPY_NI0_NI1_32_CASES_MATCH'
report['modeVerifierSha256'] = hashlib.sha256(verifier.read_bytes()).hexdigest()
report['limits'] = ['OriginalNOPstore/memcpy32NI0-NI1fixtures, FPSCRpreserved and4864copiedbytes match.',
                    'NOPword remains original60000000; sourceexception-number word unmodified inthismeasurement.',
                    'Exact native attempt separately observed, but native NOP-write adaptation/full OS-vector loop still unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS32originalNOPstore/copycases/4864bytes; nativeNOPwrite remains blocked')
