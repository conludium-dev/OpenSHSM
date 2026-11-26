"""Audit post-presentation drain latency; observer batches are drain calls, not host loops."""
from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parent / 'audit_stock_pe_cadence_live.py'
script = base.read_text().replace('window-pe-cadence', 'window-post-present')
script = script.replace('pe-cadence-live', 'post-present-live')
script = script.replace('PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED',
    'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED')
script = script.replace('hostPassesDeferred', 'drainCallsDeferred')
script = script.replace('copyHostPassStepMedian', 'copyDrainCallStepMedian')
script = script.replace('pe-cadence-audit.json', 'post-present-cadence-audit.json')
scope = {'__file__': str(Path(__file__).resolve())}
exec(compile(script, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
report.update(result='POST_PRESENT_OWNED_PE_DELAY_BRACKETS_AUDITED',
    baseAuditorSha256=hashlib.sha256(base.read_bytes()).hexdigest())
report['limits'].append('Observer batch counts FIFO drain calls; post-swap adds another call within one host loop. Do not equate drain index with host iteration.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
