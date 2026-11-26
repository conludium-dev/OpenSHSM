"""Component-test measured cache rule; stub storage is not a full cache proof."""
from pathlib import Path
import json
import subprocess
import hashlib

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-di-burst-cache-boot')
source = r'''#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <stdexcept>
namespace nwii::runtime {
struct CPUContext { uint32_t pc=0x80212fa0,lr=0x80241d88,msr=0x30,ctr=1; std::array<uint32_t,32> gpr{}; };
unsigned stmSubmitted=36;
bool experimentDiBurstFirstRetired=false;
uint32_t experimentDiBurstReplyOwner=0x135e0080;
namespace hw {
struct ExperimentIpcSnapshot { uint32_t ppcMessage=0x135e0140,armMessage=0x135e0080,ppcControl=0x30; } state;
ExperimentIpcSnapshot experiment_ipc_snapshot() { return state; }
}
bool experiment_di_burst_arm_match(uint32_t message,uint32_t arm) { return message==0x135e0140 && arm==experimentDiBurstReplyOwner; }
std::map<uint32_t,uint32_t> words;
uint32_t bat_memory_read32(CPUContext&,uint32_t address) { return words[address]; }
void bat_memory_cache_operation(CPUContext&,uint32_t,unsigned) { throw std::runtime_error("Unverified fallback"); }
}
#include "di_burst_cache_adapter.h"
int main() {
    using namespace nwii::runtime;
    CPUContext c; c.gpr[4]=1; c.gpr[31]=0x935e0080;
    const std::array<uint32_t,8> packet{8,1,6,0x86,0x135e2560,32,0,0};
    for(unsigned i=0;i<8;++i) { words[0x935e0080+i*4]=packet[i]; }
    words[0x804983a8]=0x01000000; words[0x804b2b4c]=0x935e0180;
    unsigned refused=0;
    auto attempt=[&](uint32_t address=0x135e2560,unsigned operation=470) {
        try { experiment_di_burst_cache_operation(c,address,operation); }
        catch(const std::runtime_error&) { ++refused; return true; }
        return false;
    };
    for(auto& [address,value]:words) { value^=1; if(!attempt()) { return 1; } value^=1; }
    for(auto* value:std::array<uint32_t*,8>{&c.pc,&c.lr,&c.msr,&c.ctr,&c.gpr[4],&c.gpr[31],&stmSubmitted,&hw::state.armMessage}) {
        *value^=1; if(!attempt()) { return 2; } *value^=1;
    }
    if(!attempt(0x135e2580)||!attempt(0x135e2560,86)||refused!=20||experimentDiBurstInputInvalidates) { return 3; }
    const auto saved=c.gpr;
    experiment_di_burst_cache_operation(c,0x135e2560,470);
    if(c.gpr!=saved||c.pc!=0x80212fa0||c.lr!=0x80241d88||c.msr!=0x30||c.ctr!=1||experimentDiBurstInputInvalidates!=1) { return 4; }
    if(!attempt()||refused!=21) { return 5; }
    hw::state.ppcControl=0x3c;
    experimentDiBurstReplyOwner=0x135e0140; hw::state.armMessage=0x135e0140;
    if(experiment_di_burst_reply_ready(hw::state)) { return 6; }
    experimentDiBurstFirstRetired=true;
    if(!experiment_di_burst_reply_ready(hw::state)) { return 7; }
    stmSubmitted=35; if(experiment_di_burst_reply_ready(hw::state)) { return 8; }
    std::cout << "CACHE_COMPONENT_21_REFUSALS_STATE_PRESERVED_X2_GUARD_PASS\n";
}
'''
host = output / 'cache-guard-probe.cpp'
host.write_text(source)
exe = output / 'cache-guard-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'cache-guards.json').write_text(json.dumps({'result': 'CACHE_COMPONENT_PASS',
    'refusals': 21, 'guardSha256': sha(experiment / 'di_burst_cache_adapter.h'), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Actual rule with stub word storage/cache fallback/owner predicate, not hidden-cache or physical Wii verification.']}, indent=2) + '\n')
print(result.stdout.strip())
