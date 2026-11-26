"""Replay existing SI oracle on exact whole-startup STM objects with admission disabled."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_stm_ack_si_regression.py')
body = parent.read_text().replace('stm-irq-native-ack', 'mass-stm-startup-boot').replace("'attempt.json'", "'build.json'")
body = body.replace('NEW_ACK_OBJECTS_SI16', 'NEW_BOOT_STM_OBJECTS_SI16').replace('new ACK objects', 'new startup STM objects')
body = body.replace("host.write_text('#include ", "host.write_text('#include \"ipc_open_packet.h\"\\n#include ", 1)
marker = 'sources = [host,'
injection = "host.write_text(host.read_text() + '\\nnamespace nwii::runtime { void experiment_stm_submit(CPUContext&, uint32_t) { throw std::runtime_error(\"Unexpected STM submission in SI regression\"); } }\\n')\n"
assert body.count(marker) == 1
body = body.replace(marker, injection + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-stm-startup-boot/si-regression.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
