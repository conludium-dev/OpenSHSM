"""Compare measured PI stores with native original instruction and vendor state."""
from pathlib import Path
import hashlib
import json
import subprocess
from pi_mask_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base, output = private / 'mass-mmio-observer', private / 'mass-pi-mask'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_pi_mask_dolphin.py')], check=True)
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, name in [('adapterSha256', 'pi_mask_adapter.h'), ('scriptSha256', 'build_pi_mask.py'),
                  ('lowererSha256', 'pi_mask_lowering.py'), ('baseBuilderSha256', 'build_branch.py'), ('probeSha256', 'pi_mask_probe.h')]:
    assert lowering[key] == sha(experiment / name)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
for name, digest in lowering['vendorSourceSha256'].items():
    assert digest == sha(upstream / name)
for name, digest in lowering['privateHeaderSha256'].items():
    assert digest == sha(output / name) == sha(base / name)
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert len(metadata['records']) == len(lowering['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe, policy = output / 'openshsm-mass-boot', private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
old_wrapper = (base / 'boot-wrapper.cpp').read_text()
main = 'int main(int argc, char** argv) {'
new_main = main + '\n    if (argc == 2 && std::string(argv[1]) == "--pi-mask-check") { return experiment_pi_mask_probe(); }'
assert (output / 'boot-wrapper.cpp').read_text() == '#include "pi_mask_probe.h"\n' + old_wrapper.replace(main, new_main)
oracle_path = private / 'dolphin-pi-mask/comparison.json'
oracle = json.loads(oracle_path.read_text())
native = subprocess.run([str(exe), '--pi-mask-check'], capture_output=True, text=True, timeout=30)
assert native.returncode == 0, (native.returncode, native.stdout, native.stderr)
(output / 'native-mask.log').write_text(native.stdout + native.stderr)
rows = [line.split()[1:] for line in native.stdout.splitlines() if line.startswith('PI_MASK_CASE ')]
assert len(rows) == len(oracle['observations']) == 32
for tokens, row in zip(rows, oracle['observations']):
    index, mask, fpscr, cause = map(int, tokens)
    assert index == row['index'] and mask == row['requestedMask'] == row['readbackMask']
    assert fpscr == (index // 16) * 4
    assert cause == row['causeBefore'] == row['causeAfter'] == 0x10000
assert 'PI_MASK_GUARDS 7\n' in native.stdout
stale = subprocess.run([str(exe), '--template-stale-check'], capture_output=True, text=True, timeout=30)
assert stale.returncode == 0 and stale.stdout == 'TEMPLATE_STALE_GUARDS 38\n'
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(private / 'mass-l2/boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
assert prefix.returncode == 7 and prefix.stdout == json.loads((private / 'mass-timebase/boot.json').read_text())['stdout']
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
needle = 'memory instruction=802175d4 address=cd000034 value=40000000 length=4 physical=d000034'
assert live.returncode == 7 and needle in live.stdout and needle in boot['stdout']
assert '[HW PI] INTMR change: 0x0 -> 0xf0' in live.stdout
(output / 'live-replay.log').write_text(live.stdout + live.stderr)
report = {'result': 'VENDOR_PI_MASK_NATIVE32_ORIGINAL_CASES_VERIFIED_DELIVERY_UNVERIFIED',
          'originalCases': 32, 'nativeOriginalInstructionCases': 32, 'refusalRollbackCases': 7, 'compiledStaleEntryRefusals': 38,
          'oracleSha256': sha(oracle_path), 'loweringSha256': sha(output / 'lowering.json'), 'bootSha256': sha(output / 'boot.json'),
          'nativeLogSha256': sha(output / 'native-mask.log'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Existing vendor PI atomics/dispatcher, no duplicate register store; strict original-caller/EE0/BAT profile.',
                     'Native fixtures seed measured cause10000; this is not accepted full-boot producer initialization.',
                     'Native mid-function entry executes one original store then next strict hardware guard; no full function proof.',
                     'Vendor cause default0 is unverified boot seed; asynchronous producers/external exceptions/full PI init not implemented.',
                     'NextCD000034 hardware access, whole vectors/table/post-clock state and original menu unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS existingPI-mask32original/native cases/7rollbackguards/38staleentries; nextCD000034 refused')
