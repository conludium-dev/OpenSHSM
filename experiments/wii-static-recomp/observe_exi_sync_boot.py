"""Read-only EXISync boundary diagnosis on exact verified whole-boot objects."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-stm-async-boot'
output = root / 'mass-exi-sync-observer'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol = Path('work/private-game/disc/DATA/sys/main.dol')
data = dol.read_bytes()
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
sections = zip(struct.unpack_from('>18I', data, 0), struct.unpack_from('>18I', data, 0x48),
    struct.unpack_from('>18I', data, 0x90))
sections = list(sections)
opcodes = {0x8020dce0: 0x8003680c, 0x8020def4: 0x4082fdec, 0x80240440: 0x4bfcd861}
for address, opcode in opcodes.items():
    offsets = [offset + address - start for offset, start, size in sections if start <= address < start + size]
    assert len(offsets) == 1 and struct.unpack_from('>I', data, offsets[0])[0] == opcode
subprocess.run(['python3', str(experiment / 'audit_stm_async_boot.py')], check=True, capture_output=True, text=True)
build = json.loads((base / 'build.json').read_text())
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('boot-wrapper.cpp', 'mass_boot.cpp', 'vi-clock-backend.cpp', 'hw_vi-clock.inc', 'processor_adapter.cpp',
    'ai_mask_backend.cpp', 'dsp_startup_backend.cpp', 'ipc_event_order_probe.cpp', 'ipc_reset_backend.cpp',
    'stm_device.cpp', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
header = output / 'exi_getid_frontend.h'
text = header.read_text()
marker = '        throw std::runtime_error("GetID MMIO profile mapping unverified");'
assert text.count(marker) == 1
observe = r'''        std::cout << "EXI_SYNC_ACCESS" << std::hex << " address=" << address << " instruction=" << instruction
            << " pc=" << context.pc << " lr=" << context.lr << " msr=" << context.msr
            << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot
            << " selected=" << selected << " csr=" << hw::experimentExiMaskState[0]
            << " control=" << hw::experimentExiTransfer.control << " data=" << hw::experimentExiTransfer.data
            << " phase=" << hw::experimentExiTransfer.phase << " command=" << hw::experimentExiTransfer.command
            << " dmaAddress=" << hw::experimentExiTransfer.dmaAddress << " dmaLength=" << hw::experimentExiTransfer.dmaLength
            << " uartCommand=" << hw::experimentExiTransfer.uartCommand << std::dec << '\n';
        std::cout << "EXI_SYNC_ECB" << std::hex;
        for (unsigned offset = 0; offset < 64; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x80491f50 + offset);
        }
        std::cout << std::dec << '\n';
'''
header.write_text(text.replace(marker, observe + marker))
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', output / 'processor_adapter.cpp',
    output / 'ai_mask_backend.cpp', output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp',
    root / 'stm-open-native/ios_kernel.cpp', output / 'stm_device.cpp']
exe = output / 'openshsm-exi-sync-observer'
row = next(row for row in build['records'] if row['file'] == 'output_62.cpp')
observed_object = output / 'output_62.cpp.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-c', row['source'], '-o', str(observed_object)], capture_output=True, text=True, timeout=180)
(output / 'observer-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-include', str(output / 'interrupt_enable_observer.h'),
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), str(observed_object), *[item['object'] for item in build['records'] if item != row], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
    str(root / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
(output / 'observed-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and not result.stderr
assert 'EXI_SYNC_ACCESS' in result.stdout and 'EXI_SYNC_ECB' in result.stdout
assert 'EXI_SYNC_ACCESS address=cd00680c instruction=8020dce0 pc=8020def4 lr=80240444 msr=a032 physical=d00680c wimg=5 slot=1 selected=140 csr=1148 control=34 data=30000100 phase=1 command=1 dmaAddress=80492600 dmaLength=40 uartCommand=30000100' in result.stdout
assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in result.stdout
lines = [line for line in result.stdout.splitlines() if line.startswith(('EXI_SYNC_', 'BOOT_BOUNDARY', 'BOOT_STM_ASYNC dispatched='))]
print('\n'.join(lines))
(output / 'observation.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'),
    'dolSha256': sha(dol), 'originalOpcodes': {hex(address): hex(opcode) for address, opcode in opcodes.items()},
    'records': build['records'], 'observerObject': {'source': row['source'], 'sourceSha256': sha(Path(row['source'])),
        'object': str(observed_object), 'objectSha256': sha(observed_object)},
    'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'sourceHashes': {str(path): sha(path) for path in sources + [output / 'mass_boot.cpp', output / 'ipc_event_order_probe.cpp']},
    'executableSha256': sha(exe), 'logSha256': sha(output / 'observed-boot.log'), 'observations': lines,
    'limits': ['Read-only guard diagnostics; object 62 recompiled from byte-identical source, other objects/admission/backend unchanged; no transfer or hardware read performed by the observer.']}, indent=2) + '\n')
