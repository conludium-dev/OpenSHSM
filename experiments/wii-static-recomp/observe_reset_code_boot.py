"""Reuse the read observer without relaxing PI access."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/observe_exi_ri_boot.py')
body = parent.read_text().replace('mass-memory-protection-boot', 'mass-uart-ri-boot').replace('mass-exi-ri-observer', 'mass-reset-code-observer')
body = body.replace('output_62.cpp', 'output_63.cpp').replace('func_8020E310', 'func_802194E0')
body = body.replace('exi_ri_observer.h', 'reset_code_observer.h').replace('experiment_exi_ri_observe', 'experiment_reset_code_observe')
body = body.replace('EXI_RI_REFUSAL', 'RESET_CODE_REFUSAL')
body = body.replace("'SHSM_MI_NO_SIZE_FIXTURE')", "'SHSM_MI_NO_SIZE_FIXTURE', 'SHSM_RI_UART_DISABLED')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-reset-code-observer/observation.json')
report = json.loads(path.read_text())
report['riObserverBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
