"""Observe only original input-invalidation entry/dcbi/after at LR80241D88."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_di_burst_events_dolphin.py')
body = parent.read_text().replace('dolphin-di-burst-events', 'dolphin-di-cache-events').replace(
    'run_di_burst_events_disc_dolphin.ps1', 'run_di_cache_events_disc_dolphin.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
extra = '''
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'sites' for target in node.targets))
body = body.replace(ast.get_source_segment(body, node.value), repr([
    (10, 0x80212fa0, 0x28040000, 'DCInvalidateRange_input_entry'),
    (11, 0x80212fbc, 0x7c001bac, 'DCInvalidateRange_input_dcbi'),
    (12, 0x80212fc0, 0x38630020, 'DCInvalidateRange_input_after_dcbi')]))
body = body.replace('    pointer(code, 11, data_address | 0x40000000)',
    '    code.append(0x7d8802a6)\\n    pointer(code, 11, 0x80241d88)\\n    code.append(0x7c0c5840)\\n    filtered_branch = len(code)\\n    code.append(0)\\n    pointer(code, 11, data_address | 0x40000000)')
body = body.replace('    code[full_branch] =',
    '    code[filtered_branch] = (16 << 26) | (4 << 21) | (2 << 16) | ((restore - (text_address + filtered_branch * 4)) & 0xfffc)\\n    code[full_branch] =')
body = body.replace("'restore': restore})", "'restore': restore, 'filterBranch': text_address + filtered_branch * 4})")
'''
body = body.replace(marker, extra + '\n' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-cache-events/generation.json')
report = json.loads(path.read_text())
report['cacheParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'][-2] = 'Three non-branch replay observers save/restore r0/r11/r12/CR/MSR; exact LR80241D88 filter avoids all unrelated cache calls.'
report['limits'].append('Input cache entry/dcbi/after observations are original instructions; no cache no-op or pointer normalization injected.')
path.write_text(json.dumps(report, indent=2) + '\n')
