"""Test actual flush guard on measured stub words, not original syscall execution."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-playrecord-open-flush-boot')
source = r'''#include <array>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <iostream>
namespace nwii::runtime {
struct CPUContext { uint32_t msr = 0xa032, lr = 0x8024250c; std::array<uint32_t,32> gpr{}; };
unsigned stmSubmitted = 42;
bool experimentPostConsumptionClosed = true, pending = true;
namespace devices { const void* experiment_stm_pending() { return pending ? &pending : nullptr; } }
std::map<uint32_t,uint32_t> words;
std::map<uint32_t,uint8_t> bytes;
uint32_t bat_memory_read32(CPUContext&, uint32_t address) { return words.at(address); }
uint8_t bat_memory_read8(CPUContext&, uint32_t address) { return bytes.at(address); }
}
#include "playrecord_open_flush.h"
int main() {
    using namespace nwii::runtime;
    CPUContext c;
    c.gpr[3] = 0x935e1060; c.gpr[4] = 2; c.gpr[27] = 0x935e1020; c.gpr[28] = 3;
    c.gpr[29] = 0x80240680; c.gpr[30] = 0; c.gpr[31] = 0x935e0080;
    const std::array<uint32_t,10> packet{1,0,0,0x16,1,2,0x8053fd70,0,0x80240680,0x935e1020};
    for (unsigned i = 0; i < packet.size(); ++i) { words[0x935e0080 + i * 4] = packet[i]; }
    words[0x80528ce8] = 0xffffffff; words[0x804b2b4c] = 0x935e00c0;
    words[0x935e1120] = 0x80244e30; words[0x935e1124] = 0x8049325c; words[0x935e1128] = 0;
    constexpr char path[] = "/title/00000001/00000002/data/play_rec.dat";
    for (unsigned i = 0; i < sizeof(path); ++i) { bytes[0x935e1020 + i] = uint8_t(path[i]); }
    if (!experiment_playrecord_open_flush(c)) { return 1; }
    unsigned refused = 0;
    for (auto& [address,value] : words) {
        value ^= 1;
        if (experiment_playrecord_open_flush(c)) { return 2; }
        value ^= 1; ++refused;
    }
    for (auto& [address,value] : bytes) {
        value ^= 1;
        if (experiment_playrecord_open_flush(c)) { return 3; }
        value ^= 1; ++refused;
    }
    for (auto* value : std::array<uint32_t*,10>{&c.msr,&c.lr,&c.gpr[3],&c.gpr[4],&c.gpr[27],&c.gpr[28],&c.gpr[29],&c.gpr[30],&c.gpr[31],&stmSubmitted}) {
        *value ^= 1;
        if (experiment_playrecord_open_flush(c)) { return 4; }
        *value ^= 1; ++refused;
    }
    for (bool* flag : {&pending,&experimentPostConsumptionClosed}) {
        *flag = false;
        if (experiment_playrecord_open_flush(c)) { return 5; }
        *flag = true; ++refused;
    }
    setenv("SHSM_PLAYRECORD_FLUSH_DISABLED","1",1);
    if (experiment_playrecord_open_flush(c)) { return 6; }
    unsetenv("SHSM_PLAYRECORD_FLUSH_DISABLED"); ++refused;
    if (!experiment_playrecord_open_flush(c) || refused != 71) { std::cerr << refused; return 7; }
    std::cout << "PLAYRECORD_PATH_FLUSH_COMPONENT71_REFUSALS_PASS\n";
}
'''
host = output / 'flush-guard-probe.cpp'
host.write_text(source)
exe = output / 'flush-guard-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'flush-guards.json').write_text(json.dumps({'result': 'PLAYRECORD_FLUSH_COMPONENT71_REFUSALS_PASS',
    'refusals': 71, 'verifierSha256': sha(Path(__file__)), 'predicateSha256': sha(experiment / 'playrecord_open_flush.h'),
    'limits': ['Actual predicate with stub storage/pending state; not an original callback, syscall, service or file-write oracle.']}, indent=2) + '\n')
print(result.stdout.strip())
