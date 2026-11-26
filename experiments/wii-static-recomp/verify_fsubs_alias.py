"""Compare exact aliasing operands, paired result and status with the original prefix."""
from pathlib import Path
import struct

original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])


def single_constant(address):
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return struct.unpack('>Q', struct.pack('>d', struct.unpack_from('>f', original, offset)[0]))[0]


constant0 = single_constant(0x8052ca28)
constant2 = single_constant(0x8052c9f8)
parent = Path('experiments/wii-static-recomp/verify_fsubs_variant.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-alias').replace(
    'build_fsubs_variant_dolphin.py', 'build_fsubs_alias_dolphin.py').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_alias_dolphin.ps1').replace(
    'fsubs_variant_probe.cpp', 'fsubs_alias_probe.cpp').replace('ec401828', 'ec211828').replace(
    'PREFIX16', 'PREFIX12').replace('prefix16', 'prefix12').replace('first16', 'first12').replace(
    'F2-F0-F3', 'F1-F1-F3').replace('destinationF2/leftF0', 'destinationF1/leftF1')
start = body.index('    actual = [struct.unpack_from')
end = body.index('    return actual', start)
body = body[:start] + '''    actual = [struct.unpack_from('>Q',row,position)[0] for position in (200,456,704,192,208,216,472)]
    actual[2] &= 0xffffffff
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert actual == [double,double,fpscr,constant0,constant2,0x4330000080000000,0x4008000000000000]
    assert struct.unpack_from('>I',row,36)[0] == 0x8053fff0
''' + body[end:]
body = body.replace("{record['initialFpscr'] | record['ni'] * 4}\\n", "{record['initialFpscr'] | record['ni'] * 4} {constant0} {constant2}\\n").replace(
    '(208,464,708,192,216,448,472,36)', '(200,456,708,192,208,216,472,36)')
exec(compile(body, str(parent), 'exec'), {**globals(), '__file__': __file__})
