"""Component-test actual bounded flush predicate; stubs are not syscall execution."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-es-di-ticket-flush-boot')
source = r'''#include <array>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <iostream>
namespace nwii::runtime {
struct CPUContext { uint32_t msr = 0xa032, lr = 0x80242fc8; std::array<uint32_t,32> gpr{}; };
unsigned stmSubmitted = 36, experimentDiBurstInputInvalidates = 1;
bool experimentDiBurstFirstRetired = true;
bool pending = true;
namespace devices { const void* experiment_stm_pending() { return pending ? &pending : nullptr; } }
std::map<uint32_t,uint32_t> words;
uint32_t bat_memory_read32(CPUContext&, uint32_t address) { return words[address]; }
}
#include "es_di_ticket_flush.h"
int main() {
    using namespace nwii::runtime;
    CPUContext c;
    c.gpr[3] = 0x80540060; c.gpr[4] = 7; c.gpr[27] = 8;
    c.gpr[29] = 0x935e0080; c.gpr[30] = 0x8053ff10;
    const std::array<uint32_t,8> packet{7,1,4,0x1b,1,1,0x8053ff10,0};
    for (unsigned i = 0; i < 8; ++i) { words[0x935e0080 + i*4] = packet[i]; }
    words[0x8053ff10] = 0; words[0x8053ff14] = 0; words[0x8053ff18] = 0x8053ff80; words[0x8053ff1c] = 216;
    if (!experiment_es_di_ticket_flush(c)) { return 1; }
    unsigned refused = 0;
    for (auto& [address, value] : words) {
        value ^= 1;
        if (experiment_es_di_ticket_flush(c)) { return 2; }
        value ^= 1; ++refused;
    }
    for (auto* value : std::array<uint32_t*,9>{&c.msr,&c.lr,&c.gpr[3],&c.gpr[4],&c.gpr[27],&c.gpr[29],&c.gpr[30],&stmSubmitted,&experimentDiBurstInputInvalidates}) {
        *value ^= 1;
        if (experiment_es_di_ticket_flush(c)) { return 3; }
        *value ^= 1; ++refused;
    }
    pending = false; if (experiment_es_di_ticket_flush(c)) { return 4; } pending = true; ++refused;
    experimentDiBurstFirstRetired = false; if (experiment_es_di_ticket_flush(c)) { return 5; } experimentDiBurstFirstRetired = true; ++refused;
    setenv("SHSM_ES_DI_TICKET_FLUSH_DISABLED","1",1);
    if (experiment_es_di_ticket_flush(c)) { return 6; }
    unsetenv("SHSM_ES_DI_TICKET_FLUSH_DISABLED"); ++refused;
    c.lr = 0x80243068; c.gpr[3] = 0x8053ff30; c.gpr[4] = 1; words[0x8053ff18] = 0x53ff80;
    if (!experiment_es_di_ticket_flush(c) || refused != 24) { return 7; }
    c.gpr[3] = 0x8053ff20; if (experiment_es_di_ticket_flush(c)) { return 8; }
    std::cout << "TICKET_FLUSH_COMPONENT_TWO_SITES_25_REFUSALS_PASS\n";
}
'''
host = output / 'flush-guard-probe.cpp'
host.write_text(source)
exe = output / 'flush-guard-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'flush-guards.json').write_text(json.dumps({'result': 'FLUSH_COMPONENT_PASS',
    'refusals': 25, 'verifierSha256': sha(Path(__file__)), 'predicateSha256': sha(experiment / 'es_di_ticket_flush.h'),
    'limits': ['Actual predicate against stub words/pending state; real syscall and coherency audited separately.']}, indent=2) + '\n')
print(result.stdout.strip())
