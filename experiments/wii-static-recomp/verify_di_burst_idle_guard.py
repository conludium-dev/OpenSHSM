"""Component-test the real bounded wait predicate against measured native words."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-idle-boot'
subprocess.run(['python3', str(experiment / 'verify_di86_idle_native.py')], check=True)
report = json.loads((root / 'mass-di86-idle-observer/observation.json').read_text())
words = {}
regions = {'DI86_IDLE_PACKET': 0x935e0080, 'DI86_IDLE_QUEUED_PACKET': 0x935e00e0,
    'DI86_IDLE_WAIT_PACKET': 0x935e0140, 'DI86_IDLE_CALLBACK': 0x804983a0,
    'DI86_IDLE_REQUEST_QUEUE': 0x804b2a80, 'DI86_IDLE_THREAD': 0x80492920}
for line in report['observations']:
    tag, *values = line.split()
    if tag in regions:
        data = bytes(map(int, values))
        for offset in range(0, len(data), 4):
            words[regions[tag] + offset] = int.from_bytes(data[offset:offset + 4], 'big')
initializers = ',\n'.join('{0x%x, 0x%x}' % pair for pair in sorted(words.items()))
source = '''#include <array>
#include <cstdint>
#include <map>
#include <iostream>
namespace nwii::runtime {
struct CPUContext {};
unsigned stmSubmitted = 32;
std::map<uint32_t, uint32_t> measured{INITIALIZERS};
uint32_t bat_memory_read32(CPUContext&, uint32_t address) { return measured[address]; }
namespace hw {
struct Snapshot { uint32_t ppcMessage; uint32_t ppcControl; };
Snapshot state{0x135e0080, 0x32};
Snapshot experiment_ipc_snapshot() { return state; }
}
}
#include "di_burst_idle.h"
int main() {
    using namespace nwii::runtime;
    CPUContext context;
    if (!experiment_di_burst_wait(context)) { return 1; }
    unsigned rejected = 0;
    for (auto& [address, value] : measured) {
        value ^= 1;
        if (!experiment_di_burst_wait(context)) { ++rejected; }
        value ^= 1;
    }
    for (auto* value : {&stmSubmitted, &hw::state.ppcMessage, &hw::state.ppcControl}) {
        *value ^= 1;
        if (experiment_di_burst_wait(context)) { return 2; }
        *value ^= 1;
        ++rejected;
    }
    if (!experiment_di_burst_wait(context) || rejected != 36) { std::cout << rejected << "\\n"; return 3; }
    std::cout << "BOUNDED_WAIT_COMPONENT_36_MUTANTS_PASS\\n";
}
'''.replace('INITIALIZERS', initializers)
host = output / 'idle-guard-probe.cpp'
host.write_text(source)
exe = output / 'idle-guard-probe'
result = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'idle-guard-tests.json').write_text(json.dumps({
    'result': 'BOUNDED_WAIT_COMPONENT_PASS', 'mutantsRejected': 36,
    'verifierSha256': sha(Path(__file__)), 'guardSha256': sha(experiment / 'di_burst_idle.h'),
    'nativeObservationSha256': sha(root / 'mass-di86-idle-observer/observation.json'),
    'limits': ['Component predicate test uses measured word map, not live OS/kernel/IRQ execution proof.']}, indent=2) + '\n')
print(result.stdout.strip())
