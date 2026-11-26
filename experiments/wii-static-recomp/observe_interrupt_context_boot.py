"""Extend the retained read-only observer with actual context and SI callback memory."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_interrupt_enable_boot.py')
body = parent.read_text().replace('mass-interrupt-enable-observer', 'mass-interrupt-context-observer')
body = body.replace('interrupt_enable_observer.h', 'interrupt_context_observer.h')
body = body.replace('experiment_interrupt_enable_observe', 'experiment_interrupt_context_observe')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-interrupt-context-observer/build.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['sourceHashes']['experiments/wii-static-recomp/interrupt_enable_observer.h'] = hashlib.sha256(Path('experiments/wii-static-recomp/interrupt_enable_observer.h').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
