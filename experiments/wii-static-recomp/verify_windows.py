"""Compile the same unmodified generated functions for native Windows x86-64 and PPC reference assembly."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

private = Path('work/private-game/static-recomp')
generated = private / 'nwii-current'
tools = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
zig = 'C:/OpenSHSM-lab/work/research/zig/zig-x86_64-windows-0.14.1/zig.exe'
executable = generated / 'probe-host-windows.exe'
command = [zig, 'c++', '-std=c++20', '-O2', '-include', 'bit', '-target', 'x86_64-windows-gnu',
           '-I', str(tools / 'nWiiRuntime/include'), 'experiments/wii-static-recomp/probe_bridge.cpp',
           'experiments/wii-static-recomp/probe_host.cpp', str(generated / 'selected.cpp'), '-o', str(executable)]
build = subprocess.run(command, capture_output=True, text=True, timeout=600)
(private / 'windows-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
oracle_path = private / 'execution-unicorn-vs-nwii.json'
oracle = json.loads(oracle_path.read_text())
request = ''.join(f"{row['prior']} {row['direction']}\n" for row in oracle['records'])
result = subprocess.run([str(executable)], input=request, capture_output=True, text=True, timeout=90)
(private / 'windows-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
expected = [[row['prior'], row['direction'], row['ppcValue'], 1, 3, 0, 1] for row in oracle['records']]
assert rows == expected
assembly_path = private / 'dtk-output/asm/auto_03_800F2228_text.s'
assembly = assembly_path.read_text().split('.fn fn_800F3E60, global\n')[1].split('.endfn fn_800F3E60')[0]
assembly = re.sub(r'\br(\d+)\b', r'\1', assembly)
reference = generated / 'reference-roundtrip.s'
reference.write_text('.text\n.globl fn_800F3E60\n.type fn_800F3E60,@function\nfn_800F3E60:\n' +
                     assembly + '\n.size fn_800F3E60,.-fn_800F3E60\n')
ppc_object = generated / 'reference-roundtrip.o'
assembly_build = subprocess.run([zig, 'cc', '-target', 'powerpc-freestanding', '-c', str(reference), '-o', str(ppc_object)],
                                capture_output=True, text=True, timeout=120)
(private / 'ppc-assembly-build.log').write_text(assembly_build.stdout + assembly_build.stderr)
assert assembly_build.returncode == 0, assembly_build.stderr
report = {'result': 'PASS', 'cases': len(rows), 'target': 'x86_64-windows-gnu',
          'executableSha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
          'originalOracleSha256': hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
          'generatedSha256': hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest(),
          'ppcReferenceObjectSha256': hashlib.sha256(ppc_object.read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Standalone experimental host calls actual PhoneSettings header and compiled original PPC code; not the live OpenSHSM SDL executable.',
                     'PPC reference reassembly is an ISA/boundary/relocation check for objdiff, not a comparison of x86 host code to PPC machine code.']}
(private / 'execution-windows-vs-original.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', len(rows), 'Windows x86-64 original-function roundtrips; PPC reference assembled')
