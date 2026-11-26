"""Actual existing kernel releases FD after stream close; errors/reopen retain STM and bytes."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_sysconf_read_device.py')
body = parent.read_text().replace('mass-sysconf-read-boot', 'mass-sysconf-close-boot')
injection = '''
    if (kernel.close(context, 3) != IPC_OK || kernel.close(context, 3) != -4) { return 22; }
    if (kernel.read(context, 3, 0x4b31a0, 0x4000) != -4) { return 23; }
    if (kernel.open(context, "/shared2/sys/SYSCONF", 1) != 3) { return 24; }
    try { kernel.close(context, 3); return 25; } catch (const std::runtime_error&) {}
    for (unsigned i = 0; i < 0x4000; ++i) { if (destination[i] != uint8_t(expected[i])) { return 26; } }
    if (devices::experiment_stm_pending() != pending) { return 27; }
'''
marker = '    if (devices::experiment_stm_pending() != pending) { return 20; }'
assert body.count(marker) == 1
body = body.replace(marker, marker + injection)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-close-boot/device-guards.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['result'] = 'ACTUAL_CLOSE_RELEASE_FD3_INVALID_MINUS4_REOPEN3_PREMATURE_REFUSAL_PENDING_BYTES_READ_GUARDS_PASS'
report['limits'] = ['Existing kernel/stream component; dynamic source callbacks separately verified.',
    'Next product file/SC completion and public PC-settings policy unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual streamCLOSE/sharedFDrelease/alreadyclosed-4/readclosed-4/reopen3/premature refusal/bytes+STM/read guards')
