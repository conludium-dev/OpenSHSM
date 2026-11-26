"""Execute all five original instructions with single-bit-pattern denominator fixtures."""
from pathlib import Path
import struct

parent = Path('experiments/wii-static-recomp/build_fp_initializer_dolphin.py')
body = parent.read_text().replace('dolphin-fp-initializer', 'dolphin-divide-initializer').replace(
    'run_fp_initializer_dolphin.ps1', 'run_divide_initializer_dolphin.ps1').replace(
    '0x8000c2f4', '0x8013b0c0').replace('0x8052861c', '0x80527ec0').replace(
    '0x80529158', '0x80529f38').replace("'functionBytes':56", "'functionBytes':20").replace(
    '14-instruction', '5-instruction').replace('signed integer', 'single raw-bit denominator')
start, end = body.index('values = ['), body.index('data,code,records')
body = body[:start] + '''section = next(i for i in range(18) if layout[18+i] <= 0x80527ec0 < layout[18+i]+layout[36+i])
offset = layout[section] + 0x80527ec0 - layout[18+section]
stock = struct.unpack_from('>I',original,offset)[0]
values = [stock,0,0x80000000,0x3f800000,0xbf800000,0x42400000,0x41f00000,0x44040000,
    1,0x80000001,0x007fffff,0x00800000,0x00800001,0x7f7fffff,0xff7fffff,0x7f800000,
    0xff800000,0x7fc00001,0xffc00042,0x7f800001,0xff800042,0x3f7fffff,0x3f800001,0x3f800002,
    0x3f000000,0x3eaaaaab,0x3dcccccd,0x3faaaaab,0x3f555555,0x3f000001,0x3effffff,0x80000100]
assert len(values) == 32
''' + body[end:]
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
