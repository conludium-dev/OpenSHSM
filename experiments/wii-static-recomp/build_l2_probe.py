"""Extend existing accurate-cache boot observer to the original L2 polling branch."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/build_dcache_probe.py')
body = base.read_text()
body = body.replace('dolphin-dcache-probe', 'dolphin-l2-probe')
body = body.replace('run_dcache_probe.ps1', 'run_l2_probe.ps1')
body = body.replace('endpoint = 0x802106c0', 'endpoint = 0x80213534')
body = body.replace("assert opcode >> 26 == 31 and ((opcode >> 1) & 1023) == 339\nassert ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5) == 1017", 'assert opcode == 0x4082fff8')
body = body.replace("completion = code[-3:]", """first_float = next(i for i, op in enumerate(code) if op >> 26 == 54)
code[first_float:first_float] = [(31 << 26) | (11 << 21) | (83 << 1),
                               namespace['dform'](24, 11, 11, 0x2000),
                               (31 << 26) | (11 << 21) | (146 << 1)]
completion = code[-3:]""")
body = body.replace('code += completion', "code.extend([namespace['spr'](11, 1017), namespace['dform'](36, 11, 12, 24)])\ncode += completion")
body = body.replace('Private measurement branch before L2CR read', 'Private measurement branch before L2 polling bne')
exec(compile(body, str(base), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-l2-probe/generation.json')
report = json.loads(output.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['scope'] += '; collector enables FP after original MSR snapshot for FPR observation.'
output.write_text(json.dumps(report, indent=2) + '\n')
