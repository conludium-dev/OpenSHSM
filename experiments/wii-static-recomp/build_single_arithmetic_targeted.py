"""Extend original arithmetic evidence with actual boot operands and rounding boundaries."""
from pathlib import Path
import struct

def bits(value):
    return struct.unpack('>Q',struct.pack('>d',value))[0]

raw = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I',raw[:256])
address = 0x8052c3d8
section = next(i for i in range(18) if header[18+i] <= address < header[18+i]+header[36+i])
offset = header[section] + address - header[18+section]
scale = struct.unpack_from('>f',raw,offset)[0]
quotient = struct.unpack('>f',struct.pack('>f',528 / 100))[0]
divisions = [(bits(a),bits(b)) for a,b in [(528,100),(1,3),(2,3),(16777217,100),(2147483647,100),
    (-2147483648,100),(100,528),(-528,100),(528,-100),(3.141592653589793,2.718281828459045),
    (1.0000000000000002,3),(1,1.0000000000000002),(0.1,0.2),(0.2,0.1),(123456789,100),(-123456789,100)]]
divisions += [(0x3ff0000010000000 + delta,bits(1)) for delta in (-1,0,1)]
divisions += [(0x3810000000000000,bits(2)),(0x380fffffffffffff,bits(1)),(0x36a0000000000000,bits(2)),
    (0x369fffffffffffff,bits(1)),(0x0010000000000000,bits(1.0000000000000002)),
    (0x0010000000000000,bits(1.5)),(0x000fffffffffffff,bits(2)),(0x3ff0000000000000,0x7fefffffffffffff),
    (0x7fefffffffffffff,0x3ff0000000000001),(0xbff0000010000000,bits(1)),(0xbff0000010000001,bits(1)),
    (0x47efffffe0000000,bits(1)),(0x47effffff0000000,bits(1))]
multiplications = [(bits(a),bits(b)) for a,b in [(scale,quotient),(528,0.01),(0.1,0.2),(3.141592653589793,2.718281828459045),
    (1,1),(16777217,1),(123456789,0.01),(-123456789,0.01),(0.2,528),(528,-0.2),
    (1.0000000000000002,3),(3,1.0000000000000002),(2147483647,0.01),(-2147483648,0.01),(1,0.1),(0.1,1)]]
multiplications += [(bits(1),0x3ff0000008000000 + delta) for delta in (-1,0,1)]
multiplications += [(0x3ff0000010000000 + delta,bits(1)) for delta in (-1,0,1)]
multiplications += [(0x3810000000000000,bits(0.5)),(0x380fffffffffffff,bits(1)),(0x36a0000000000000,bits(0.5)),
    (0x0010000000000000,bits(1.5)),(0x000fffffffffffff,bits(1.0000000000000002)),
    (0x7fefffffffffffff,bits(0.5)),(0x47efffffe0000000,bits(1)),(0x47effffff0000000,bits(1)),
    (0xbff0000010000000,bits(1)),(bits(1),0x8000000000000001)]
assert len(divisions) == len(multiplications) == 32
parent = Path('experiments/wii-static-recomp/build_single_arithmetic_dolphin.py')
outer = parent.read_text().replace('dolphin-single-arithmetic','dolphin-single-arithmetic-targeted').replace(
    'run_single_arithmetic_dolphin.ps1','run_single_arithmetic_targeted.ps1')
marker = "exec(compile(body,str(parent),'exec'),{'__file__':__file__})"
assert outer.count(marker) == 1
changes = '''body = body.replace('count = 2048','count = 256').replace(
    'operation,local = index // 1024,index % 1024','operation,local = index // 128,index % 128').replace(
    'ni,status,pair = local // 512,(local // 256) % 2,local % 256','ni,status,pair = local // 64,(local // 32) % 2,local % 32')
body = body.replace('a,b = values[pair // 16],values[pair % 16]','a,b = targeted[operation][pair]')
body = body.replace("constants = b''.join(struct.pack('>Q',value) for value in values) + struct.pack('>Q',0x4008000000000000)",
    "targeted = " + repr([divisions,multiplications]) + "\\nconstants = struct.pack('>Q',0x4008000000000000) + b''.join(struct.pack('>2Q',*pair) for group in targeted for pair in group)")
body = body.replace('dform(50,31,4,128)','dform(50,31,4,0)').replace(
    'dform(50,2 if operation == 0 else 0,4,(pair // 16) * 8),dform(50,1,4,(pair % 16) * 8)',
    'dform(50,2 if operation == 0 else 0,4,8 + operation * 512 + pair * 16),dform(50,1,4,16 + operation * 512 + pair * 16)')
'''
outer = outer.replace(marker,changes + marker)
exec(compile(outer,str(parent),'exec'),{**globals(),'__file__':__file__})
