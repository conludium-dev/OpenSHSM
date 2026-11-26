"""Component-check third sender with measured native ES inputs, not live IRQ proof."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-es-boot'
parent = experiment / 'verify_di_burst_sender_guard.py'
tree = ast.parse(parent.read_text())
node = next(node for node in tree.body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'source' for target in node.targets))
source = ast.literal_eval(node.value.func.value.func.value)
native = json.loads((root / 'mass-di86-idle-observer/observation.json').read_text())
values = {line.split()[0]: line.split()[1:] for line in native['observations']}
memory = {0x800000d4: 0x80492a70, 0x800000e4: 0}
for tag, address in [('DI86_IDLE_WAIT_PACKET', 0x935e0140), ('DI86_IDLE_THREAD', 0x80492920), ('DI86_IDLE_REQUEST_QUEUE', 0x804b2a80)]:
    raw = bytes(map(int, values[tag]))
    for byte in range(0, len(raw), 4):
        memory[address + byte] = int.from_bytes(raw[byte:byte + 4], 'big')
memory[0x804b2a80] = 17
packet = bytes(map(int, values['DI86_IDLE_WAIT_PACKET']))[:32] + bytes(32)
source = source[:source.index('int main()')]
source = source.replace('unsigned stmSubmitted = 32;', 'unsigned stmSubmitted = 34;').replace(
    'std::map<uint32_t,uint32_t> measured', 'struct Memory { unsigned hid0=0xc200; } mem;\nMemory& memory_context(CPUContext&) { return mem; }\nstd::array<uint8_t,8> esPath{47,100,101,118,47,101,115,0};\nstd::map<uint32_t,uint32_t> measured').replace(
    'if(address!=0x135e00e0||size!=64)', 'if(address>=0x528cf0 && address<0x528cf8 && size==1) { return esPath.data()+address-0x528cf0; } if(address!=0x135e0140||size!=64)').replace(
    'ppcMessage=0x135e0080', 'ppcMessage=0x135e00e0').replace(
    '#include "di_burst_sender.h"', '#include "di_burst_sender.h"\n#include "di_burst_es.h"').replace(
    'experimentDiBurstPending[1]=request;', 'experimentDiBurstPending[2]=request;')
source += r'''int main() {
    using namespace nwii::runtime;
    CPUContext c;
    experimentDiBurstPending[0]=0x135e0080;
    experimentDiBurstPending[1]=0x135e00e0;
    unsigned refused=0;
    auto attempt=[&]() {
        try { if(experiment_di_burst_es_write(c,0xcd000000,0x135e0140)) { return false; } }
        catch(const std::runtime_error&) { ++refused; return true; }
        return false;
    };
    for(unsigned i=0;i<64;++i) {
        packet[i]^=1; if(!attempt()) { return 1; } packet[i]^=1;
    }
    for(auto address:std::array<uint32_t,7>{0x800000d4,0x800000e4,0x80492934,0x935e016c,0x935e0170,0x804b2a80,0x804b2a84}) {
        measured[address]^=1; if(!attempt()) { return 2; } measured[address]^=1;
    }
    for(auto& byte:esPath) { byte^=1; if(!attempt()) { return 3; } byte^=1; }
    for(auto* field:std::array<uint32_t*,5>{&hw::state.ppcControl,&hw::state.armMessage,&hw::state.ppcMask,&experimentDiBurstPending[1],&experimentDiBurstPending[2]}) {
        *field^=1; if(!attempt()) { return 4; } *field^=1;
    }
    if(refused!=84||!experiment_di_burst_es_write(c,0xcd000000,0x135e0140)||stmSubmitted!=35) { return 5; }
    measured[0x804b2a80]=18;
    c.pc=0x80241c20; c.lr=0x80242084;
    uint32_t control=0;
    if(!experiment_di_burst_es_read(c,0xcd000004,control)||control!=0x30) { return 6; }
    c.pc=0x80241c30; c.lr=0x80242094;
    if(!experiment_di_burst_es_write(c,0xcd000004,0x31)||stmSubmitted!=36||experimentDiBurstPending[2]!=0x135e0140) { return 7; }
    if(!experiment_di_burst_arm_match(0x135e0140,0x135e0080)||experiment_di_burst_arm_match(0x135e0140,0x135e00e0)) { return 8; }
    std::cout << "ES_SENDER_COMPONENT_84_MUTANTS_PASS\n";
}
'''
source = source.replace('WORDS', ','.join('{%d,%d}' % pair for pair in sorted(memory.items()))).replace('BYTES', ','.join(map(str, packet)))
host = output / 'es-guard-probe.cpp'
host.write_text(source)
exe = output / 'es-guard-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-I', str(experiment), str(host), '-o', str(exe)], capture_output=True, text=True)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'es-guard-tests.json').write_text(json.dumps({'result': 'ES_SENDER_COMPONENT_PASS',
    'mutantsRejected': 84, 'verifierSha256': sha(Path(__file__)), 'guardSha256': sha(experiment / 'di_burst_es.h'),
    'limits': ['Measured native ES words with stub MMIO/BAT/ACK; not actual kernel/cache/IRQ/scheduler behavior.']}, indent=2) + '\n')
print(result.stdout.strip())
