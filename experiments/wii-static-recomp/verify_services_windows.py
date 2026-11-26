"""Cross-check the service probe on Windows and assemble independent PPC reference functions."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

output = Path('work/private-game/static-recomp/phone-services')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
zig = 'C:/OpenSHSM-lab/work/research/zig/zig-x86_64-windows-0.14.1/zig.exe'
oracle_path = output / 'execution.json'
oracle = json.loads(oracle_path.read_text())
assert oracle['result'] == 'PASS' and oracle['cases'] == 744
assert oracle['generatedSha256'] == hashlib.sha256((output / 'selected.cpp').read_bytes()).hexdigest()
snapshots = output / 'native-snapshots.txt'
assert oracle['nativeSnapshotsSha256'] == hashlib.sha256(snapshots.read_bytes()).hexdigest()
exe = output / 'services-host-windows.exe'
result = subprocess.run([zig, 'c++', '-std=c++20', '-O2', '-include', 'bit', '-target', 'x86_64-windows-gnu',
                         '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(upstream / 'nWiiAnalyzer/include'),
                         'experiments/wii-static-recomp/services_host.cpp', str(output / 'selected.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), '-o', str(exe)],
                         capture_output=True, text=True, timeout=240)
(output / 'windows-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
request = ''.join(' '.join(map(str, record['input'])) + '\n' for record in oracle['records'])
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], input=request,
                         capture_output=True, text=True, timeout=90)
(output / 'windows-snapshots.txt').write_text(result.stdout)
assert result.returncode == 0, result.stderr[-4000:]
assert result.stdout.splitlines() == snapshots.read_text().splitlines(), 'Windows register/memory snapshots differ from verified original PPC oracle'
assembly = Path('work/private-game/static-recomp/dtk-output/asm/auto_03_800E6590_text.s').read_text()
references = []
for function in ('fn_800ED314', 'fn_800ED3C8'):
    body = assembly.split('.fn ' + function + ', global\n')[1].split('.endfn ' + function)[0]
    body = re.sub(r'\br(\d+)\b', r'\1', body)
    source = output / (function + '-reference.s')
    obj = output / (function + '-reference.o')
    source.write_text('.text\n.globl ' + function + '\n.type ' + function + ',@function\n' + function + ':\n' +
                       body + '\n.size ' + function + ',.-' + function + '\n')
    result = subprocess.run([zig, 'cc', '-target', 'powerpc-freestanding', '-c', str(source), '-o', str(obj)],
                             capture_output=True, text=True, timeout=120)
    (output / (function + '-assembly.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (function, result.stderr)
    references.append({'function': function, 'objectSha256': hashlib.sha256(obj.read_bytes()).hexdigest()})
report = {'result': 'PASS', 'cases': 744, 'target': 'x86_64-windows-gnu',
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'originalOracleSha256': hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
          'generatedSha256': oracle['generatedSha256'], 'references': references,
          'limits': oracle['limits'] + ['PPC reference objects support ISA/boundary/relocation diffs, not host-to-PPC matching.']}
(output / 'windows.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:744Windows service-control snapshots match original oracle;2PPC reference functions assembled')
