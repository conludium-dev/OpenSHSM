"""Exercise the exact flush predicate with stub storage; no syscall claim."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-playrecord-seek-boot')
source = r'''#include <array>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <iostream>
namespace nwii::runtime {
struct CPUContext { uint32_t msr = 0x32,lr = 0x80242240; std::array<uint32_t,32> gpr{}; };
unsigned stmSubmitted = 46;
bool experimentPlayrecordReadReplied = true,pending = true;
namespace devices { const void* experiment_stm_pending() { return pending ? &pending : nullptr; } }
std::map<uint32_t,uint32_t> words;
uint32_t bat_memory_read32(CPUContext&,uint32_t address) { return words.at(address); }
}
#include "playrecord_seek_flush.h"
int main() {
    using namespace nwii::runtime;
    CPUContext context;
    context.gpr[3] = 0x935e00a0;
    context.gpr[4] = 1;
    words[0x804931d0] = 4;
    words[0x80528a40] = 3;
    words[0x8052ab40] = 1;
    words[0x804b2b4c] = 0x935e0120;
    words[0x935e1120] = 0x802464b0;
    words[0x935e1124] = 0x8049325c;
    words[0x80493260] = 0x8021cde0;
    const std::array<uint32_t,10> packet{5,4,4,0,0,2,0x8053fd70,0,0x80240680,0x935e1020};
    for (unsigned i = 0; i < packet.size(); ++i) { words[0x935e0080 + i * 4] = packet[i]; }
    if (!experiment_playrecord_seek_flush(context)) { return 1; }
    unsigned refused = 0;
    for (auto& [address,value] : words) {
        value ^= 1;
        if (experiment_playrecord_seek_flush(context)) { return 2; }
        value ^= 1;
        ++refused;
    }
    for (auto* value : {&context.msr,&context.lr,&context.gpr[3],&context.gpr[4],&stmSubmitted}) {
        *value ^= 1;
        if (experiment_playrecord_seek_flush(context)) { return 3; }
        *value ^= 1;
        ++refused;
    }
    for (bool* flag : {&pending,&experimentPlayrecordReadReplied}) {
        *flag = false;
        if (experiment_playrecord_seek_flush(context)) { return 4; }
        *flag = true;
        ++refused;
    }
    setenv("SHSM_PLAYRECORD_SEEK_DISABLED","1",1);
    if (experiment_playrecord_seek_flush(context)) { return 5; }
    unsetenv("SHSM_PLAYRECORD_SEEK_DISABLED");
    ++refused;
    if (refused != 25 || !experiment_playrecord_seek_flush(context)) { return 6; }
    std::cout << "PLAYRECORD_SEEK_FLUSH25_REFUSALS_PASS\n";
}
'''
host = output / 'seek-flush-guard.cpp'
host.write_text(source)
exe = output / 'seek-flush-guard'
compiled = subprocess.run(['clang++','-std=c++20','-I',str(experiment),str(host),'-o',str(exe)],capture_output=True,text=True)
assert compiled.returncode == 0,compiled.stderr
result = subprocess.run([str(exe)],capture_output=True,text=True)
assert result.returncode == 0 and not result.stderr,result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'seek-flush-guards.json').write_text(json.dumps({'result':'PLAYRECORD_READ_FLUSH_COMPONENT25_REFUSALS_PASS',
    'verifierSha256':sha(Path(__file__)),'predicateSha256':sha(experiment / 'playrecord_seek_flush.h'),
    'refusals':25,'limits':['Exact predicate with stub words/flags, not whole original syscall/IOS/IRQ execution.']},indent=2) + '\n')
print(result.stdout.strip())
