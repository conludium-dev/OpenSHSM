"""Verify original AI mask block and retained capture provenance."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
verifier = experiment / 'verify_dsp_read_dolphin.py'
body = verifier.read_text().replace('dsp-read', 'ai-mask').replace('dsp_read_dolphin', 'ai_mask_dolphin')
body = body.replace('offset - 4', 'offset - 0x28').replace('0xA0A5500A', '0x54800211').replace('0x802176F4', '0x8021772C').replace('0xCC00500A', '0xCD006C00')
body = body.replace("'ni': record['ni']", "'ni': record['ni'], 'softwareMask': record['softwareMask'], 'before': struct.unpack_from('>I', row, 32)[0], 'after': struct.unpack_from('>I', row, 28)[0]")
exec(compile(body, str(verifier), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-ai-mask')
path = output / 'comparison.json'
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
assert generation['readGeneratorSha256'] == sha(experiment / 'build_dsp_read_dolphin.py')
assert generation['exitPatchAddress'] == 0x80217754
previous = report['observations'][0]['before']
for row in report['observations']:
    expected = (row['before'] & 0xffffffd3) | (4 if row['index'] & 1 else 0)
    assert row['before'] == previous and row['value'] == expected
    assert row['causeBefore'] == row['causeAfter'] == 0x10000
    previous = row['after']
report['result'] = 'ORIGINAL_WII_AI_MASK_BLOCK16_OBSERVATIONS_VALIDATED'
report['baseVerifierSha256'] = sha(verifier)
report['limits'] = ['Original Wii CD006C00 block, two mask states/NI0-NI1, unseeded loader AI state.',
                    'No sample playback/rate/timer/pending IRQ/full preceding startup or physical Wii equivalence.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Original AI masks observed:', [(row['before'], row['value'], row['after']) for row in report['observations'][:4]])
