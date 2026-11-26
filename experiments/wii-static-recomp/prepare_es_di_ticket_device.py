"""Specialize existing ES class in private experiment, not vendor/runtime registry."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-di-burst-cache-boot'
output = root / 'es-di-ticket-device'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_es_di_ticket_dolphin.py')], check=True)
build = json.loads((base / 'build.json').read_text())
for name in ('es_device.cpp', 'di_device.cpp', 'fs_device.cpp', 'stm_device.cpp'):
    path = base / name
    assert sha(path) == build['sourceHashes'][str(path)]
    (output / name).write_bytes(path.read_bytes())
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
(output / 'es_di_ticket_adapter.h').write_bytes((experiment / 'es_di_ticket_adapter.h').read_bytes())
path = output / 'es_device.cpp'
text = path.read_text()
assert text.count('#include "es_datadir_adapter.h"') == 1
text = text.replace('#include "es_datadir_adapter.h"', '#include "es_datadir_adapter.h"\n#include "es_di_ticket_adapter.h"')
marker = '    int32_t ioctlv(CPUContext& context, const IpcRequest& req) override {'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\n        if (req.ioctl_cmd == 0x1b) {\n            return experiment_es_di_ticket_write(context, req, title_, std::getenv("SHSM_ES_TICKET_PATH"));\n        }')
path.write_text(text)
(output / 'preparation.json').write_text(json.dumps({'preparerSha256': sha(Path(__file__)),
    'parentBuildSha256': sha(base / 'build.json'), 'adapterSha256': sha(experiment / 'es_di_ticket_adapter.h'),
    'sourceHashes': {str(path): sha(path) for path in output.glob('*.cpp')},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'limits': ['Same ES class/factory/shared kernel. Only strict measured1B added; old title/data-dir methods unchanged.',
        'Component preparation, not native PPC flush/submission/lifecycle completion.']}, indent=2) + '\n')
print('Prepared private existing ES class ticket-view specialization; no vendor or production changes')
