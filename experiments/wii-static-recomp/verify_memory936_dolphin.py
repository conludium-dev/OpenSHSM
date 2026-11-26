"""Check the new MEM2 window against original function endpoints, not guessed native output."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_memory_protection_dolphin.py'
body = parent.read_text().replace('dolphin-memory-protection', 'dolphin-memory936')
body = body.replace('build_memory_protection_dolphin.py', 'build_memory936_dolphin.py')
body = body.replace('run_memory_protection_dolphin.ps1', 'run_memory936_dolphin.ps1')
assert body.count('0x9300007f') == 1
body = body.replace('0x9300007f', '0x930000ff')
body = body.replace('ORIGINAL_MEMORY_PROTECTION8_FIRST8_REPEAT_MI_TABLE_QUEUE_BAT_PASS',
    'ORIGINAL_MEMORY936_8_FIRST8_REPEAT_MI_TABLE_QUEUE_BAT_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-memory936')
generation = json.loads((output / 'generation.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert generation['profileGeneratorSha256'] == sha(experiment / 'build_memory_protection_dolphin.py')
assert generation['loaderProofSha256'] == sha(Path('work/private-game/static-recomp/dolphin-loader-snapshot/comparison.json'))
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['parentVerifierSha256'] = sha(parent)
report['originalBehavior'] = 'BATConfig selects fn_802181D0 for936end; DBAT7 cached93000000..937FFFFF (8MB).'
report['limits'].append('Prepared whole-function fixture, not original retail boot. New window follows owned-DOL lis93/addiFF at80218248/4C.')
path.write_text(json.dumps(report, indent=2) + '\n')
