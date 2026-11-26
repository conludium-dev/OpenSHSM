"""Offline reproduction using installed experimental tools and the user's supported DOL."""
from pathlib import Path
import argparse
import hashlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--audit-only', action='store_true')
parser.add_argument('--phone-fragment', action='store_true')
parser.add_argument('--phone-services', action='store_true')
parser.add_argument('--mass', action='store_true')
parser.add_argument('--processor', action='store_true')
parser.add_argument('--cache', action='store_true')
parser.add_argument('--fpscr', action='store_true')
parser.add_argument('--dolphin', action='store_true')
parser.add_argument('--icache', action='store_true')
parser.add_argument('--coherence', action='store_true')
parser.add_argument('--memory-frontend', action='store_true')
parser.add_argument('--cache-conflict', action='store_true')
parser.add_argument('--dcache', action='store_true')
parser.add_argument('--l2', action='store_true')
parser.add_argument('--branch', action='store_true')
parser.add_argument('--poll', action='store_true')
parser.add_argument('--carry', action='store_true')
parser.add_argument('--timebase', action='store_true')
parser.add_argument('--os-time', action='store_true')
parser.add_argument('--performance', action='store_true')
parser.add_argument('--hid4', action='store_true', help='Verify original HID4 and isolated BAT core; no live activation')
parser.add_argument('--bat', action='store_true', help='Full shared BAT memory frontend and scoped original HID4 activation')
parser.add_argument('--spd', action='store_true', help='Original HID0 SPD function comparison and scoped writer extension')
parser.add_argument('--ni-numeric', action='store_true', help='Observe original NI/frsp and verify numerical conversion only; no runtime activation')
parser.add_argument('--frsp', action='store_true', help='Verify FRSP status and full-module routing; retain NI quarantine')
parser.add_argument('--frsp-roots', action='store_true', help='Recover missing FRSP roots in isolation; no dispatch activation')
parser.add_argument('--ni-guard', action='store_true', help='Scoped NI setter with strict FP guards and bounded boot continuation')
parser.add_argument('--template-copy', action='store_true', help='Exact blocked-store observation and isolated original template-copy comparison')
parser.add_argument('--fp64', action='store_true', help='Verified double bit transfers and full-module original memcpy under NI0/NI1')
parser.add_argument('--template-patch', action='store_true', help='Scoped measured mutable-template word and stale compiled-entry refusal')
parser.add_argument('--template-nop', action='store_true', help='Observed/measured NOP word store on existing template cache path')
parser.add_argument('--table-observer', action='store_true', help='Observe OS table/reset writes with physical protected-image diagnostics')
parser.add_argument('--template-reset', action='store_true', help='Original reset-store oracle and scoped existing-cache adaptation')
parser.add_argument('--mmio-observer', action='store_true', help='Exact guarded memory-write observation in original interrupt initialization')
parser.add_argument('--pi-mask', action='store_true', help='Original PI-mask store and existing vendor register/dispatcher integration at EE0')
parser.add_argument('--ipc-reset', action='store_true', help='Original IPC reset observations and isolated vendor-register/original-store tests; no live activation')
parser.add_argument('--ipc-pending', action='store_true', help='Original ACK/reply reset observations and isolated existing-scheduler causal test; no boot activation')
parser.add_argument('--ipc-producer', action='store_true', help='Bounded physical OPEN parser/kernel/full64-byte reply/event coupling; no boot activation')
parser.add_argument('--ipc-sdk-roots', action='store_true', help='Reuse dtk SDK IPC roots and verify two register helpers in Ghidra; no sender activation')
parser.add_argument('--ipc-control-projection', action='store_true', help='Original control-clear/X2 observations and bounded existing-storage backend; no send/IRQ activation')
parser.add_argument('--ipc-irq-projection', action='store_true', help='Original IRQFLAG-clear immediate/delayed observations and bounded existing IPC/PI/scheduler projection')
parser.add_argument('--ipc-buffer-chain', action='store_true', help='Execute original IPC buffer initialization on synthetic loader inputs; no sender activation')
parser.add_argument('--ios-open-wrapper', action='store_true', help='Compare whole recompiled IOS_Open with original PPC and explicit service fixtures; no IOS activation')
parser.add_argument('--ios-open-allocator', action='store_true', help='Use original heap creation/aligned allocator in IOS_Open differential; cache/transport/IRQ remain fixtures')
parser.add_argument('--ios-open-free', action='store_true', help='Two original allocation/free cycles with heap reuse; host-directed lifecycle, no IOS activation')
parser.add_argument('--ios-transport-roots', action='store_true', help='Pin/compile original IOS transport and independently inspect with Ghidra; no execution activation')
parser.add_argument('--ios-transport-execution', action='store_true', help='Execute original transport through explicit services to sleep/free boundaries; no reply/boot activation')
parser.add_argument('--ios-transport-completion', action='store_true', help='Couple original transport to actual kernel/scheduler reply with synthetic sleep release; no IRQ/boot activation')
parser.add_argument('--ios-reply-handler', action='store_true', help='Compare original synchronous reply handler through explicit cache/register/wakeup services')
parser.add_argument('--ios-handler-completion', action='store_true', help='Couple actual kernel to original reply handler and queue-specific wakeup token; no real OS/IRQ activation')
parser.add_argument('--ios-wakeup', action='store_true', help='Execute original wakeup queue mutations with explicit SelectThread/interrupt services; no actual context switch')
parser.add_argument('--ios-wakeup-completion', action='store_true', help='Couple original wakeup queue mutation to kernel/handler completion; no actual SelectThread/context switch')
parser.add_argument('--ios-select-thread', action='store_true', help='Original priority selection to callback/context boundaries; no actual CPU switch')
parser.add_argument('--ios-default-switch-callback', action='store_true', help='Execute the original initial switch callback and resume SelectThread to OSSetCurrentContext; no CPU switch')
parser.add_argument('--ios-set-context', action='store_true', help='Original getter/setter in SelectThread through default callback, stopping before OSLoadContext; no CPU switch')
parser.add_argument('--ios-load-context', action='store_true', help='Original standalone register/GQR/SRR restoration through RFI with saved EE0; no full thread/IRQ switch')
parser.add_argument('--ios-save-context', action='store_true', help='Original save and host-directed save/load roundtrip at EE0; no selector/IRQ activation')
parser.add_argument('--ios-selector-context-transfer', action='store_true', help='Original selector/save/set/load and self-resumption through RFI at EE0; no wakeup/IRQ/boot activation')
parser.add_argument('--ios-sleep', action='store_true', help='Original priority wait-queue insertion with SelectThread/interrupt fixtures; no actual blocking')
parser.add_argument('--ios-sleep-wakeup', action='store_true', help='Host-directed original sleep/wakeup on shared queue; SelectThread/interrupts remain fixtures')
parser.add_argument('--ios-thread-cycle', action='store_true', help='Original sleep/selector/save/load/wakeup and A-thread resumption from B at EE0; IRQ/transport unverified')
parser.add_argument('--ios-thread-cycle-irqs', action='store_true', help='Original interrupt disable/restore in two-thread cycle at initial EE0/1 with empty event state; no IRQ delivery')
parser.add_argument('--ios-deferred-wakeup', action='store_true', help='Original wakeup under mismatched IRQ context then original reschedule; prepared IRQ entry, no real delivery')
parser.add_argument('--ios-thread-reply-handler', action='store_true', help='Original reply handler/deferred wakeup/reschedule with supplied synchronous OPEN reply; no transport')
parser.add_argument('--ios-thread-kernel-reply', action='store_true', help='Actual kernel/event reply through original handler/deferred wakeup/thread resumption; no transport/IRQ vector')
parser.add_argument('--ios-thread-transport', action='store_true', help='Original transport sends/blocks/resumes and returns actual kernel result; free/cache/IRQ remain fixtures')
parser.add_argument('--ios-thread-open-lifecycle', action='store_true', help='Original IOS_Open heap/allocate/send/sleep/completion/free in one MEM1 cycle; cache/MMIO/IRQ remain fixtures')
parser.add_argument('--ios-thread-heap-reuse', action='store_true', help='144 original IOS_Open/completion/free cycles share one heap; fresh and reused lost-event mutants')
parser.add_argument('--ios-thread-allocation-failure', action='store_true', help='Original IOS_Open returns-22 on small heap without sending/blocking/completion')
parser.add_argument('--ios-thread-ipc-interrupt', action='store_true', help='Original IPC interrupt reply gate in Open/thread completion cycle; register/IRQ entry fixtures')
parser.add_argument('--ios-thread-ipc-ack', action='store_true', help='Original ACK then reply in Open/thread cycle; empty ring/register/IRQ fixtures')
parser.add_argument('--ios-thread-ipc-registers', action='store_true', help='Original PPC IPC register helpers through MMU/MMIO in ACK/reply/thread chain; hardware fixture')
parser.add_argument('--ios-thread-ipc-control', action='store_true', help='Measured control projection on existing vendor storage in original Open/thread chain; no real IRQ delivery')
parser.add_argument('--ios-thread-ipc-irq', action='store_true', help='Prepared kernel reply before ACK, latched IPC/PI and deferred original reply dispatch; IRQ vector remains fixture')
parser.add_argument('--ios-irq-dispatch-roots', action='store_true', help='Pin/compile original external handler and dispatcher190words and verify Ghidra; no dispatcher execution')
parser.add_argument('--ios-external-irq', action='store_true', help='Original external save/dispatcher/masks/IRQ27 callback/context restoration192cases; handler/time/vector preamble fixtures')
parser.add_argument('--ios-thread-external-irq', action='store_true', help='Original dispatcher selects IPC handler and reschedules sleeping IOS_Open caller; vector preamble/time/ACK remain fixtures')
parser.add_argument('--ios-exception-vector', action='store_true', help='Original exception vector saves preamble and routes IPC/thread resume; prepared copy/hardware entry/clock remain fixtures')
parser.add_argument('--ios-vector-return', action='store_true', help='Original vector/IPC/Open then second A sleep restores interrupted B; prepared entry/clock remain fixtures')
parser.add_argument('--ipc-reset-boot', action='store_true', help='Separate guarded boot profile passes verified quiescent IPC reset and retains the next hardware boundary')
args = parser.parse_args()
args.ios_vector_return |= args.ipc_reset_boot
args.ios_exception_vector |= args.ios_vector_return
args.ios_thread_external_irq |= args.ios_exception_vector
args.ios_external_irq |= args.ios_thread_external_irq
args.ios_irq_dispatch_roots |= args.ios_external_irq
args.ios_thread_ipc_irq |= args.ios_irq_dispatch_roots
args.ios_thread_ipc_control |= args.ios_thread_ipc_irq
args.ipc_irq_projection |= args.ios_thread_ipc_irq
args.ios_thread_ipc_registers |= args.ios_thread_ipc_control
args.ipc_control_projection |= args.ios_thread_ipc_control
args.ios_thread_ipc_ack |= args.ios_thread_ipc_registers
args.ios_thread_ipc_interrupt |= args.ios_thread_ipc_ack
args.ios_thread_heap_reuse |= args.ios_thread_allocation_failure
args.ios_thread_open_lifecycle |= args.ios_thread_heap_reuse or args.ios_thread_ipc_interrupt
args.ios_thread_transport |= args.ios_thread_open_lifecycle
args.ios_thread_kernel_reply |= args.ios_thread_transport
args.ios_thread_reply_handler |= args.ios_thread_kernel_reply
args.ios_deferred_wakeup |= args.ios_thread_reply_handler
args.ios_thread_cycle_irqs |= args.ios_deferred_wakeup
args.ios_thread_cycle |= args.ios_thread_cycle_irqs
args.ios_sleep_wakeup |= args.ios_thread_cycle
args.ios_sleep |= args.ios_sleep_wakeup
args.ios_selector_context_transfer |= args.ios_sleep
args.ios_save_context |= args.ios_selector_context_transfer
args.ios_load_context |= args.ios_save_context
args.ios_set_context |= args.ios_load_context
args.ios_default_switch_callback |= args.ios_set_context
args.ios_select_thread |= args.ios_default_switch_callback
args.ios_wakeup_completion |= args.ios_select_thread
args.ios_wakeup |= args.ios_wakeup_completion
args.ios_handler_completion |= args.ios_wakeup
args.ios_reply_handler |= args.ios_handler_completion
args.ios_transport_completion |= args.ios_reply_handler
args.ios_transport_execution |= args.ios_transport_completion
args.ios_transport_roots |= args.ios_transport_execution
args.ios_open_free |= args.ios_transport_roots
args.ios_open_allocator |= args.ios_open_free
args.ios_open_wrapper |= args.ios_open_allocator
args.ipc_buffer_chain |= args.ios_open_wrapper
args.ipc_control_projection |= args.ipc_irq_projection
args.ipc_sdk_roots |= args.ipc_buffer_chain or args.ipc_control_projection
args.ipc_producer |= args.ipc_sdk_roots
args.ipc_pending |= args.ipc_producer
args.ipc_reset |= args.ipc_pending
args.pi_mask |= args.ipc_reset
args.mmio_observer |= args.pi_mask
args.template_reset |= args.mmio_observer
args.table_observer |= args.template_reset
args.template_nop |= args.table_observer
args.template_patch |= args.template_nop
args.fp64 |= args.template_patch
args.template_copy |= args.fp64
args.ni_guard |= args.template_copy
args.frsp |= args.frsp_roots or args.ni_guard
args.ni_numeric |= args.frsp
args.spd |= args.ni_numeric
args.bat |= args.spd
args.hid4 |= args.bat
args.performance |= args.hid4
args.os_time |= args.performance
args.timebase |= args.os_time
args.carry |= args.timebase
args.poll |= args.carry
args.branch |= args.poll
args.l2 |= args.branch
args.dcache |= args.l2
args.cache_conflict |= args.dcache
args.memory_frontend |= args.cache_conflict
args.coherence |= args.memory_frontend
args.icache |= args.coherence
args.dolphin |= args.icache
args.fpscr |= args.dolphin
args.cache |= args.fpscr
root = Path('.').resolve()
tools = root / '_scratch/tmp/wii-static-recomp-tools'
upstream = tools / 'NWiiRecomp'
private = root / 'work/private-game/static-recomp'
generated = private / 'nwii-current'
dol = root / 'work/private-game/disc/DATA/sys/main.dol'
assert hashlib.sha1(dol.read_bytes()).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3', 'Unverified Wii version'
private.mkdir(parents=True, exist_ok=True)


def run(stage, command, timeout=900):
    print(stage, flush=True)
    result = subprocess.run([str(item) for item in command], capture_output=True, text=True, timeout=timeout)
    (private / ('pipeline-' + stage + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (stage, result.stdout[-3000:], result.stderr[-3000:])


if not args.audit_only:
    includes = [upstream / directory / 'include' for directory in ('nWiiAnalyzer', 'nWiiRecomp', 'nWiiRuntime')]
    sources = [root / 'experiments/wii-static-recomp/nwii_probe_driver.cpp']
    sources += [upstream / name for name in ('nWiiAnalyzer/src/analyzer.cpp', 'nWiiAnalyzer/src/signature_scanner.cpp',
                'nWiiAnalyzer/src/dolphin_sigdb.cpp', 'nWiiRecomp/src/recompiler.cpp', 'nWiiRecomp/src/symbols.cpp',
                'nWiiRuntime/src/core/loader.cpp')]
    run('build-analyzer', ['clang++', '-std=c++20', '-O2', *[flag for path in includes for flag in ('-I', str(path))],
                           *sources, '-o', tools / 'nwii-probe'])
    run('generate', [tools / 'nwii-probe', dol, generated])
    run('dtk-config', [tools / 'dtk', 'dol', 'config', '-o', private / 'dtk-config.yml', dol])
    run('dtk-split', [tools / 'dtk', 'dol', 'split', private / 'dtk-config.yml', private / 'dtk-output'])
    runtime_headers = upstream / 'nWiiRuntime/include'
    run('build-mac-library', ['clang++', '-std=c++20', '-O2', '-include', 'bit', '-I', runtime_headers,
                             '-dynamiclib', root / 'experiments/wii-static-recomp/probe_bridge.cpp',
                             generated / 'selected.cpp', '-o', generated / 'libshsm-recomp-probe.dylib'])
    run('build-mac-host', ['clang++', '-std=c++20', '-O2', root / 'experiments/wii-static-recomp/probe_host.cpp',
                          generated / 'libshsm-recomp-probe.dylib', '-o', generated / 'probe-host'])
    run('execute-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                          root / 'experiments/wii-static-recomp/verify_execution.py'])
    run('execute-windows', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                           root / 'experiments/wii-static-recomp/verify_windows.py'])
    run('objdiff', [tools / 'objdiff-cli', 'diff', '-1', private / 'dtk-output/obj/auto_03_800F2228_text.o',
                   '-2', generated / 'reference-roundtrip.o', 'fn_800F3E60', '-o', private / 'objdiff-reference.json', '--format', 'json-pretty'])
    run('ghidra', ['python3', root / 'experiments/wii-static-recomp/run_ghidra.py'])
    run('runtime', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                   root / 'experiments/wii-static-recomp/build_runtime_probe.py'])
run('audit', ['python3', root / 'experiments/wii-static-recomp/audit_result.py'])
if args.phone_fragment:
    if not args.audit_only:
        run('phone-dependencies', ['python3', root / 'experiments/wii-static-recomp/inspect_phone_dependencies.py'])
        run('phone-build', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                           root / 'experiments/wii-static-recomp/build_runtime_probe.py', '--', '--phone-fragment'])
        run('phone-frames', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                            root / 'experiments/wii-static-recomp/verify_phone_fragment.py'])
    run('phone-audit', ['python3', root / 'experiments/wii-static-recomp/audit_phone_fragment.py'])
if args.phone_services:
    if not args.audit_only:
        run('services-build', ['python3', root / 'experiments/wii-static-recomp/build_services_probe.py'])
        run('services-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                               root / 'experiments/wii-static-recomp/verify_services_execution.py'])
        run('services-windows', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                root / 'experiments/wii-static-recomp/verify_services_windows.py'])
        run('services-ghidra', ['python3', root / 'experiments/wii-static-recomp/run_services_ghidra.py'])
    run('services-audit', ['python3', root / 'experiments/wii-static-recomp/audit_services_probe.py'])
if args.mass:
    if not args.audit_only:
        if not args.phone_services:
            run('mass-backend-profile', ['python3', root / 'experiments/wii-static-recomp/build_services_probe.py'])
        run('mass-generate', ['python3', root / 'experiments/wii-static-recomp/generate_mass.py'])
        run('mass-syntax', ['python3', root / 'experiments/wii-static-recomp/compile_mass.py'])
        run('mass-objects', ['python3', root / 'experiments/wii-static-recomp/compile_mass.py', '--objects'])
        run('mass-boot', ['python3', root / 'experiments/wii-static-recomp/run_mass_boot.py'])
        run('mass-boot-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                               root / 'experiments/wii-static-recomp/verify_mass_boot.py'])
    run('mass-audit', ['python3', root / 'experiments/wii-static-recomp/audit_mass.py'])
if args.processor or args.cache:
    if not args.audit_only:
        run('processor-lower', ['python3', root / 'experiments/wii-static-recomp/lower_processor.py'])
        run('processor-boot', ['python3', root / 'experiments/wii-static-recomp/run_mass_boot.py', '--processor'])
        run('processor-register-check', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                       root / 'experiments/wii-static-recomp/verify_processor.py'])
        run('processor-boot-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_mass_boot.py', '--processor'])
        run('processor-baseline-refresh', ['python3', root / 'experiments/wii-static-recomp/run_mass_boot.py'])
        run('processor-baseline-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                        root / 'experiments/wii-static-recomp/verify_mass_boot.py'])
    run('processor-audit', ['python3', root / 'experiments/wii-static-recomp/audit_processor.py'])
if args.cache:
    if not args.audit_only:
        run('cache-lower', ['python3', root / 'experiments/wii-static-recomp/lower_processor.py', '--cache'])
        run('cache-boot', ['python3', root / 'experiments/wii-static-recomp/run_mass_boot.py', '--cache'])
        run('cache-contract', ['python3', root / 'experiments/wii-static-recomp/verify_cache.py'])
        run('cache-boot-oracle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                root / 'experiments/wii-static-recomp/verify_mass_boot.py', '--cache'])
    run('cache-audit', ['python3', root / 'experiments/wii-static-recomp/audit_cache.py'])
if args.fpscr:
    if not args.audit_only:
        run('fpscr-build', ['python3', root / 'experiments/wii-static-recomp/build_fpscr.py'])
        oracle = ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3']
        run('fpscr-instruction-check', [*oracle, root / 'experiments/wii-static-recomp/verify_fpscr.py'])
        run('fpscr-initializer-check', [*oracle, root / 'experiments/wii-static-recomp/verify_fpr_init.py'])
        run('fpscr-boot-partial-check', [*oracle, root / 'experiments/wii-static-recomp/verify_fpscr_boot.py'])
    run('fpscr-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_fpscr.py'])
if args.dolphin:
    if not args.audit_only:
        run('dolphin-local-runtime', ['python3', root / 'experiments/wii-static-recomp/prepare_dolphin_runtime.py'])
        run('dolphin-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_dolphin_probe.py'])
        run('dolphin-native-translated-fixture', ['python3', root / 'experiments/wii-static-recomp/build_fpscr.py', '--translated-fixture'])
        for mode in ['boot', 'fpr-init']:
            run('dolphin-' + mode, ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                   root / 'experiments/wii-static-recomp/run_dolphin_probe.py', '--', '--mode', mode])
    run('dolphin-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_dolphin_probe.py'])
if args.icache:
    if not args.audit_only:
        run('icache-build', ['python3', root / 'experiments/wii-static-recomp/build_icache.py'])
        run('icache-contract', ['python3', root / 'experiments/wii-static-recomp/verify_icache.py'])
        run('icache-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_dolphin_probe.py', '--icache'])
        run('icache-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                              root / 'experiments/wii-static-recomp/run_dolphin_probe.py', '--', '--stage', 'icache'])
    run('icache-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_icache.py'])
if args.coherence:
    if not args.audit_only:
        run('coherence-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_dolphin_probe.py', '--coherence'])
        for accuracy in ['False', 'True']:
            run('coherence-' + accuracy.lower(), ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                                 root / 'experiments/wii-static-recomp/run_dolphin_probe.py', '--',
                                                 '--stage', 'coherence', '--accurate-cache', accuracy])
    run('coherence-gap-audit', ['python3', root / 'experiments/wii-static-recomp/audit_coherence.py'])
if args.memory_frontend:
    if not args.audit_only:
        run('memory-build', ['python3', root / 'experiments/wii-static-recomp/build_memory_frontend.py'])
        run('memory-pre-dce-boot', ['python3', root / 'experiments/wii-static-recomp/run_memory_boot.py'])
    run('memory-bounded-audit', ['python3', root / 'experiments/wii-static-recomp/verify_memory_frontend.py'])
    run('memory-original-consumer', ['python3', root / 'experiments/wii-static-recomp/verify_memory_original.py'])
if args.cache_conflict:
    if not args.audit_only:
        run('conflict-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_conflict_probe.py'])
        run('conflict-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                 root / 'experiments/wii-static-recomp/run_conflict_probe.py'])
    run('conflict-independent-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_conflict.py'])
if args.dcache:
    if not args.audit_only:
        run('dcache-build', ['python3', root / 'experiments/wii-static-recomp/build_dcache.py'])
        run('dcache-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_dcache_probe.py'])
        run('dcache-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                              root / 'experiments/wii-static-recomp/run_dcache_probe.py'])
    run('dcache-scoped-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_dcache.py'])
if args.l2:
    if not args.audit_only:
        run('l2-build', ['python3', root / 'experiments/wii-static-recomp/build_l2.py'])
        run('l2-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_l2_probe.py'])
        run('l2-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                          root / 'experiments/wii-static-recomp/run_l2_probe.py'])
    run('l2-scoped-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_l2.py'])
if args.branch:
    if not args.audit_only:
        run('branch-module-build', ['python3', root / 'experiments/wii-static-recomp/build_branch.py'])
        run('branch-original-isa', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_branch_isa.py'])
        run('branch-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_branch_probe.py'])
        run('branch-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                              root / 'experiments/wii-static-recomp/run_branch_probe.py'])
    run('branch-scoped-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_branch.py'])
if args.poll:
    if not args.audit_only:
        run('poll-contract-build', ['python3', root / 'experiments/wii-static-recomp/build_poll.py'])
        run('poll-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_poll_probe.py'])
        run('poll-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                            root / 'experiments/wii-static-recomp/run_poll_probe.py'])
        run('poll-normalized-dol', ['python3', root / 'experiments/wii-static-recomp/build_poll_normalized_probe.py'])
        run('poll-normalized-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                      root / 'experiments/wii-static-recomp/run_poll_normalized_probe.py'])
    run('poll-known-gap-audit', ['python3', root / 'experiments/wii-static-recomp/audit_poll_gap.py'])
if args.carry:
    if not args.audit_only:
        run('carry-module-build', ['python3', root / 'experiments/wii-static-recomp/build_carry.py'])
        run('carry-original-isa', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                  root / 'experiments/wii-static-recomp/verify_carry_isa.py'])
    run('carry-scoped-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_carry.py'])
if args.timebase:
    if not args.audit_only:
        run('timebase-module-build', ['python3', root / 'experiments/wii-static-recomp/build_timebase.py'])
        run('timebase-controlled-reader', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                          root / 'experiments/wii-static-recomp/verify_timebase_reader.py'])
    run('timebase-bounded-audit', ['python3', root / 'experiments/wii-static-recomp/verify_timebase.py'])
if args.os_time:
    if not args.audit_only:
        run('timebase-scoped-activate', ['python3', root / 'experiments/wii-static-recomp/activate_timebase.py'])
        run('os-time-native-probe', ['python3', root / 'experiments/wii-static-recomp/build_os_time_probe.py'])
        run('os-time-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_os_time_dolphin.py'])
        run('os-time-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                       root / 'experiments/wii-static-recomp/run_os_time_dolphin.py'])
    run('os-time-consumer-audit', ['python3', root / 'experiments/wii-static-recomp/audit_os_time.py'])
if args.performance:
    if not args.audit_only:
        run('performance-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_performance_dolphin.py'])
        run('performance-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                           root / 'experiments/wii-static-recomp/run_performance_dolphin.py'])
        run('performance-module-build', ['python3', root / 'experiments/wii-static-recomp/build_performance.py'])
        run('performance-scoped-activate', ['python3', root / 'experiments/wii-static-recomp/activate_performance.py'])
    run('performance-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_performance.py'])
if args.hid4:
    if not args.audit_only:
        run('hid4-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_hid4_dolphin.py'])
        run('hid4-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                    root / 'experiments/wii-static-recomp/run_hid4_dolphin.py'])
    run('hid4-bat-dependencies', ['python3', root / 'experiments/wii-static-recomp/analyze_bat_dependencies.py'])
    run('hid4-isolated-bat-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_bat_translation.py'])
if args.bat:
    if not args.audit_only:
        run('bat-loader-measurement', ['python3', root / 'experiments/wii-static-recomp/build_bat_seed.py'])
        run('bat-loader-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                 root / 'experiments/wii-static-recomp/run_bat_seed.py'])
        run('bat-module-build', ['python3', root / 'experiments/wii-static-recomp/build_bat.py'])
        run('bat-rotate-record-isa', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_rotate_record.py'])
        run('bat-scoped-activate', ['python3', root / 'experiments/wii-static-recomp/activate_bat.py'])
    run('bat-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_bat.py'])
if args.spd:
    if not args.audit_only:
        run('spd-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_spd_dolphin.py'])
        run('spd-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                   root / 'experiments/wii-static-recomp/run_spd_dolphin.py'])
        run('spd-module-build', ['python3', root / 'experiments/wii-static-recomp/build_spd.py'])
    run('spd-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_spd.py'])
if args.ni_numeric:
    if not args.audit_only:
        run('ni-numeric-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ni_dolphin.py'])
        run('ni-numeric-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                          root / 'experiments/wii-static-recomp/run_ni_dolphin.py'])
    run('ni-numeric-scoped-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_ni_conversion.py'])
if args.frsp:
    if not args.audit_only:
        run('frsp-flags-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_frsp_flags_dolphin.py'])
        run('frsp-flags-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                         root / 'experiments/wii-static-recomp/run_frsp_flags_dolphin.py'])
        run('frsp-module-build', ['python3', root / 'experiments/wii-static-recomp/build_frsp.py'])
    run('frsp-module-audit', ['python3', root / 'experiments/wii-static-recomp/audit_frsp.py'])
if args.frsp_roots:
    run('frsp-missing-address-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_frsp_gaps.py'])
    if not args.audit_only:
        run('frsp-explicit-root-generation', ['python3', root / 'experiments/wii-static-recomp/build_frsp_roots.py'])
    run('frsp-explicit-root-verification', ['python3', root / 'experiments/wii-static-recomp/verify_frsp_roots.py'])
    run('frsp-explicit-root-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_frsp_roots_ghidra.py'])
if args.ni_guard:
    if not args.audit_only:
        run('ni-guard-module-build', ['python3', root / 'experiments/wii-static-recomp/build_ni_guard.py'])
        run('ni-guard-scoped-activation', ['python3', root / 'experiments/wii-static-recomp/activate_ni_guard.py'])
    run('ni-guard-live-audit', ['python3', root / 'experiments/wii-static-recomp/audit_ni_live.py'])
if args.template_copy:
    if not args.audit_only:
        run('code-write-observer-build', ['python3', root / 'experiments/wii-static-recomp/build_code_write_observer.py'])
        run('template-copy-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_template_copy_dolphin.py'])
        run('template-copy-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                            root / 'experiments/wii-static-recomp/run_template_copy_dolphin.py'])
        run('template-modes-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_template_modes_dolphin.py'])
        run('template-modes-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                             root / 'experiments/wii-static-recomp/run_template_modes_dolphin.py'])
        run('template-copy-native-build', ['python3', root / 'experiments/wii-static-recomp/build_template_copy_probe.py'])
    run('code-write-observer-audit', ['python3', root / 'experiments/wii-static-recomp/verify_code_write_observer.py'])
    run('template-copy-native-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_template_copy_native.py'])
if args.fp64:
    if not args.audit_only:
        run('fp64-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_fp64_dolphin.py'])
        run('fp64-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                     root / 'experiments/wii-static-recomp/run_fp64_dolphin.py'])
        run('fp64-native-instruction-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_fp64.py'])
        run('fp64-windows-helper-comparison', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                             root / 'experiments/wii-static-recomp/verify_fp64_windows.py'])
        run('fp64-module-build', ['python3', root / 'experiments/wii-static-recomp/build_fp64.py'])
    run('fp64-module-audit', ['python3', root / 'experiments/wii-static-recomp/audit_fp64.py'])
if args.template_patch:
    if not args.audit_only:
        run('template-patch-module-build', ['python3', root / 'experiments/wii-static-recomp/build_template_patch.py'])
    run('template-patch-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_template_patch.py'])
if args.template_nop:
    if not args.audit_only:
        run('nop-store-observer-build', ['python3', root / 'experiments/wii-static-recomp/build_nop_observer.py'])
        run('nop-store-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_nop_copy_dolphin.py'])
        run('nop-store-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                         root / 'experiments/wii-static-recomp/run_nop_copy_dolphin.py'])
        run('template-nop-module-build', ['python3', root / 'experiments/wii-static-recomp/build_template_nop.py'])
    run('nop-store-exact-observation', ['python3', root / 'experiments/wii-static-recomp/verify_nop_observer.py'])
    run('template-nop-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_template_nop.py'])
if args.table_observer:
    if not args.audit_only:
        run('table-write-observer-build', ['python3', root / 'experiments/wii-static-recomp/build_table_write_observer.py'])
    run('table-write-exact-audit', ['python3', root / 'experiments/wii-static-recomp/verify_table_write_observer.py'])
if args.template_reset:
    if not args.audit_only:
        run('reset-store-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_reset_copy_dolphin.py'])
        run('reset-store-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                           root / 'experiments/wii-static-recomp/run_reset_copy_dolphin.py'])
        run('template-reset-module-build', ['python3', root / 'experiments/wii-static-recomp/build_template_reset.py'])
    run('template-reset-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_template_reset.py'])
if args.mmio_observer:
    if not args.audit_only:
        run('mmio-write-observer-build', ['python3', root / 'experiments/wii-static-recomp/build_mmio_write_observer.py'])
    run('mmio-write-exact-audit', ['python3', root / 'experiments/wii-static-recomp/verify_mmio_write_observer.py'])
if args.pi_mask:
    if not args.audit_only:
        run('pi-mask-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_pi_mask_dolphin.py'])
        run('pi-mask-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                       root / 'experiments/wii-static-recomp/run_pi_mask_dolphin.py'])
        run('pi-mask-module-build', ['python3', root / 'experiments/wii-static-recomp/build_pi_mask.py'])
    run('pi-mask-scoped-audit', ['python3', root / 'experiments/wii-static-recomp/audit_pi_mask.py'])
    run('ipc-mask-gap-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ipc_mask_gap.py'])
if args.ipc_reset:
    if not args.audit_only:
        run('ipc-reset-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ipc_reset_dolphin.py'])
        run('ipc-reset-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                         root / 'experiments/wii-static-recomp/run_ipc_reset_dolphin.py'])
        run('ipc-reset-fixture-build', ['python3', root / 'experiments/wii-static-recomp/build_ipc_reset_fixture.py'])
    run('ipc-vendor-negative-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_vendor_gap.py'])
    run('ipc-reset-isolated-audit', ['python3', root / 'experiments/wii-static-recomp/audit_ipc_reset_fixture.py'])
if args.ipc_pending:
    if not args.audit_only:
        run('ipc-pending-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ipc_pending_dolphin.py'])
        run('ipc-pending-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                           root / 'experiments/wii-static-recomp/run_ipc_pending_dolphin.py'])
    run('ipc-pending-event-order-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_event_order.py'])
    run('ipc-kernel-missing-device-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_kernel_fixed.py'])
if args.ipc_producer:
    if not args.audit_only:
        run('ipc-packet-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ipc_packet_dolphin.py'])
        run('ipc-packet-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                          root / 'experiments/wii-static-recomp/run_ipc_packet_dolphin.py'])
    run('ipc-producer-packet-kernel-event-comparison', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_producer.py'])
if args.ipc_sdk_roots:
    run('ipc-sdk-root-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ipc_sdk_roots.py'])
    run('ipc-sdk-register-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_sdk_ghidra.py'])
if args.ipc_control_projection:
    if not args.audit_only:
        run('ipc-control-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ipc_control_dolphin.py'])
        run('ipc-control-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                           root / 'experiments/wii-static-recomp/run_ipc_control_dolphin.py'])
    run('ipc-control-projection-native-original', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_control_backend.py'])
if args.ipc_irq_projection:
    if not args.audit_only:
        run('ipc-irq-measurement-dol', ['python3', root / 'experiments/wii-static-recomp/build_ipc_irq_dolphin.py'])
        run('ipc-irq-original-dolphin', ['python3', root / 'work/research/run-windows-qa-from-macos.py',
                                       root / 'experiments/wii-static-recomp/run_ipc_irq_dolphin.py'])
    run('ipc-irq-projection-native-original', ['python3', root / 'experiments/wii-static-recomp/verify_ipc_irq_backend.py'])
if args.ipc_buffer_chain:
    run('ipc-buffer-original-chain', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                     root / 'experiments/wii-static-recomp/verify_ipc_buffer_chain.py'])
if args.ios_open_wrapper:
    run('ios-open-native-original-wrapper', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                            root / 'experiments/wii-static-recomp/verify_ios_open.py'])
    run('ios-open-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_open_ghidra.py'])
if args.ios_open_allocator:
    run('ios-open-original-allocator', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                       root / 'experiments/wii-static-recomp/verify_ios_open.py', '--original-allocator'])
    run('ios-allocator-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_open_ghidra.py', '--allocator'])
if args.ios_open_free:
    run('ios-open-original-free-reuse', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                        root / 'experiments/wii-static-recomp/verify_ios_open.py', '--original-free'])
    run('ios-free-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_open_ghidra.py', '--free'])
if args.ios_transport_roots:
    run('ios-transport-original-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ios_transport.py'])
    run('ios-transport-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py'])
if args.ios_transport_execution:
    run('ios-transport-native-original-boundaries', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                   root / 'experiments/wii-static-recomp/verify_ios_transport.py'])
if args.ios_transport_completion:
    run('ios-transport-kernel-completion', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                          root / 'experiments/wii-static-recomp/verify_ios_transport.py', '--kernel-completion'])
if args.ios_reply_handler:
    run('ios-reply-handler-native-original', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                             root / 'experiments/wii-static-recomp/verify_ios_transport.py', '--reply-handler'])
    run('ios-reply-handler-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--reply-handler'])
if args.ios_handler_completion:
    run('ios-original-handler-completion', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                           root / 'experiments/wii-static-recomp/verify_ios_transport.py', '--handler-completion'])
if args.ios_wakeup:
    run('ios-wakeup-native-original-queues', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                            root / 'experiments/wii-static-recomp/verify_ios_wakeup.py'])
    run('ios-wakeup-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--wakeup'])
if args.ios_wakeup_completion:
    run('ios-original-wakeup-completion', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                          root / 'experiments/wii-static-recomp/verify_ios_transport.py', '--wakeup-completion'])
if args.ios_select_thread:
    run('ios-select-thread-native-original', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                             root / 'experiments/wii-static-recomp/verify_ios_select_thread.py'])
    run('ios-select-thread-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--select-thread'])
if args.ios_default_switch_callback:
    run('ios-select-thread-default-callback', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                             root / 'experiments/wii-static-recomp/verify_ios_select_thread.py', '--default-callback'])
if args.ios_set_context:
    run('ios-selector-original-context-setting', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                root / 'experiments/wii-static-recomp/verify_ios_select_thread.py', '--set-context'])
    run('ios-set-context-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--set-context'])
if args.ios_load_context:
    run('ios-original-context-load-rfi', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                       root / 'experiments/wii-static-recomp/verify_ios_load_context.py'])
    run('ios-load-context-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--load-context'])
if args.ios_save_context:
    run('ios-original-context-save', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_ios_load_context.py', '--save-only'])
    run('ios-original-context-save-load', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                         root / 'experiments/wii-static-recomp/verify_ios_load_context.py', '--save-roundtrip'])
    run('ios-save-context-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--save-context'])
if args.ios_selector_context_transfer:
    run('ios-original-selector-context-transfer', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                root / 'experiments/wii-static-recomp/verify_ios_select_thread.py', '--context-transfer'])
if args.ios_sleep:
    run('ios-original-sleep-queue', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                   root / 'experiments/wii-static-recomp/verify_ios_wakeup.py', '--sleep'])
    run('ios-sleep-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--sleep'])
if args.ios_sleep_wakeup:
    run('ios-original-sleep-wakeup', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_ios_wakeup.py', '--sleep-wakeup'])
if args.ios_thread_cycle:
    run('ios-original-two-thread-cycle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                        root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py'])
if args.ios_thread_cycle_irqs:
    run('ios-original-two-thread-cycle-irqs', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                             root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--original-irqs'])
    run('ios-original-irq-primitives-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_irq_primitives_ghidra.py'])
if args.ios_deferred_wakeup:
    run('ios-original-deferred-wakeup-reschedule', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--deferred-wakeup'])
    run('ios-reschedule-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_irq_primitives_ghidra.py', '--reschedule'])
if args.ios_thread_reply_handler:
    run('ios-original-thread-reply-handler', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                            root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--reply-handler'])
if args.ios_thread_kernel_reply:
    run('ios-original-thread-kernel-reply', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                           root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--kernel-reply'])
if args.ios_thread_transport:
    run('ios-original-thread-transport', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                        root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--transport'])
if args.ios_thread_open_lifecycle:
    run('ios-original-thread-open-lifecycle', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                             root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--open-lifecycle'])
if args.ios_thread_heap_reuse:
    run('ios-original-thread-heap-reuse', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                         root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--heap-reuse'])
if args.ios_thread_allocation_failure:
    run('ios-original-thread-allocation-refusal', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--allocation-failure'])
if args.ios_thread_ipc_interrupt:
    run('ios-ipc-interrupt-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ios_transport.py', '--ipc-interrupt', '--compare-so'])
    run('ios-ipc-interrupt-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--ipc-interrupt'])
    run('ios-original-thread-ipc-interrupt', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                            root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--ipc-interrupt'])
if args.ios_thread_ipc_ack:
    run('ios-original-thread-ipc-ack', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                     root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--ipc-ack'])
if args.ios_thread_ipc_registers:
    run('ios-original-thread-ipc-registers', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                           root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--ipc-registers'])
if args.ios_thread_ipc_control:
    run('ios-original-thread-ipc-control', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                         root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--ipc-control'])
if args.ios_thread_ipc_irq:
    run('ios-original-thread-ipc-irq', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                     root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--ipc-irq'])
if args.ios_irq_dispatch_roots:
    run('ios-original-irq-dispatch-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ios_transport.py', '--irq-dispatch', '--compare-so'])
    run('ios-original-irq-dispatch-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--irq-dispatch'])
if args.ios_external_irq:
    run('ios-original-external-irq', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                    root / 'experiments/wii-static-recomp/verify_ios_load_context.py', '--external-irq'])
    run('ios-original-scheduler-guards-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--scheduler-guards'])
if args.ios_thread_external_irq:
    run('ios-original-external-dispatch-ipc-thread', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                   root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--external-irq'])
if args.ios_exception_vector:
    run('ios-original-exception-vector-analysis', ['python3', root / 'experiments/wii-static-recomp/analyze_ios_transport.py', '--exception-vector'])
    run('ios-original-exception-vector-ghidra', ['python3', root / 'experiments/wii-static-recomp/verify_ios_transport_ghidra.py', '--exception-vector'])
    run('ios-original-exception-vector-ipc-thread', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                   root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--exception-vector'])
if args.ios_vector_return:
    run('ios-original-vector-ipc-interrupted-b-return', ['arch', '-x86_64', '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                                                      root / 'experiments/wii-static-recomp/verify_ios_thread_cycle.py', '--vector-return'])
if args.ipc_reset_boot:
    if not args.audit_only:
        run('ipc-reset-scoped-boot-build', ['python3', root / 'experiments/wii-static-recomp/build_ipc_reset_boot.py'])
    run('ipc-reset-scoped-boot-audit', ['python3', root / 'experiments/wii-static-recomp/audit_ipc_reset_boot.py'])
print('IPC_RESET BOOT:validated original reset advances to guarded80217650; further hardware/full boot unverified' if args.ipc_reset_boot else
      'IOS_VECTOR RETURN:288original vector/IPC/Open/A sleep/B restoration comparisons; prepared entry/clock/full boot unverified' if args.ios_vector_return else
      'IOS_EXCEPTION VECTOR:288original vector/dispatch/IPC/resume comparisons at initial IR/DR0/1; copy/hardware entry/clock/full boot unverified' if args.ios_exception_vector else
      'IOS_THREAD EXTERNAL IRQ:144original dispatch/IPC/scheduler/resume comparisons; vector/time/ACK/full boot unverified' if args.ios_thread_external_irq else
      'IOS_EXTERNAL IRQ:192original entry/mask/handler-return/RFI comparisons; handler/time/vector preamble/full boot unverified' if args.ios_external_irq else
      'IOS_IRQ ROOTS:190original words compiled/Ghidra-checked; dispatcher/vector execution and full boot unverified' if args.ios_irq_dispatch_roots else
      'IOS_IPC IRQ:144original Open/thread cycles with prepared reply/latched PI/deferred dispatch; vector/cache/full boot unverified' if args.ios_thread_ipc_irq else
      'IOS_IPC CONTROL:144original Open/thread cycles with measured W1C/X2 storage; IRQFLAG/cache/real delivery/full boot unverified' if args.ios_thread_ipc_control else
      'IOS_IPC REGISTERS:8original helper instructions in144ACK/reply/Open/thread cycles; hardware backend/full boot unverified' if args.ios_thread_ipc_registers else
      'IOS_IPC ACK:144original ACK-then-reply/Open/thread cycles; queued-send/timeout/real IRQ/full boot unverified' if args.ios_thread_ipc_ack else
      'IOS_IPC INTERRUPT:144original reply-wrapper/Open/thread cycles; real IRQ/ACK/cache/full boot unverified' if args.ios_thread_ipc_interrupt else
      'IOS_ALLOCATION REFUSAL:144original small-heap returns-22/no-send/no-block cases; full heap/IRQ/boot unverified' if args.ios_thread_allocation_failure else
      'IOS_HEAP REUSE:144original completion/free cycles on one heap and2lost-event mutants; cache/MMIO/IRQ/full boot unverified' if args.ios_thread_heap_reuse else
      'IOS_OPEN LIFECYCLE:144heap/allocate/send/sleep/kernel/handler/resume/free cycles and lost-event mutant; cache/MMIO/IRQ/full boot unverified' if args.ios_thread_open_lifecycle else
      'IOS_THREAD TRANSPORT:144send/sleep/kernel/handler/resume/return-6 cycles and lost-event mutant; free/cache/IRQ/full boot unverified' if args.ios_thread_transport else
      'IOS_THREAD KERNEL REPLY:144kernel/event/handler/deferred-wakeup/A-resume cycles; transport/IRQ vector/full boot unverified' if args.ios_thread_kernel_reply else
      'IOS_THREAD REPLY HANDLER:144supplied OPEN reply/handler/deferred-wakeup/A-resume cycles; kernel/transport/IRQ vector/full boot unverified' if args.ios_thread_reply_handler else
      'IOS_DEFERRED WAKEUP:144three-phase mismatch/wakeup/reschedule cycles; actual IRQ handler/transport/full boot unverified' if args.ios_deferred_wakeup else
      'IOS_THREAD IRQ PRIMITIVES:144cycles/EE0-1/empty-event refusal; actual IRQ delivery/transport/full boot unverified' if args.ios_thread_cycle_irqs else
      'IOS_THREAD CYCLE:72prepared A-sleep/B-wake/A-resume cases at EE0; IRQ/transport/full boot unverified' if args.ios_thread_cycle else
      'IOS_SLEEP WAKEUP:144host-directed mixed-priority queue cycles; actual blocking/selector/IRQ/full boot unverified' if args.ios_sleep_wakeup else
      'IOS_SLEEP QUEUE:144priority insertion cases/59instructions; actual blocking/selector/IRQ/full boot unverified' if args.ios_sleep else
      'IOS_SELECTOR CONTEXT:1296cases/540prepared next entries/36self-resumptions at EE0; wakeup/IRQ/full boot unverified' if args.ios_selector_context_transfer else
      'IOS_SAVE CONTEXT:96save/96host-directed save-load cases at EE0; selector/IRQ/full boot unverified' if args.ios_save_context else
      'IOS_LOAD CONTEXT:384standalone register/GQR/SRR/RFI cases at EE0; actual save/selector/IRQ/boot unverified' if args.ios_load_context else
      'IOS_SET CONTEXT:1296cases/576OSLoadContext boundaries; actual context transfer/IRQ/boot unverified' if args.ios_set_context else
      'IOS_DEFAULT CALLBACK:216cases/96original callback returns to context-setting boundary; actual context/IRQ/boot unverified' if args.ios_default_switch_callback else
      'IOS_SELECT THREAD:216priority selection frontiers/139DOL instructions; actual context/IRQ/boot unverified' if args.ios_select_thread else
      'IOS_WAKEUP COMPLETION:80cases/6ready-queue returns/2drop mutants; real SelectThread/context/IRQ/boot unverified' if args.ios_wakeup_completion else
      'IOS_WAKEUP QUEUES:192cases, original links/state/ready mask; real SelectThread/context/IRQ/boot unverified' if args.ios_wakeup else
      'IOS_HANDLER COMPLETION:80cases/6kernel-handler-wakeup returns/2drop mutants; real OS/IRQ/cache/boot unverified' if args.ios_handler_completion else
      'IOS_REPLY HANDLER:32sync OPEN fixtures/150DOL instructions; real wakeup/IRQ/cache/boot unverified' if args.ios_reply_handler else
      'IOS_TRANSPORT COMPLETION:80cases/6actual kernel replies/negative drop test; synthetic sleep release, real IRQ/cache/boot unverified' if args.ios_transport_completion else
      'IOS_TRANSPORT EXECUTION:80fixture cases through original queue code to sleep/free; real MMIO/reply/IRQ/boot unverified' if args.ios_transport_execution else
      'IOS_TRANSPORT STATIC ROOT:144instructions/DOL/native object/Ghidra; execution/IOS/boot unverified' if args.ios_transport_roots else
      'IOS_OPEN ORIGINAL FREE:96cases/192opens/96frees, host-directed lifecycle; actual IOS/cache/IRQ/boot unverified' if args.ios_open_free else
      'IOS_OPEN ORIGINAL ALLOCATOR:96native/original cases; actual cache/IRQ/transport/boot unverified' if args.ios_open_allocator else
      'IOS_OPEN WRAPPER:96native/original cases with explicit services; actual IOS/cache/IRQ/boot unverified' if args.ios_open_wrapper else
      'ORIGINAL BUFFER CHAIN:16synthetic loader fixtures/128calls; actual SHSM allocation/IOS sender/boot unverified' if args.ipc_buffer_chain else
      'STATIC SDK ROOTS:10dtk labels/DOL bytes, register helpers independently decoded; original sender/boot unverified' if args.ipc_sdk_roots else
      'BOUNDED IPC PRODUCER:8full64-byte reply/event cases and12malformed guards; original sender/GPIO/full boot unverified' if args.ipc_producer else
      'ISOLATED IPC PENDING:8original ACK/reply reset states and existing scheduler causal test; IOS/GPIO/full boot unverified' if args.ipc_pending else
      'ISOLATED IPC RESET:32original controls/8original-native stores, live refusal retained; IOS/events/GPIO/full reset unverified' if args.ipc_reset else
      'BOUNDED PI MASK:32original/native EE0cases/7guards, existing vendor state; IPCmask/delivery/full boot unverified' if args.pi_mask else
      'EXACT MMIO:802175D0→CC003004/valueF0/physical0C003004, writes remain refused' if args.mmio_observer else
      'BOUNDED RESET:32original/32native copies,10rollback/38stale-entry guards; new MMIO boundary/full vectors unverified' if args.template_reset else
      'EXACT RESET:80211B0C→80211C08/38600000, physical211C08; reset remains blocked, original execution/vector endpoint pending' if args.table_observer else
      'BOUNDED NOP:32originalstorecases/combinedcopies,10rollbackguards/38staleentries; live80211A7C/full real vector endpoint unverified' if args.template_nop else
      'BOUNDED TEMPLATE PATCH:32original patch/copy cases,10rollbackguards/38compiledentryrefusals; next template write/full OS-vector endpoint pending' if args.template_patch else
      'BOUNDED FP64:sixforms/320original observations Mac+Windows helpers, fullmodule memcpy32NI0-NI1cases; mutable-code/vector boot pending' if args.fp64 else
      'BOUNDED TEMPLATE:exact original store observed; Dolphin NI0/NI1 copies exact, nativeNI0 matches; NI1 bit-transfer/mutable-code adaptations pending' if args.template_copy else
      'BOUNDED NI MODE:verified setter/strict FP guards; live compiled-code write boundary, full endpoint/menu unverified' if args.ni_guard else
      'BOUNDED ROOTS:three omitted functions/532instructions compiled in isolation; two Ghidra boundary checks; runtime integration pending' if args.frsp_roots else
      'BOUNDED FRSP:256original observations, 1166addresses lowered; NI activation/other FP/menu pending; production unchanged' if args.frsp else
      'BOUNDED NI NUMBERS:32original frsp observations; FPSCR flags/other FP operations/runtime activation pending; production unchanged' if args.ni_numeric else
      'BOUNDED SPD:original function8cases/4guards verified; live FPSCR mode/full endpoint pending; production unchanged' if args.spd else
      'BOUNDED BAT:HID4/rotate ISA verified; shared frontend integrated, live nextHID0C200/full endpoint pending; production unchanged' if args.bat else
      'BOUNDED HID4:8original function/alias observations; isolated BAT core only, live activation pending; production unchanged' if args.hid4 else
      'BOUNDED RESET:6original setters/8observations/8guards; live80210840 endpoint and clock epoch pending; production unchanged' if args.performance else
      'BOUNDED CONSUMER:original OS time64cases; live SPR952 endpoint/RTC epoch pending; production unchanged' if args.os_time else
      'BOUNDED READER:controlled timebase retry/provider verified; live OS clock and RTC epoch pending; production unchanged' if args.timebase else
      'BOUNDED BOOT:immediate carry corrected; normalized early OS CPU endpoint matches; timebase pending; production unchanged' if args.carry else
      'EVIDENCE:guarded polling advanced boot; XER.CA gap remains; early OS prefix NOT accepted; production unchanged' if args.poll else
      'BOUNDED BOOT:conditional polling corrected; accurate-cache __init_data endpoint; scheduler contract pending; production unchanged' if args.branch else
      'BOUNDED BOOT:L2 register endpoint matches; next not-taken-branch scheduler lowering; production unchanged' if args.l2 else
      'BOUNDED BOOT:DCE enabled; accurate-cache endpoint matches; next L2CR; production unchanged' if args.dcache else
      'BOUNDED CACHE:8conflict trials/160samples; cache-enabled bootstrap pending; production unchanged' if args.cache_conflict else
      'BOUNDED FRONTEND:125objects; accurate five samples; cache-enabled bootstrap pending; production unchanged' if args.memory_frontend else
      'EVIDENCE:cache gap confirmed; DCEnable not accepted; production unchanged' if args.coherence else
      'PASS:bounded static-recompilation milestone; production release unchanged', flush=True)
