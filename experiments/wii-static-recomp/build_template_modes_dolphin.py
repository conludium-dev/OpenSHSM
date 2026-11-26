"""Reuse the store/copy fixture with explicit NI0/NI1 and measured FPSCR."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_template_copy_dolphin.py'
body = builder.read_text().replace('dolphin-template-copy', 'dolphin-template-modes')
body = body.replace('16 * stride', '32 * stride').replace('range(16)', 'range(32)')
body = body.replace('0x38600000 | index', '0x38600000 | (index & 15)')
body = body.replace("'index': index, 'value':", "'index': index, 'ni': index // 16, 'value':")
needle = '    pointer(code, 30, 0xc0000000 + result_base + index * stride)'
body = body.replace(needle, needle + '''
    code.extend([dform(50, 31, 30, 40), (63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    if index >= 16:
        code.append(branch(base + len(code) * 4, 0x80210830, True))''')
body = body.replace('code.append(dform(36, 0, 30, 24))', '''code.append(dform(36, 0, 30, 24))
code.extend([(63 << 26) | (583 << 1), dform(54, 0, 30, 704)])''')
body = body.replace('pointer(code, 0, 0xc001cafe)', '''code.extend([(63 << 26) | (583 << 1), dform(54, 0, 30, 712)])
pointer(code, 0, 0xc001cafe)''')
body = body.replace('run_template_copy_dolphin.ps1', 'run_template_modes_dolphin.ps1')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-template-modes')
path = output / 'generation.json'
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original store/memcpy/NI setter unchanged; explicit NI0/NI1, pre/post FPSCR observations, synthetic ordinary-RAM copy fixtures.'
report['limits'] = ['Full OS loop, real exception-vector destinations/relocation/dispatch and physical Wii timing unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Generated32template-copy cases with explicit NI0/NI1 and pre/post FPSCR')
