"""Enable only original verified cold IPC control store in the existing startup."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_ipc_startup_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_ipc_control_backend.py')], check=True)
parent = experiment / 'observe_ipc_startup_boot.py'
body = parent.read_text().replace('mass-ipc-startup-observer', 'mass-ipc-startup-boot')
body = body.replace('ipc_startup_observer.h', 'ipc_startup_frontend.h')
body = body.replace('experiment_ipc_startup_observe_store', 'experiment_ipc_startup_store')
marker = "exec(compile(source, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
injection = '''entry_path = output / 'mass_boot.cpp'
entry = entry_path.read_text()
marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry.count(marker) == 1
entry_path.write_text(entry.replace(marker, marker + '\\n    nwii::runtime::experimentIpcStartup = !std::getenv("SHSM_IPC_STARTUP_DISABLED");'))
wrapper_path = output / 'boot-wrapper.cpp'
wrapper = wrapper_path.read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper.count(marker) == 1
wrapper = wrapper.replace(marker, marker + '\\n    std::cout << "BOOT_IPC_STARTUP writes=" << nwii::runtime::experimentIpcStartupWrites << " control=" << std::hex << nwii::runtime::hw::experiment_ipc_snapshot().ppcControl << std::dec << "\\\\n";')
wrapper_path.write_text('#include "ipc_startup_frontend.h"\\n' + wrapper)
'''
body = body.replace(marker, "source = source.replace(\"exec(compile(body, str(parent), 'exec'), {'__file__': __file__})\", \"body = body.replace(\\\"for row in build['records']:\\\", \" + " + repr(repr(injection)) + " + \" + \\\"for row in build['records']:\\\", 1)\\nexec(compile(body, str(parent), 'exec'), {'__file__': __file__})\")\n" + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-ipc-startup-boot/build.json')
report = json.loads(path.read_text())
report['originalProofSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/dolphin-ipc-startup/comparison.json').read_bytes()).hexdigest()
report['backendProofSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/ipc-control-backend/comparison.json').read_bytes()).hexdigest()
report['entrySha256'] = hashlib.sha256((path.parent / 'mass_boot.cpp').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
