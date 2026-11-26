"""Capture the actual original fdivs/fmuls instructions with raw IEEE operands."""
from pathlib import Path
import struct
import json
import hashlib

parent = Path('experiments/wii-static-recomp/build_fcmp_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp','dolphin-single-arithmetic').replace(
    'run_fcmp_dolphin.ps1','run_single_arithmetic_dolphin.ps1').replace(
    '0x700000','0x800000').replace('count = 1024','count = 2048')
body = body.replace('ni,status,pair = index // 512,(index // 256) % 2,index % 256',
    'operation,local = index // 1024,index % 1024\n    ni,status,pair = local // 512,(local // 256) % 2,local % 256')
body = body.replace('for reg in (0,1):','for reg in (0,1,2,3):')
body = body.replace('dform(50,1,4,(pair // 16) * 8),dform(50,0,4,(pair % 16) * 8)',
    'dform(50,2 if operation == 0 else 0,4,(pair // 16) * 8),dform(50,1,4,(pair % 16) * 8)')
body = body.replace('0x801f5028,True','0x800a8f20 if operation == 0 else 0x800a8f30,True')
body = body.replace("'initialCr':0xa5a55a5a}","'initialCr':0xa5a55a5a,'operation':operation,'opcode':0xec220824 if operation == 0 else 0xec000072}")
body = body.replace('0x801f5028','0x800a8f20').replace('0x801f502c','0x800a8f24').replace('fc010040','ec220824')
marker = 'header[56] = base'
assert body.count(marker) == 1
body = body.replace(marker,'''second_offset = header[section] + 0x800a8f30 - header[18+section]
assert original[second_offset:second_offset + 4] == bytes.fromhex('ec000072')
struct.pack_into('>I',image,second_offset + 4,branch(0x800a8f34,collector))
''' + marker)
body = body.replace("'patchOffset':offset + 4","'patchOffsets':[offset + 4,second_offset + 4]")
body = body.replace('Prepared1024 original ordered compare cases, no DUT instruction replacement',
    'Prepared2048 original fdivs/fmuls cases, no DUT instruction replacement')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/dolphin-single-arithmetic/generation.json')
report = json.loads(path.read_text())
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original fdivs800A8F20:EC220824 and fmuls800A8F30:EC000072 unchanged; adjacent exits patched.',
    '16x16 IEEE pairs/NI0-NI1/two status controls, not whole initializer or physical Wii proof.']
path.write_text(json.dumps(report,indent=2) + '\n')
