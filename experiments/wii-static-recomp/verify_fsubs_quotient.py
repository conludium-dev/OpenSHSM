"""Compare the original quotient, previous stores and exact conversion with existing numeric helpers."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fsubs_variant.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-quotient').replace(
    'build_fsubs_variant_dolphin.py', 'build_fsubs_quotient_dolphin.py').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_quotient_dolphin.ps1').replace(
    'fsubs_variant_probe.cpp', 'fsubs_quotient_probe.cpp').replace('ec401828', 'ec001028').replace(
    'PREFIX16', 'PREFIX26').replace('prefix16', 'prefix26').replace('first16', 'first26').replace(
    'F2-F0-F3', 'F0-F0-F2').replace('destinationF2/leftF0/rightF3', 'destinationF0/leftF0/rightF2')
start, end = body.index("    value = record['value']"), body.index('    return actual')
body = body[:start] + '''    source_value = record['value']
    value = (abs(source_value) // 6) * (-1 if source_value < 0 else 1)
    single = struct.unpack('>I',struct.pack('>f',float(value)))[0]
    double = struct.unpack('>Q',struct.pack('>d',struct.unpack('>f',struct.pack('>I',single))[0]))[0]
    source_single = struct.unpack('>I',struct.pack('>f',float(source_value)))[0]
    source_double = struct.unpack('>Q',struct.pack('>d',struct.unpack('>f',struct.pack('>I',source_single))[0]))[0]
    fpscr = ((record['initialFpscr'] | record['ni'] * 4) & ~0x1f000) | ((2 if not value else 8 if value < 0 else 4) << 12)
    actual = [struct.unpack_from('>Q',row,position)[0] for position in (192,448,704,200,208,456,464)]
    actual[2] &= 0xffffffff
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I',row,16) == (0xc001cafe,record['index'])
    assert actual == [double,double,fpscr,source_double,0x4330000080000000,source_double,0x4008000000000000]
    assert struct.unpack_from('>I',row,36)[0] == 0x8053ffe0
    assert struct.unpack_from('>I',row,32)[0] == ((value & 0xffffffff) ^ 0x80000000)
    assert struct.unpack_from('>2I',row,24) == (source_single,source_value & 0xffffffff)
''' + body[end:]
body = body.replace('(208,464,708,192,216,448,472,36)', '(192,448,708,200,208,456,464,36,32,24,28)').replace(
    'mutants == 1024', 'mutants == 1408').replace("'mutants':1024", "'mutants':1408").replace('1024 mutations', '1408 mutations')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
