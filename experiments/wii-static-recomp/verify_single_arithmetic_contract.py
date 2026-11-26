"""Check atomic refusals and sanitizer execution on all original input matrices."""
from pathlib import Path
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-single-arithmetic')
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
includes = ['-I',str(experiment),'-I','work/private-game/static-recomp/mass-ni-guard','-I',str(runtime / 'include')]
for source,name in [('single_arithmetic_contract.cpp','arithmetic-contract'),('single_arithmetic_probe.cpp','arithmetic-ubsan')]:
    exe = output / name
    result = subprocess.run(['clang++','-std=c++20','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',*includes,
        str(experiment / source),'-o',str(exe)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0,result.stderr
    if name == 'arithmetic-contract':
        result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
        assert result.returncode == 0 and result.stdout == 'SINGLE_ARITHMETIC_CONTRACT guards=20\n' and not result.stderr,result
    else:
        lines = []
        for directory in (output,output.with_name('dolphin-single-arithmetic-targeted')):
            generation = json.loads((directory / 'generation.json').read_text())
            lines.extend(f"{row['a']} {row['b']} {row['initialFpscr'] | row['ni'] * 4} {row['opcode']}\n" for row in generation['records'])
        result = subprocess.run([str(exe)],input=''.join(lines),capture_output=True,text=True,timeout=30)
        assert result.returncode == 0 and not result.stderr and len(result.stdout.splitlines()) == 2304,result.stderr
print('PASS arithmetic20 atomic refusals/UBSan2304 original input cases; compiler int128 portability unverified')
