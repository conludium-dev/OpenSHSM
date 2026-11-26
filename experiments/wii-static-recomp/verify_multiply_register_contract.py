"""Check new opcode profile refusals and UB-free execution on all captured inputs."""
from pathlib import Path
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/multiply-register-component')
subprocess.run(['python3',str(experiment / 'prepare_multiply_register_component.py')],check=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
includes = ['-I',str(output),'-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard','-I',str(runtime / 'include')]
for source,name in [(experiment / 'multiply_register_contract.cpp','contract'),(output / 'multiply-register-probe.cpp','ubsan-probe')]:
    exe = output / name
    result = subprocess.run(['clang++','-std=c++20','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',*includes,str(source),'-o',str(exe)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0,result.stderr
    if name == 'contract':
        result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
        assert result.returncode == 0 and result.stdout == 'MULTIPLY_REGISTER_CONTRACT guards=12\n' and not result.stderr,result
    else:
        lines = []
        for directory in ('dolphin-multiply-register','dolphin-multiply-register-targeted'):
            rows = json.loads((output.parent / directory / 'generation.json').read_text())['records']
            lines.extend(f"{r['a']} {r['b']} {r['initialFpscr'] | r['ni'] * 4} {r['opcode']}\n" for r in rows)
        result = subprocess.run([str(exe)],input=''.join(lines),capture_output=True,text=True,timeout=30)
        assert result.returncode == 0 and not result.stderr and len(result.stdout.splitlines()) == 2304,result.stderr
print('PASS multiply-register12 atomic refusals/UBSan2304 cases; no full FPU/platform claim')
