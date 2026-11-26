"""Compare existing IOSKernel and scoped existing packet parser against original STM replies."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'stm-open-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for options in ([], ['--startup-control']):
    subprocess.run(['python3', str(experiment / 'verify_stm_open_dolphin.py'), *options], check=True)
vendor = runtime / 'src/hle/ios_kernel.cpp'
body = vendor.read_text()
transforms = [('    m_fds.push_back({nullptr, 0, true});', ''),
    ('for (size_t i = 1;', 'for (size_t i = 0;'),
    ('fd > 0 && fd < m_fds.size()', 'fd < m_fds.size()'),
    ('    return IPC_ENOENT;', '    return -6;')]
fixed = body
for before, after in transforms:
    assert fixed.count(before) == (2 if before.startswith('fd >') else 1)
    fixed = fixed.replace(before, after)
kernel = output / 'ios_kernel.cpp'
kernel.write_text(fixed)
header = experiment / 'ipc_open_packet.h'
adapter = header.read_text()
marker = '    if (!length || physical < 0x00400000u'
assert adapter.count(marker) == 1
extra = '''    if (length == 64 && physical >= 0x135e0020 && physical <= 0x135e03e0 && !(physical & 31)) {
        auto first = context.mmu.get_ptr(physical);
        auto last = context.mmu.get_ptr(physical + length - 1);
        if (!first || last != first + length - 1) { throw std::runtime_error("MEM2 IPC packet backing unavailable"); }
        return first;
    }
'''
adapter = adapter.replace(marker, extra + marker, 1)
adapter = adapter.replace('command != 1 || mode != 1', 'command != 1 || (mode != 0 && mode != 1)')
marker = '    const auto result = IOSKernel::get().open(context, path, mode);'
assert adapter.count(marker) == 1
adapter = adapter.replace(marker, '''    if ((path != "/dev/stm/immediate" && path != "/dev/openshsm_missing") ||
        (path == "/dev/stm/immediate" && mode != 0)) {
        throw std::runtime_error("STM OPEN path/mode outside measured profile");
    }
''' + marker)
(output / 'ipc_open_packet.h').write_text(adapter)
probe = experiment / 'stm_open_host.cpp'
host = output / 'stm_open_host.cpp'
host.write_bytes(probe.read_bytes())
sources = [host, runtime / 'src/hle/devices/stm_device.cpp']
results = {}
for mode, kernel_source in (('vendor', vendor), ('measured', kernel)):
    exe = output / ('stm-open-' + mode)
    result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O2', '-include', 'bit',
        '-I', str(output), '-I', str(runtime / 'include'), *map(str, sources), str(kernel_source), '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    (output / (mode + '-build.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    for target in ('kernel', 'packet'):
        result = subprocess.run([str(exe), target], capture_output=True, text=True, timeout=20)
        (output / (mode + '-' + target + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and not result.stderr
        lines = result.stdout.splitlines()
        if target == 'kernel':
            rows = [list(map(int, line.split()[1:])) for line in lines if line.startswith('STM_KERNEL ')]
            expected = [[index, index + (mode == 'vendor') if index < 8 else (-106 if mode == 'vendor' else -6)] for index in range(16)]
            assert rows == expected
        else:
            rows = [list(map(int, line.split()[1:])) for line in lines if line.startswith('STM_PACKET ')]
            assert len(rows) == 16 and 'STM_PACKET_GUARDS 8' in lines
            if mode == 'measured':
                for directory in ('dolphin-stm-open', 'dolphin-stm-open-startup'):
                    oracle = json.loads((root / directory / 'comparison.json').read_text())
                    for row, original in zip(rows, oracle['observations']):
                        assert row[:2] == [original['index'], original['replyResult']]
                        assert bytes(row[2:]).hex() == original['replyPacketHex']
        results[mode + '-' + target] = sha(output / (mode + '-' + target + '.log'))
assert vendor.read_text() == body
(output / 'comparison.json').write_text(json.dumps({'result': 'EXISTING_KERNEL_FDZERO_STM16_PACKET64_MATCH_TWO_ORIGINAL_PROFILES',
    'verifierSha256': sha(Path(__file__)), 'hostSha256': sha(probe), 'vendorSha256': sha(vendor),
    'kernelSha256': sha(kernel), 'adapterParentSha256': sha(header), 'adapterSha256': sha(output / 'ipc_open_packet.h'),
    'deviceSha256': sha(sources[1]), 'transforms': transforms, 'logs': results,
    'originalProofs': {name: sha(root / name / 'comparison.json') for name in ('dolphin-stm-open', 'dolphin-stm-open-startup')},
    'guards': 8, 'vendorCounterexamples': 16,
    'limits': ['Private specialization of existing kernel vector/parser, actual vendor STM device; no second registry.',
        'OPEN results/full64bytes only; native transport/IRQ timing/current startup not yet integrated.',
        'FD0 close/get-entry checks adapted consistently but original close/reuse/device-IOCTL behavior unverified.']}, indent=2) + '\n')
print('PASS existing kernel/parser STM8-missing8/full64bytes vs both original profiles;8guards;16vendorcounterexamples')
