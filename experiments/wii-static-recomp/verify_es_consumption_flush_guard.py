"""Mutation-test actual flush predicate on measured words; not a syscall oracle."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-es-consumption-flush-boot')
source = r'''#include <array>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <iostream>
namespace nwii::runtime {
struct CPUContext { uint32_t msr = 0xa032, lr = 0; std::array<uint32_t,32> gpr{}; };
unsigned stmSubmitted = 38, experimentInquiryInputInvalidates = 1;
bool experimentInquiryTicketReturned = true, experimentInquiryReplyActive = true, pending = true;
namespace devices { const void* experiment_stm_pending() { return pending ? &pending : nullptr; } }
std::map<uint32_t,uint32_t> words;
uint32_t bat_memory_read32(CPUContext&, uint32_t address) { return words.at(address); }
uint16_t bat_memory_read16(CPUContext&, uint32_t address) { return uint16_t(words.at(address)); }
}
#include "es_consumption_flush.h"
int main() {
    using namespace nwii::runtime;
    unsigned refused = 0;
    for (unsigned site = 0; site < 3; ++site) {
        CPUContext c;
        c.gpr[29] = 0x935e0080; c.gpr[30] = 0x8053fd70;
        const std::array<uint32_t,8> packet{7,0,4,0x16,1,2,0x8053fd70,0};
        for (unsigned i = 0; i < 8; ++i) { words[0x935e0080 + i*4] = packet[i]; }
        const std::array<uint32_t,6> vectors{site == 2 ? 0x53fca0u : 0x8053fca0u,8,0,0,site ? 0x53fcc0u : 0x8053fcc0u,4};
        for (unsigned i = 0; i < 6; ++i) { words[0x8053fd70 + i*4] = vectors[i]; }
        words[0x804983c8] = 0; words[0x8052ac50] = 0;
        words[0x804b2b4c] = 0x935e00c0; words[0x800030e6] = 0x8002;
        c.lr = site == 0 ? 0x80242fc8 : site == 1 ? 0x80243020 : 0x80243068;
        c.gpr[3] = site == 0 ? 0x8053fce0 : site == 1 ? 0x8053fcc0 : 0x8053fdb0;
        c.gpr[4] = site == 2 ? 2 : 1;
        c.gpr[27] = site == 0 ? 8 : 0; c.gpr[28] = site == 0 ? 8 : 0;
        if (!experiment_es_consumption_flush(c)) { return 1; }
        for (auto& [address,value] : words) {
            value ^= 1;
            if (experiment_es_consumption_flush(c)) { return 2; }
            value ^= 1; ++refused;
        }
        for (auto* value : std::array<uint32_t*,8>{&c.msr,&c.lr,&c.gpr[3],&c.gpr[4],&c.gpr[29],&c.gpr[30],&stmSubmitted,&experimentInquiryInputInvalidates}) {
            *value ^= 1;
            if (experiment_es_consumption_flush(c)) { return 3; }
            *value ^= 1; ++refused;
        }
        if (site < 2) {
            for (unsigned index : {27u,28u}) {
                c.gpr[index] ^= 1;
                if (experiment_es_consumption_flush(c)) { return 4; }
                c.gpr[index] ^= 1; ++refused;
            }
        }
        for (bool* flag : {&pending,&experimentInquiryTicketReturned,&experimentInquiryReplyActive}) {
            *flag = false;
            if (experiment_es_consumption_flush(c)) { return 5; }
            *flag = true; ++refused;
        }
        setenv("SHSM_ES_CONSUMPTION_FLUSH_DISABLED","1",1);
        if (experiment_es_consumption_flush(c)) { return 6; }
        unsetenv("SHSM_ES_CONSUMPTION_FLUSH_DISABLED"); ++refused;
        if (!experiment_es_consumption_flush(c)) { return 7; }
    }
    if (refused != 94) { std::cerr << refused; return 8; }
    std::cout << "ES16_FLUSH_THREE_SITES_COMPONENT94_REFUSALS_PASS\n";
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
(output / 'flush-guards.json').write_text(json.dumps({'result': 'ES16_FLUSH_COMPONENT94_REFUSALS_PASS',
    'refusals': 94, 'verifierSha256': sha(Path(__file__)), 'predicateSha256': sha(experiment / 'es_consumption_flush.h'),
    'limits': ['Actual predicate on stub word storage/pending state; not syscall/cache/coherency or original execution proof.']}, indent=2) + '\n')
print(result.stdout.strip())
