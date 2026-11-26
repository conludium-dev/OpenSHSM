"""Read the next packet flush caller state, preserving existing startup refusals."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

parent = Path('experiments/wii-static-recomp/build_flush_ee_boot.py')
body = parent.read_text().replace("root / 'mass-flush-ee-boot'", "root / 'mass-flush-packet-observer'")
marker = 'sources = [output /'
injection = '''wrapper_path = output / 'boot-wrapper.cpp'
wrapper = wrapper_path.read_text()
marker = '    l2_snapshot(address, context);'
assert wrapper.count(marker) == 1
observer = ''' + repr(r'''    if (address == 0x80212fd0 && context.lr == 0x80242240) {
        const auto& state = bat_context(context);
        std::cout << "PACKET_FLUSH_STATE " << std::hex << context.pc << ' ' << context.lr << ' '
            << context.msr << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << state.hid0 << ' '
            << hw::pi_intsr.load() << ' ' << hw::pi_intmr.load() << std::dec << ' '
            << context.in_callback << ' ' << context.callback_depth << ' ' << context.backup_stack.size() << ' '
            << bool(context.dispatch_saved_ctx) << ' ' << context.ext_resched_pending << ' ' << context.exception_pc << ' '
            << context.vblank_pending.load() << ' ' << context.dec_irq_pending << ' '
            << context.pending_cb_count.load() << ' ' << context.pending_callbacks.size() << '\n';
    }
''') + '''
wrapper_path.write_text(wrapper.replace(marker, observer + marker))
'''
assert body.count(marker) == 1
body = body.replace(marker, injection + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-flush-packet-observer')
environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
    str(output / 'boot-quarantine.tsv'), 'work/private-game/static-recomp/sram-native/settings.bin'],
    env=environment, capture_output=True, text=True, timeout=30)
(output / 'observed-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and not result.stderr
lines = [line for line in result.stdout.splitlines() if line.startswith(('PACKET_FLUSH_STATE ', 'BOOT_BOUNDARY '))]
assert len(lines) == 2
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'observation.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)),
    'parentSha256': sha(parent), 'buildSha256': sha(output / 'build.json'),
    'logSha256': sha(output / 'observed-boot.log'), 'states': lines}, indent=2) + '\n')
print('\n'.join(lines))
