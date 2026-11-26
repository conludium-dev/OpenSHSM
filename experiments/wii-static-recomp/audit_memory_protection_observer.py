"""Audit the exact refused MI access without broadening hardware permissions."""
from pathlib import Path
import hashlib
import json
import re

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-memory-protection-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
assert report['builderSha256'] == sha(experiment / 'observe_memory_protection_boot.py')
assert report['observerSha256'] == sha(experiment / 'memory_protection_observer.h')
assert report['parentBuilderSha256'] == sha(experiment / 'observe_fp64_boot.py')
assert report['baseBootSha256'] == sha(private / 'mass-audio-init-boot/boot.json')
assert report['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert report['logSha256'] == sha(output / 'boot.log')
assert report['diagnostic'] == 'MI_INIT_REFUSAL instruction=802186ac address=cc004020 physical=c004020 value=0 msr=2032 lr=802186a4 wimg=5 slot=1 width=2'
assert len(report['records']) == 125 and len(report['changes']) == 1
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in report['sourceHashes'].items():
    assert sha(Path(name)) == digest
row = next(row for row in report['records'] if row['file'] == 'output_63.cpp')
change = report['changes'][0]
source = Path(row['source']).read_text()
assert source.count(change['after']) == 1
assert source.replace(change['after'], change['before']) == Path(row['inputSource']).read_text()
assert sha(Path(row['inputSource'])) == row['inputSourceSha256']
log = (output / 'boot.log').read_text()
assert re.search(r'^BOOT_BOUNDARY pc=802186a4 lr=802186a4 msr=2032 calls=\d+ reason=BAT MMIO/locked-cache/unmapped backing access unavailable$', log, re.M)
assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
assert 'BOOT_FLUSH entries=1 phase=0 barriers=1' in log
(output / 'audit.json').write_text(json.dumps({'result': 'EXACT_MI_INIT_WRITE_REFUSAL_SAME_BOOT_GUARD_PASS',
    'observationSha256': sha(output / 'observation.json'), 'auditorSha256': sha(Path(__file__)),
    'limits': ['Exact instruction/value/address/mapping observed; no new hardware permission, native function completion or boot advance.']}, indent=2) + '\n')
print('PASS exact MI write802186AC→CC004020/value0; original boot refusal and DSP completion retained')
