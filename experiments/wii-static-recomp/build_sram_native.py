"""Compile whole original SRAM initialization with the shared EXI DMA profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_query_native.py'
body = parent.read_text().replace('si-query-native', 'sram-native').replace('si-query-host', 'sram-host').replace('si-query-probe', 'sram-probe')
body = body.replace('verify_si_query_dolphin.py', 'verify_sram_dolphin.py').replace('dolphin-si-query-callback/comparison.json', 'dolphin-sram/comparison.json')
body = body.replace('si_query_frontend.h', 'sram_frontend.h').replace('si_query_host.cpp', 'sram_host.cpp')
body = body.replace('experiment_si_query_', 'experiment_sram_')
body = body.replace('si_idle_backend.h', 'exi_getid_backend.h').replace('si_query_backend.h', 'exi_getid_backend.h')
marker = 'metadata_path = private /'
assert body.count(marker) == 1
body = body.replace(marker, '''reference = json.loads((private / 'dolphin-sram/comparison.json').read_text())
settings_path = output / 'settings.bin'
settings_path.write_bytes(bytes.fromhex(reference['reports'][0]['values'][0]['scbHex'])[:64])
''' + marker)
body = body.replace("[str(exe), 'work/private-game/disc/DATA/sys/main.dol']", "[str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(settings_path)]")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/sram-native')
path = output / 'build.json'
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report['baseBuilderSha256'] = sha(parent)
report['settingsSha256'] = sha(output / 'settings.bin')
report['hostInputSha256'] = sha(experiment / 'sram_host.cpp')
report['getidFrontendSha256'] = sha(experiment / 'exi_getid_frontend.h')
path.write_text(json.dumps(report, indent=2) + '\n')
