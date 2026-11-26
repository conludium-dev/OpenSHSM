"""Add DEC ownership fields to the existing private ClockContext; vendor untouched."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-seek-boot'
output = root / 'dec-clock-component'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
for path in base.glob('*.h'):
    assert sha(path) == build['headerHashes'][str(path)]
    (output / path.name).write_bytes(path.read_bytes())
path = output / 'timebase_adapter.h'
text = path.read_text()
marker = '    bool scriptedClock = false;'
assert text.count(marker) == 1
path.write_text(text.replace(marker,'    bool decCounterArmed = false;\n    uint64_t decPollEvent = 0;\n' + marker))
(output / 'dec_clock_adapter.h').write_bytes((experiment / 'dec_clock_adapter.h').read_bytes())
(output / 'preparation.json').write_text(json.dumps({'preparerSha256':sha(Path(__file__)),
    'parentBuildSha256':sha(base / 'build.json'),'adapterSha256':sha(experiment / 'dec_clock_adapter.h'),
    'headerHashes':{str(path):sha(path) for path in output.glob('*.h')},
    'limits':['Existing ClockContext and CPUContext dec_value/dec_written_tb/dec_irq_pending reused.',
        'Only armed/event ownership added; same timebase source/EventScheduler, no thread or second clock.',
        'Positive writes only; zero/negative/latched IRQ writes and DEC exception delivery remain guarded.']},indent=2) + '\n')
