"""Validate routed source/object scope and the measured cache-aware frontend without claiming DCE boot."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-memory')
oracle = Path('work/private-game/static-recomp/dolphin-coherence-probe')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['result'] == 'COMPILED_NOT_BOOT_VERIFIED' and lowering['filesCompiled'] == 125
assert lowering['headerSha256'] == sha(experiment / 'memory_frontend.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_memory_frontend.py')
count = 0
for record in lowering['records']:
    source = output / record['file']
    prior = Path(record['inputDirectory']) / record['file']
    assert record['sourceSha256'] == sha(source) and record['inputSha256'] == sha(prior)
    assert record['objectSha256'] == sha(output / (record['file'] + '.o'))
    old, new = prior.read_text().splitlines(), source.read_text().splitlines()
    assert len(old) == len(new)
    changes = {change['line'] - 1: change for change in record['changes']}
    assert len(changes) == sum(before != after for before, after in zip(old, new))
    for index, (before, after) in enumerate(zip(old, new)):
        if before != after:
            assert changes[index]['before'] == before and changes[index]['after'] == after
    assert 'ctx.mmu.' not in source.read_text() and 'ctx.psq_load(' not in source.read_text() and 'ctx.psq_store(' not in source.read_text()
    count += len(changes)
assert count == lowering['memoryRoutingLines'] == 511904
exe = output / 'memory-frontend-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'memory_frontend_probe.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
(output / 'probe-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
observed = list(map(int, result.stdout.splitlines()[0].split()))
comparison = json.loads((oracle / 'comparison.json').read_text())
assert observed == comparison['dolphin']['true']
assert 'FRONTEND_CHECKS crossLine integer float pairedFloat eviction strictIO quantizedRefusal PASS' in result.stdout
boot = json.loads((output / 'boot.json').read_text())
assert boot['result'] == 'PRE_DCE_BOOT_MATCHES_BASELINE' and boot['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert boot['loweringSha256'] == sha(output / 'lowering.json')
subprocess.run(['python3', str(experiment / 'audit_coherence.py')], check=True)
report = {'result': 'FRONTEND_COMPILED_AND_BOUNDED_VERIFIED', 'filesCompiledAndLinked': 125, 'routedLines': count,
          'accurateOracleFiveSamplesMatch': True, 'preDceBaselineMatches': True, 'dceAccepted': False,
          'sourceSha256': sha(experiment / 'memory_frontend.h'), 'probeSourceSha256': sha(experiment / 'memory_frontend_probe.cpp'),
          'probeExeSha256': sha(exe), 'limits': ['32KiB/128sets/8ways/32B lines with tree replacement; eviction checked locally, not against a Dolphin conflict-set trace.',
                     'Integer/float/paired float memory routing compiled module-wide; quantized paired formats refuse execution pending verification.',
                     'DCE gate remains closed; no cache-enabled original bootstrap, DMA consumer, OS/IOS/GX/menu/scene acceptance.',
                     'Canonical MEM1/MEM2 aliases only; full BAT/page faults, locks and physical timing remain unimplemented.'],
          'next': 'Validate conflict-set replacement and cache-aware original-function execution, then accept DCE and verify the next boot boundary against an accurate-cache CPU-visible snapshot.'}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('BOUNDED PASS:125objects/511904routes/accurate5samples/preDCEboot; full cache-enabled bootstrap pending')
