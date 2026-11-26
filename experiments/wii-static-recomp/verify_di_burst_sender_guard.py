"""Test real sender guard with measured inputs; stubs do not prove full runtime."""
from pathlib import Path
import json
import subprocess
import hashlib

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-sender-boot'
native = json.loads((root / 'mass-di86-idle-observer/observation.json').read_text())
values = {line.split()[0]: line.split()[1:] for line in native['observations']}
regions = {'DI86_IDLE_QUEUED_PACKET': 0x935e00e0, 'DI86_IDLE_WAIT_PACKET': 0x935e0140,
    'DI86_IDLE_CALLBACK': 0x804983a0, 'DI86_IDLE_REQUEST_QUEUE': 0x804b2a80,
    'DI86_IDLE_THREAD': 0x80492920}
memory = {0x800000d4: 0x80492a70, 0x800000e4: 0}
for tag, address in regions.items():
    raw = bytes(map(int, values[tag]))
    for byte in range(0, len(raw), 4):
        memory[address + byte] = int.from_bytes(raw[byte:byte + 4], 'big')
packet = bytes(map(int, values['DI86_IDLE_QUEUED_PACKET']))[:32] + bytes(32)
source = r'''#include <array>
#include <cstdint>
#include <map>
#include <vector>
#include <stdexcept>
#include <iostream>
namespace nwii::runtime {
struct CPUContext { uint32_t msr = 0x30, pc = 0x80241c30, lr = 0x8024204c; bool in_callback = false; unsigned callback_depth = 0; std::vector<unsigned> backup_stack; };
unsigned stmSubmitted = 32;
std::map<uint32_t,uint32_t> measured{WORDS};
std::array<uint8_t,64> packet{BYTES};
uint32_t bat_memory_read32(CPUContext&, uint32_t address) { return measured[address]; }
uint32_t experiment_ipc_be32(const uint8_t* p) { return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3]; }
const uint8_t* experiment_ipc_mem1_span(CPUContext&,uint32_t address,unsigned size) { if(address!=0x135e00e0||size!=64) { throw std::runtime_error("span"); } return packet.data(); }
struct Bat { unsigned dbat=0, hid4=0; } bat;
Bat& bat_context(CPUContext&) { return bat; }
struct Mapping { uint32_t physical; unsigned slot, wimg; };
Mapping resolve_reference_bat(unsigned,unsigned,uint32_t,uint32_t address,bool) { return {address & 0x1fffffff,1,5}; }
namespace hw {
struct Snapshot { uint32_t ppcMessage=0x135e0080,armMessage=0x135e0080,ppcControl=0x30,armControl=0,ppcMask=0x40000000; int delay=0; } state;
Snapshot experiment_ipc_snapshot() { return state; }
struct Mask { unsigned load() { return 0x40f8; } } pi_intmr;
}
struct MMIODispatcher { static MMIODispatcher& get() { static MMIODispatcher v; return v; } void write32(uint32_t address,uint32_t value) { if(address!=0xcd000000) { throw std::runtime_error("address"); } hw::state.ppcMessage=value; } };
}
#include "di_burst_sender.h"
namespace nwii::runtime {
void experiment_di_burst_ack(CPUContext&,uint32_t request) { experimentDiBurstPending[1]=request; }
}
int main() {
    using namespace nwii::runtime;
    CPUContext c;
    experimentDiBurstPending[0]=0x135e0080;
    unsigned refused=0;
    for(unsigned i=0;i<64;++i) {
        packet[i]^=1;
        try { if(experiment_di_burst_sender_write(c,0xcd000000,0x135e00e0)) { return 1; } }
        catch(const std::runtime_error&) { ++refused; }
        packet[i]^=1;
    }
    const std::array<uint32_t,10> critical{0x800000d4,0x800000e4,0x80492934,0x935e016c,0x935e0170,0x804b2a80,0x804b2a84,0x935e0100,0x935e0104,0x804983cc};
    for(auto address:critical) {
        measured[address]^=1;
        try { if(experiment_di_burst_sender_write(c,0xcd000000,0x135e00e0)) { return 2; } }
        catch(const std::runtime_error&) { ++refused; }
        measured[address]^=1;
    }
    for(unsigned i=0;i<5;++i) {
        auto* value=i==0?&hw::state.ppcControl:i==1?&hw::state.armMessage:i==2?&hw::state.armControl:i==3?&hw::state.ppcMask:&experimentDiBurstPending[0];
        *value^=1;
        try { if(experiment_di_burst_sender_write(c,0xcd000000,0x135e00e0)) { return 3; } }
        catch(const std::runtime_error&) { ++refused; }
        *value^=1;
    }
    if(refused!=79 || !experiment_di_burst_sender_write(c,0xcd000000,0x135e00e0) || stmSubmitted!=33 || hw::state.ppcMessage!=0x135e00e0) { return 4; }
    measured[0x804b2a80]=17;
    c.pc=0x80241c20; c.lr=0x80242084;
    uint32_t control=0;
    if(!experiment_di_burst_sender_read(c,0xcd000004,control)||control!=0x30) { return 5; }
    c.pc=0x80241c30; c.lr=0x80242094;
    if(!experiment_di_burst_sender_write(c,0xcd000004,0x31)||stmSubmitted!=34||experimentDiBurstPending[1]!=0x135e00e0) { return 6; }
    c.lr=0x8024204c;
    if(experiment_di_burst_sender_write(c,0xcd000000,0x135e0140)) { return 7; }
    std::cout << "SENDER_COMPONENT_79_MUTANTS_PASS\n";
}
'''.replace('WORDS', ','.join('{%d,%d}' % pair for pair in sorted(memory.items()))).replace('BYTES', ','.join(map(str, packet)))
host = output / 'sender-guard-probe.cpp'
host.write_text(source)
exe = output / 'sender-guard-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'sender-guard-tests.json').write_text(json.dumps({
    'result': 'SENDER_COMPONENT_PASS', 'mutantsRejected': 79,
    'guardSha256': sha(experiment / 'di_burst_sender.h'), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Actual guard compiled against measured words/stub MMIO-BAT-ACK; not live device/IRQ or scheduler evidence.']}, indent=2) + '\n')
print(result.stdout.strip())
