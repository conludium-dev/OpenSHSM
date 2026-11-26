"""Capture both cached runtime wait-queue edits and uncached IOS packet after CPU wakeup."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_irq_dolphin.py')
source = parent.read_text().replace('dolphin-stm-irq', 'dolphin-stm-irq-cache')
source = source.replace('run_stm_irq_dolphin.ps1', 'run_stm_irq_cache_dolphin.ps1')
marker = '''    for byte_offset in range(0, 64, 4):
        code.extend([dform(32, 0, 26, byte_offset), dform(36, 0, 30, 192 + byte_offset)])'''
assert source.count(marker) == 1
extra = '''
    pointer(code, 11, physical | 0x80000000)
    for byte_offset in range(0, 64, 4):
        code.extend([dform(32, 0, 11, byte_offset), dform(36, 0, 30, 256 + byte_offset)])'''
source = source.replace(marker, marker + extra)
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-irq-cache/generation.json')
report = json.loads(path.read_text())
report['cacheParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Uncached packet192..255 and cached packet256..319: runtime queue edits may be dirty, not IOS-visible.')
path.write_text(json.dumps(report, indent=2) + '\n')
