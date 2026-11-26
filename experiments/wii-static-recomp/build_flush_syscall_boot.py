"""Extend the existing FPU boot builder with the verified flush syscall profile."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_fpu_boot.py')
body = parent.read_text()
body = body.replace("output = private / 'mass-fpu-boot'", "output = private / 'mass-flush-syscall-boot'")
body = body.replace("base = private / 'mass-ai-clock-boot'", "base = private / 'mass-fpu-boot'")
body = body.replace('verify_fpu_first_use_native.py', 'verify_flush_syscall_native.py').replace('fpu-first-use-native', 'flush-syscall-native')
body = body.replace('context.fpuFirstUse = !std::getenv("SHSM_FPU_DISABLED")', 'context.flushSyscall = !std::getenv("SHSM_FLUSH_DISABLED")')
body = body.replace('BOOT_FPU entries=', 'BOOT_FLUSH entries=').replace('context.fpuEntries', 'context.flushEntries')
body = body.replace('context.exceptionVector', 'context.flushPhase').replace(' vector=', ' phase=')
body = body.replace('context.fpuResume', 'context.flushBarriers').replace(' resume=', ' barriers=')
body = body.replace('#include "fpu_first_use.h"', '#include "flush_syscall.h"')
start = body.index('stack_marker = ')
end = body.index('wrapper.write_text(wrapper_body)', start)
body = body[:start] + body[end:]
start = body.index("removed_policy_entry = '80211BA0")
end = body.index('results = {}', start)
body = body[:start] + "removed_policy_entry = ''\npolicy.write_bytes(policy_input.read_bytes())\n" + body[end:]
body = body.replace("('SHSM_FPU_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY')", "('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY')")
body = body.replace("environment['SHSM_FPU_DISABLED'] = '1'", "environment['SHSM_FLUSH_DISABLED'] = '1'")
body = body.replace("'BOOT_FPU '", "'BOOT_FLUSH '")
body = body.replace("native['headerHashes']", "native['inputHashes']")
body = body.replace('FPU_BOOT_REQUIRES_BOUNDARY_AUDIT', 'FLUSH_SYSCALL_BOOT_REQUIRES_BOUNDARY_AUDIT')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-flush-syscall-boot/boot.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Copied C00 vector executes through existing dispatcher; HID0 uses existing CPU storage with a scoped bit8 transition.',
    'Sequential host fence and synchronous D-cache writeback are PC adaptations, not physical Wii timing/order.',
    'Next guard retained; no original frame/menu/audio or full-game proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
