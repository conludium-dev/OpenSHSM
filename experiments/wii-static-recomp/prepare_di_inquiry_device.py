"""Add strict inquiry to existing private DI class; LAB metadata is not a game asset."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-es-di-ticket-boot'
output = root / 'di-inquiry-device'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_es_di_ticket_events_dolphin.py')], check=True)
build = json.loads((base / 'build.json').read_text())
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('di_device.cpp', 'es_device.cpp', 'fs_device.cpp', 'stm_device.cpp'):
    path = base / name
    assert sha(path) == build['sourceHashes'][str(path)]
    (output / name).write_bytes(path.read_bytes())
(output / 'di_inquiry_adapter.h').write_bytes((experiment / 'di_inquiry_adapter.h').read_bytes())
path = output / 'di_device.cpp'
text = path.read_text()
text = '#include "di_inquiry_adapter.h"\n' + text
marker = '    int32_t ioctl(CPUContext& context, const IpcRequest& request) override {'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\n        if (request.ioctl_cmd == 0x12) {\n            return experiment_di_inquiry_write(context, request, std::getenv("SHSM_DI_LAB_INQUIRY_PATH"));\n        }')
path.write_text(text)
capture_path = root / 'dolphin-es-di-ticket-events-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
metadata = base64.b64decode(capture['inquiryPhysical'])
assert len(metadata) == 32
(output / 'dolphin-lab-inquiry.bin').write_bytes(metadata)
(output / 'preparation.json').write_text(json.dumps({'preparerSha256': sha(Path(__file__)), 'parentBuildSha256': sha(base / 'build.json'),
    'captureSha256': sha(capture_path), 'metadataSha256': hashlib.sha256(metadata).hexdigest(),
    'sourceHashes': {str(path): sha(path) for path in output.glob('*.cpp')},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'limits': ['Only measured12 added to existing DI class/factory, other methods unchanged.',
        'Explicit captured Dolphin LAB drive metadata, not physical Wii identity or required original runtime asset/public-release dependency.',
        'Private CPU experiment only; production virtual-drive identity policy remains unresolved.']}, indent=2) + '\n')
print('Prepared existing DI inquiry specialization with explicitly labelled private Dolphin LAB metadata')
