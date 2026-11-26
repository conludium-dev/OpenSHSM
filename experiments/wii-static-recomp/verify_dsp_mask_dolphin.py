"""Validate whole original DSP mask block, reusing read capture provenance."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_dsp_read_dolphin.py'
body = verifier.read_text().replace('dsp-read', 'dsp-mask').replace('dsp_read_dolphin', 'dsp_mask_dolphin')
body = body.replace('offset - 4', 'offset - 0x3c').replace('0xA0A5500A', '0x3CA0CC00').replace('0x802176F4', '0x802176EC')
body = body.replace("'ni': record['ni']", "'ni': record['ni'], 'softwareMask': record['softwareMask'], 'before': struct.unpack_from('>I', row, 32)[0], 'after': struct.unpack_from('>I', row, 28)[0]")
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-dsp-mask')
path = output / 'comparison.json'
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
assert generation['readGeneratorSha256'] == sha(experiment / 'build_dsp_read_dolphin.py')
assert generation['exitPatchAddress'] == 0x80217728
previous = 0x0804
for row in report['observations']:
    bits = row['index'] & 7
    expected = 0x0804 | (0x10 if bits & 4 else 0) | (0x40 if bits & 2 else 0) | (0x100 if bits & 1 else 0)
    assert row['before'] == previous
    assert row['value'] == row['after'] == expected
    assert row['causeBefore'] == row['causeAfter'] == 0x10000
    previous = expected
report['result'] = 'ORIGINAL_DSP_MASK_BLOCK16_CASES_PASS'
report['baseVerifierSha256'] = sha(verifier)
report['limits'] = ['Original read/modify/write block with8software mask combinations, NI0/NI1, no pending DSP sources.',
                    'Unseeded Dolphin loader state; no preceding full startup, general DSP/audio/DMA/IRQ or physical Wii.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 whole original DSP mask block, all8 masks/NI0-NI1/PI unchanged')
