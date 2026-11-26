"""Compare positive DEC countdown to the original trace and check bounded timer state."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dec-clock-component'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prep = json.loads((output / 'preparation.json').read_text())
assert prep['preparerSha256'] == sha(experiment / 'prepare_dec_clock_component.py')
assert prep['adapterSha256'] == sha(experiment / 'dec_clock_adapter.h')
for path,digest in prep['headerHashes'].items():
    assert sha(Path(path)) == digest
host = output / 'dec-clock-contract.cpp'
host.write_bytes((experiment / 'dec_clock_contract.cpp').read_bytes())
exe = output / 'dec-clock-contract'
compiled = subprocess.run(['clang++','-std=c++20','-O2','-I',str(output),'-I',str(experiment),'-I',str(runtime / 'include'),
    str(host),str(runtime / 'src/core/event_scheduler.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=60)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0,compiled.stderr[-3000:]
result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr,result.stdout + result.stderr
oracle_path = root / 'dolphin-playrecord-dec-events-disc/playrecord-events-comparison.json'
oracle = json.loads(oracle_path.read_text())
actual = list(map(int,result.stdout.splitlines()[0].split()[1:]))
assert actual == oracle['dec']['countdown']
assert result.stdout.splitlines()[1] == 'DEC_CONTRACT reprogram-expiry-latch-wrap guards=7'
(output / 'verification.json').write_text(json.dumps({'result':'EXISTING_CLOCK_DEC_COUNTDOWN_ORIGINAL_MATCH_REPROGRAM_EXPIRY_CONTRACT_PASS',
    'verifierSha256':sha(Path(__file__)),'preparationSha256':sha(output / 'preparation.json'),
    'contractSha256':sha(experiment / 'dec_clock_contract.cpp'),'executableSha256':sha(exe),'oracleSha256':sha(oracle_path),
    'limits':['Six sampled positive counter values match original trace using disclosed shared scripted clock inputs.',
        'Expiry/reprogramming/latching/wrap tests are PC model contracts, not original IRQ/hardware observations.',
        'Future timer is armed without dec_irq_pending; expiry latches pending and keeps delivery guarded.',
        'No native boot/SDK callback completion yet; negative/zero writes unverified.']},indent=2) + '\n')
print('PASS existing ClockContext/counter/EventScheduler/six original DEC samples/reprogram-expiry-latch-wrap/7 guards; exception delivery unverified')
