"""Verify original aspect-byte policy and locate its existing Wii consumers; no runtime mutation."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-build', type=Path, required=True)
    args = parser.parse_args()
    assert platform.machine() == 'x86_64', 'Use installed Unicorn under Rosetta'
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    sys.path.insert(0, str(project / '_scratch/tmp/wii-static-recomp-tools/python-x64'))
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn import ppc_const as ppc
    root = project / 'work/private-game/static-recomp/stock-baseline'
    dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])

    def data(address, size):
        index = next(i for i in range(18) if layout[18 + i] <= address
            and address + size <= layout[18 + i] + layout[36 + i])
        offset = layout[index] + address - layout[18 + index]
        return dol[offset:offset + size]

    assert data(0x80528bd4, 7) == b'IPL.AR\0'
    assert struct.unpack('>II', data(0x80441378, 8)) == (0x80528bd4, 1)
    source = root / 'window-fp-guard/output_41.cpp'
    text = source.read_text()
    start = text.index('void func_80248DE0(CPUContext& ctx) {')
    end = text.index('\nvoid func_', start + 1)
    wrapper = text[start:end]
    words = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', wrapper)
    assert len(words) == 21
    for address, word in words:
        assert struct.unpack('>I', data(int(address, 16), 4))[0] == int(word, 16)
    assert 'ctx.gpr[4] = 1;' in wrapper
    assert 'func_802484C0(ctx)' in wrapper
    getter_start = text.index('void func_802484C0(CPUContext& ctx) {')
    getter_end = text.index('\nvoid func_', getter_start + 1)
    getter = text[getter_start:getter_end]
    assert 'ctx.gpr[0] < 96' in getter and 'ctx.gpr[0] == 96' in getter
    getter_words = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', getter)
    for address, word in getter_words:
        assert struct.unpack('>I', data(int(address, 16), 4))[0] == int(word, 16)
    uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
    uc.mem_map(0x80000000, 0x400000)
    uc.mem_write(0x80248de0, data(0x80248de0, 84))
    sentinel = 0x80008000
    output = []
    supplied = {'value': 0, 'success': 0}

    def lookup(machine, address, size, user):
        if address == 0x802484c0:
            assert machine.reg_read(ppc.UC_PPC_REG_4) == 1
            target = machine.reg_read(ppc.UC_PPC_REG_3)
            machine.mem_write(target, bytes([supplied['value']]))
            machine.reg_write(ppc.UC_PPC_REG_3, supplied['success'])
            machine.reg_write(ppc.UC_PPC_REG_PC, machine.reg_read(ppc.UC_PPC_REG_LR))

    uc.hook_add(UC_HOOK_CODE, lookup)
    for success in (0, 1):
        for value in range(256):
            supplied.update(value=value, success=success)
            sp = 0x80010000
            uc.reg_write(ppc.UC_PPC_REG_1, sp)
            uc.reg_write(ppc.UC_PPC_REG_LR, sentinel)
            uc.emu_start(0x80248de0, sentinel, count=100)
            result = uc.reg_read(ppc.UC_PPC_REG_3)
            assert result == (1 if success and value == 1 else 0)
            assert uc.reg_read(ppc.UC_PPC_REG_1) == sp
            assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel
            output.append({'lookupSuccess': success, 'byte': value, 'return': result})
    consumers = []
    for unit in (19, 30):
        path = root / f'window-fp-guard/output_{unit}.cpp'
        matches = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})\n'
            r'    ctx.lr = 0x[0-9A-F]+; // save return address\n'
            r'    ctx.pc = 0x80248DE0; func_80248DE0\(ctx\);', path.read_text())
        assert len(matches) == 1
        address, word = matches[0]
        assert struct.unpack('>I', data(int(address, 16), 4))[0] == int(word, 16)
        consumers.append({'address': address, 'opcode': word, 'sourcePath': str(path), 'sourceSha256': sha(path)})
    fs = root / 'window-fs-rename/fs_device.cpp'
    fs_record_path = fs.parent / 'build.json'
    fs_record = json.loads(fs_record_path.read_text())
    assert sha(fs) == fs_record['sourceSha256']
    fs_obj = fs.with_suffix('.cpp.o')
    assert sha(fs_obj) == fs_record['objectSha256']
    runtime = json.loads(args.runtime_build.read_text())
    archive = Path(runtime['archivePath'])
    assert sha(archive) == runtime['archiveSha256']
    member = subprocess.check_output(['/usr/bin/arch', '-arm64', '/usr/bin/ar', '-p', str(archive), 'fs_device.cpp.o'])
    assert hashlib.sha256(member).hexdigest() == sha(fs_obj)
    body = fs.read_text()
    assert 'sc[3]=\'1\'; sc[4]=\'5\';' in body
    assert 'uint8_t val[] = { 0, 4, \'N\',\'T\',\'S\',\'C\' };' in body
    cache = Path(tempfile.mkdtemp(prefix='openshsm-wii-aspect-', dir='/private/tmp'))
    report = {'result': 'ORIGINAL_WII_ASPECT_BYTE_POLICY_512_CASES_PASS',
        'wrapperAddress': '80248DE0', 'wrapperDOLWords': len(words),
        'byteGetterAddress': '802484C0', 'byteGetterDOLWords': len(getter_words),
        'settingKey': 'IPL.AR', 'settingId': 1, 'consumers': consumers, 'cases': output,
        'dependencies': {str(path): sha(path) for path in [Path(__file__), dol_path, source, fs,
            fs_obj, fs_record_path, args.runtime_build, archive]},
        'originalBehavior': 'The DOL wrapper returns1 only for a successful byte lookup whose value is1; otherwise0.',
        'inferredBehavior': 'Wrapper is SCGetAspectRatio: same original IPL.AR id1 table and two game consumers.',
        'pcAdaptationFinding': 'Existing synthetic SYSCONF header/value do not constitute a proven valid aspect-byte configuration.',
        'limits': ['Software750CL runs original wrapper only; byte lookup is explicitly supplied, not original parser execution.',
            'Getter type96 guard verified statically, not executed in this test.',
            'No original SC reload/config parser/actual runtime getter result/projection or live16:9 acceptance.',
            'No changes to current game process, original Wii copy, save/config or framing.']}
    path = cache / 'evidence.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
