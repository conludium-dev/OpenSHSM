"""Extend the existing private ES class with only the observed LAB ES16 shape."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-di-inquiry-boot'
output = root / 'es-consumption-device'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_es_consumption_dolphin.py')], check=True)
build = json.loads((base / 'build.json').read_text())
for name in ('es_device.cpp', 'di_device.cpp', 'fs_device.cpp', 'stm_device.cpp'):
    path = base / name
    assert sha(path) == build['sourceHashes'][str(path)]
    (output / name).write_bytes(path.read_bytes())
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
(output / 'es_consumption_adapter.h').write_bytes((experiment / 'es_consumption_adapter.h').read_bytes())
path = output / 'es_device.cpp'
text = path.read_text()
assert text.count('#include "es_di_ticket_adapter.h"') == 1
text = text.replace('#include "es_di_ticket_adapter.h"', '#include "es_di_ticket_adapter.h"\n#include "es_consumption_adapter.h"')
marker = '    int32_t ioctlv(CPUContext& context, const IpcRequest& req) override {'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\n        if (req.ioctl_cmd == 0x16) {\n            return experiment_es_consumption_write(context, req, title_, std::getenv("SHSM_ES_TICKET_PATH"));\n        }')
path.write_text(text)
(output / 'preparation.json').write_text(json.dumps({'preparerSha256': sha(Path(__file__)),
    'parentBuildSha256': sha(base / 'build.json'), 'adapterSha256': sha(experiment / 'es_consumption_adapter.h'),
    'sourceHashes': {str(path): sha(path) for path in output.glob('*.cpp')},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'limits': ['Same existing ES class/factory/kernel; only exact measured LAB ES16 branch added.',
        'Requires explicit SHSM_ES_LAB_CONSUMPTION=1; not physical IOS consumption policy or native PPC completion.']}, indent=2) + '\n')
print('Prepared bounded existing ES16 device; vendor and production unchanged')
