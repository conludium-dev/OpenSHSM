"""Verify observed callback/queued packets and distinguish populated OS context from empty fixture."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/audit_interrupt_enable_boot.py')
body = parent.read_text().replace('mass-interrupt-enable-observer', 'mass-interrupt-context-observer')
body = body.replace('observe_interrupt_enable_boot.py', 'observe_interrupt_context_boot.py')
body = body.replace('experiment_interrupt_enable_observe', 'experiment_interrupt_context_observe')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
root = Path('work/private-game/static-recomp')
output = root / 'mass-interrupt-context-observer'
build = json.loads((output / 'build.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert build['parentBuilderSha256'] == sha(Path('experiments/wii-static-recomp/observe_interrupt_enable_boot.py'))
log = (output / 'observed-boot.log').read_text()
def values(tag):
    lines = [line for line in log.splitlines() if line.startswith(tag + ' ')]
    assert len(lines) == 1
    return [int(value, 16) for value in lines[0].split()[1:]]
context = values('IRQ_ENABLE_CONTEXT')
assert len(context) == 1 + 0x1c8 // 4 and context[0] == 0x80492658
words = context[1:]
assert words[0x198 // 4] == 0x800060f4 and words[0x19c // 4] == 0x32
assert words[0x1a0 // 4] == 0 and any(words)
memory = values('IRQ_ENABLE_SI_MEMORY')
state = dict(zip(memory[::2], memory[1::2]))
assert state[0x800000d8] == 0x80492658
assert state[0x8042b6f0] == 0 and state[0x8042b6f8] == 3 and state[0x8042b6fc] == 0x8042b708
assert state[0x8042b700] == 0x80210110
assert all(state[address] == 0x80 for address in (0x8042b708, 0x8042b70c, 0x8042b710, 0x8042b714))
packets = values('IRQ_ENABLE_PACKETS')
assert len(packets) == 32 and packets[0] == 0xffffffff
for index in range(1, 4):
    packet = packets[index * 8:(index + 1) * 8]
    assert packet[:6] == [index, 0x8052aa28, 1, 0x8042b708 + index * 4, 3, 0x80210110]
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'STARTUP_CALLBACK_PRESENT_THREE_QUEUED_SI_PACKETS_POPULATED_CONTEXT_CONFIRMED'
report['parentAuditorSha256'] = sha(parent)
report['callback'] = '80210110'
report['queue'] = packets
report['contextWords'] = words
report['inferredBehavior'] = 'Boot has callback-present active port0 and queued ports1..3; prior null-callback hypothesis disproved.'
report['limits'] += ['Observed context retains first-use FPU saved state; not the empty original SI fixture.',
    'Queued original handler/timing/context execution still needs verification before boot delivery.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS callback80210110 PRESENT/active0/queued1..3; originalFPU-owned populatedcontext retained; no delivery enabled')
