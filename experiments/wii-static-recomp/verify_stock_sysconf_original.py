"""Execute original Wii parser, entry decoder, byte getter and aspect wrapper without service hooks."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import sys
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config(value):
    result = bytearray(0x4000)
    result[:6] = b'SCv0\x00\x01'
    result[6:10] = struct.pack('>HH', 10, 18)
    result[10:18] = bytes([0x65]) + b'IPL.AR' + bytes([value])
    result[-4:] = b'SCed'
    return result


def main():
    assert platform.machine() == 'x86_64', 'Use installed Unicorn under Rosetta'
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    sys.path.insert(0, str(project / '_scratch/tmp/wii-static-recomp-tools/python-x64'))
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    from unicorn import ppc_const as ppc
    dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    cases = []
    for value in (0, 1, 2, 255):
        cases.append((f'byte-{value}', config(value), 0, int(value == 1)))
    for name, offset, byte in [('header', 3, ord('1')), ('footer', 0x3fff, 0),
            ('first-offset', 7, 11), ('end-offset', 9, 19), ('count', 5, 255)]:
        data = config(1)
        data[offset] = byte
        cases.append((name, data, 2, None))
    data = config(1)
    data[10] = 0x85
    data[9] = 19
    cases.append(('wrong-type-short', data, 0, 0))
    data = config(1)
    data[15:17] = b'XY'
    cases.append(('unknown-key', data, 0, 0))
    legacy = bytearray([0xff] * 0x4000)
    legacy[:8] = b'SCv15\x01\x00\x01'
    legacy[8:22] = b'\x02\x06IPL.AR\x00\x04NTSC'
    cases.append(('current-legacy', legacy, 2, None))
    uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
    uc.mem_map(0x80000000, 24 * 1024 * 1024)
    for i in range(18):
        if layout[36 + i]:
            uc.mem_write(layout[18 + i], dol[layout[i]:layout[i] + layout[36 + i]])
    buffer = 0x804b31a0
    sentinel = 0x80008000
    rows = []
    def call(address, args=()):
        uc.reg_write(ppc.UC_PPC_REG_1, 0x80010000)
        uc.reg_write(ppc.UC_PPC_REG_13, 0x8052e720)
        uc.reg_write(ppc.UC_PPC_REG_LR, sentinel)
        for index, value in enumerate(args, start=3):
            uc.reg_write(getattr(ppc, f'UC_PPC_REG_{index}'), value)
        uc.emu_start(address, sentinel, count=100000)
        assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel, hex(uc.reg_read(ppc.UC_PPC_REG_PC))
        assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80010000
        return uc.reg_read(ppc.UC_PPC_REG_3)
    for name, data, expected_parse, expected_aspect in cases:
        uc.mem_write(buffer, bytes(data))
        uc.mem_write(0x8052e720 - 14100, bytes(16))
        parsed = call(0x80247ac0, (buffer, 0x4000))
        assert parsed == expected_parse, (name, parsed, expected_parse)
        aspect = call(0x80248de0) if parsed == 0 else None
        assert aspect == expected_aspect, (name, aspect, expected_aspect)
        rows.append({'name': name, 'parserReturn': parsed, 'aspectReturn': aspect,
            'inputSha256': hashlib.sha256(data).hexdigest()})
    cache = Path(tempfile.mkdtemp(prefix='openshsm-sysconf-original-', dir='/private/tmp'))
    report = {'result': 'ORIGINAL_WII_SYSCONF_PARSER_ASPECT_CHAIN_PASS', 'cases': rows,
        'parserAddress': '80247AC0', 'entryDecoderAddress': '80247D10',
        'getterAddress': '802484C0', 'wrapperAddress': '80248DE0', 'suppliedServiceHooks': 0,
        'dependencies': {str(path): sha(path) for path in [Path(__file__), dol_path]},
        'limits': ['Software750CL executes unmodified original parser/dependencies/getter; not physical Wii/IOS timing.',
            'Synthetic one-entry console config; other settings follow original missing-key defaults.',
            'No rebuilt runtime FS, native chain, actual camera projection or live widescreen proof yet.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(rows), 'cases', path, flush=True)


if __name__ == '__main__':
    main()
