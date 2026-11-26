"""Check the existing native kernel/device closes and reuses only ES FD3."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_datadir_device.py')
body = parent.read_text()
marker = '    if (packetRefused != 13) { return 22; }'
assert body.count(marker) == 1
injection = '''
    for (unsigned iteration = 0; iteration < 3; ++iteration) {
        if (kernel.close(context, 3) != IPC_OK || kernel.close(context, 3) != -4) { return 23; }
        std::fill(output, output + 32, 0xa5);
        if (kernel.ioctlv(context, directory) != -4 || kernel.close(context, 99) != -4) { return 24; }
        for (unsigned index = 0; index < 32; ++index) { if (output[index] != 0xa5) { return 25; } }
        if (devices::experiment_stm_pending() != pending || !pending || pending->fd != 1 ||
            pending->req_addr != 0x135e0020 || pending->ioctl_cmd != 0x1000) { return 26; }
        if (iteration < 2 && kernel.open(context, "/dev/es", 0) != 3) { return 27; }
    }
'''
body = body.replace(marker, marker + injection)
artifact_names = [('es-title-device-probe', 'es-close-kernel-probe'), ('device-compile.log', 'close-kernel-compile.log'),
    ('device-execution.log', 'close-kernel-execution.log'), ('metadata-probe', 'close-metadata-probe'),
    ('device-guards.json', 'close-kernel.json')]
rename = ''.join('body = body.replace(' + repr(old) + ', ' + repr(new) + ')\n' for old, new in artifact_names)
body = body.replace("exec(compile(body, str(parent), 'exec'), {'__file__': __file__})",
    rename + "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})")
body = body.replace("/device-guards.json'", "/close-kernel.json'")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-es-datadir-boot/close-kernel.json')
report = json.loads(path.read_text())
report['result'] = 'ES_KERNEL_CLOSE3_REOPEN2_FD3_INVALID_MINUS4_PENDING_PASS_WITH_DATADIR_TITLE_GUARDS'
report['closeParentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Existing kernel/device component closure only; native boot still refuses CLOSE submission and SDK FD store is not tested here.')
path = path.with_name('close-kernel.json')
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS existing kernel ES CLOSE3/reopen2 reusesFD3/invalid -4/retains STM and output; native boot integration pending')
