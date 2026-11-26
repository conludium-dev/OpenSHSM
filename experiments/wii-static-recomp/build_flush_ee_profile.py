"""Generate a bounded EE extension of the existing flush mechanism, retaining EE-off behavior."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-ipc-startup-boot')
output = Path('work/private-game/static-recomp/flush-ee-profile')
output.mkdir(exist_ok=True)
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
(output / 'ipc_startup_frontend.h').write_bytes((experiment / 'ipc_startup_frontend.h').read_bytes())
source = (experiment / 'flush_syscall.h').read_text()
source = source.replace('namespace nwii::runtime {', 'namespace nwii::runtime {\ninline bool experimentFlushEe = false;', 1)
marker = '    auto& state = bat_context(context);'
check = '''
    if (context.msr == 0xa032 && (!experimentFlushEe || context.lr != 0x8024262c ||
        (hw::pi_intsr.load() & hw::pi_intmr.load()) || context.in_callback || context.callback_depth ||
        !context.backup_stack.empty() || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc ||
        context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load() || !context.pending_callbacks.empty())) {
        throw std::runtime_error("EE flush caller/pending-state unverified");
    }
'''
source = source.replace(marker, marker + check, 1)
assert source.count('context.msr != 0x2032') == 1 and source.count('context.srr1 != 0x2032') == 1
source = source.replace('context.msr != 0x2032', '(context.msr != 0x2032 && context.msr != 0xa032)')
source = source.replace('context.srr1 != 0x2032', '(context.srr1 != 0x2032 && (!experimentFlushEe || context.srr1 != 0xa032))')
(output / 'flush_syscall.h').write_text(source)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'profile.json').write_text(json.dumps({'parentHeaderSha256': sha(experiment / 'flush_syscall.h'),
    'builderSha256': sha(Path(__file__)), 'headerSha256': sha(output / 'flush_syscall.h'),
    'limits': ['Existing CPU/cache/syscall state only; EE optional/defaultoff/exact measured caller/no pending producers.',
        'EE-off path retained; no interpreter or empty syscall handler.']}, indent=2) + '\n')
