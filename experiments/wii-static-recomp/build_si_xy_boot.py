"""Enable the verified SI polling store in the existing guarded boot."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_xy_native.py')], check=True)
ghidra = private / 'si-xy-native/ghidra/verification.json'
assert json.loads(ghidra.read_text())['result'] == 'SI_SET_XY_GHIDRA23_INSTRUCTIONS92_BYTES_FULL_BODY'
builder = experiment / 'build_vi_clock_boot.py'
body = builder.read_text().replace('mass-vi-clock-boot', 'mass-si-xy-boot').replace('vi_clock_frontend.h', 'si_xy_frontend.h')
body = body.replace('experiment_vi_next_write32(ctx,', 'experiment_si_xy_write32(ctx,')
registration = '    nwii::runtime::hw::register_vi(nwii::runtime::MMIODispatcher::get());\\n'
assert body.count(registration) == 1
body = body.replace(registration, registration + '    nwii::runtime::hw::experiment_register_si_xy(nwii::runtime::MMIODispatcher::get());\\n')
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 2
old = 'wrapper.write_text(\'#include "exi_getid_frontend.h"\\n\' + body)'
new = 'wrapper.write_text(\'#include "si_xy_frontend.h"\\n\' + body)'
injection = 'body = body.replace(' + repr(old) + ', ' + repr(new) + ')\n'
position = body.rindex(marker)
body = body[:position] + 'body = body.replace(' + repr(marker) + ', ' + repr(injection + marker) + ')\n' + body[position:]
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = private / 'mass-si-xy-boot'
path = output / 'boot.json'
report = json.loads(path.read_text())
report['result'] = 'VERIFIED_SI_XY_STORE_BOOT_REQUIRES_NEXT_ACCESS_AUDIT'
report['siXY'] = {'baseBuilderSha256': sha(builder), 'nativeProofSha256': sha(private / 'si-xy-native/comparison.json'),
    'nativeVerifierSha256': sha(private / 'si-xy-native/verification.json'), 'ghidraSha256': sha(ghidra),
    'backendSha256': sha(experiment / 'si_xy_backend.h'), 'frontendSha256': sha(experiment / 'si_xy_frontend.h')}
report['limits'] = ['Measured SI polling-register write values only; active polling/device transfer/input/interrupt producers remain unverified.',
    'Next original guest refusal retained; no first image, full SI initialization or controller acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
