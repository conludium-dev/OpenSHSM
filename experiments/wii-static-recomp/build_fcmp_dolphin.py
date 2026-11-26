"""Observe the actual original ordered compare with raw IEEE pairs/NI/status fixtures."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fcmp')
output.mkdir(exist_ok=True)
source = Path('work/private-game/disc/DATA/sys/main.dol')
original = source.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = list(struct.unpack('>64I',original[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node,ast.FunctionDef):
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(helpers),'exec'),namespace)
dform,spr,pointer,branch,capture = (namespace[name] for name in ('dform','spr','pointer','branch','capture'))
base,result_base,constants_base,stride = 0x80600000,0x700000,0x807f0000,736
values = [0,0x8000000000000000,1,0x8000000000000001,0x000fffffffffffff,0x0010000000000000,
    0x3ff0000000000000,0xbff0000000000000,0x7fefffffffffffff,0xffefffffffffffff,
    0x7ff0000000000000,0xfff0000000000000,0x7ff8000000000001,0xfff8000000000042,
    0x7ff0000000000001,0xfff0000000000042]
constants = b''.join(struct.pack('>Q',value) for value in values) + struct.pack('>Q',0x4008000000000000)
constants += bytes((-len(constants)) % 32)
count = 1024
data,code,records,returns = bytearray(count * stride),[],[],[]
for index in range(count):
    if returns:
        replacement = []
        pointer(replacement,26,base + len(code) * 4)
        code[returns[-1]:returns[-1] + 2] = replacement
    ni,status,pair = index // 512,(index // 256) % 2,index % 256
    a,b = values[pair // 16],values[pair % 16]
    initial = 0x82024000 if status else 0
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I',data,index * stride + 20,index)
    struct.pack_into('>Q',data,index * stride + 48,initial)
    code.extend([dform(14,0,0,0x2030),(31 << 26) | (146 << 1)])
    pointer(code,0,0xc200)
    code.append(spr(0,1008,True))
    pointer(code,0,0xa0000000)
    code.append(spr(0,920,True))
    pointer(code,1,0x80540000)
    pointer(code,29,0xc0000000 + result_base + index * stride)
    code.extend([dform(50,31,29,48),(63 << 26) | (255 << 17) | (31 << 11) | (711 << 1)])
    pointer(code,4,constants_base)
    code.append(dform(50,31,4,128))
    for reg in (0,1):
        code.append((4 << 26) | (reg << 21) | (31 << 16) | (31 << 11) | (528 << 1))
    if ni:
        code.append(branch(base + len(code) * 4,0x80210830,True))
    code.extend([dform(50,1,4,(pair // 16) * 8),dform(50,0,4,(pair % 16) * 8)])
    pointer(code,10,0xa5a55a5a)
    code.append((31 << 26) | (10 << 21) | (255 << 12) | (144 << 1))
    code.extend([(63 << 26) | (30 << 21) | (583 << 1),dform(54,30,29,24)])
    returns.append(len(code))
    pointer(code,26,0)
    code.append(branch(base + len(code) * 4,0x801f5028,True))
    records.append({'index':index,'a':a,'b':b,'ni':ni,'initialFpscr':initial,'initialCr':0xa5a55a5a})
halt = base + len(code) * 4
replacement = []
pointer(replacement,26,halt)
code[returns[-1]:returns[-1] + 2] = replacement
code.append(branch(halt,halt))
collector = base + len(code) * 4
observer = []
capture(observer,result_base,uncached=True)
observer[1:3] = [dform(24,29,12,0),0x60000000]
code.extend(observer)
code.extend([spr(26,9,True),0x4e800420])
while len(code) % 8:
    code.append(0x60000000)
image = bytearray(original)
for text,address,content in [(True,base,struct.pack('>' + 'I' * len(code),*code)),
    (False,0x80000000 + result_base,data),(False,constants_base,constants)]:
    slot = next(i for i in (range(7) if text else range(7,18)) if not header[36 + i])
    header[slot],header[18 + slot],header[36 + slot] = len(image),address,len(content)
    image.extend(content)
section = next(i for i in range(7) if header[18+i] <= 0x801f5028 < header[18+i]+header[36+i])
offset = header[section] + 0x801f5028 - header[18+section]
assert original[offset:offset + 4] == bytes.fromhex('fc010040')
struct.pack_into('>I',image,offset + 4,branch(0x801f502c,collector))
header[56] = base
image[:256] = struct.pack('>64I',*header)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'generatorSha256':sha(Path(__file__)),
    'originalSha256':sha(source),'harnessSha256':hashlib.sha256(image).hexdigest(),
    'helperSha256':sha(helpers),'baseRunnerSha256':sha(experiment / 'run_dolphin_probe.ps1'),
    'wrapperSha256':sha(experiment / 'run_fcmp_dolphin.ps1'),'patchOffset':offset + 4,'records':records,
    'limits':['Actual original801F5028 compare and NI setter unchanged; only adjacent branch observer patched.',
        '16x16 IEEE pairs/NI0-NI1/two status controls/CR and FP lanes; emulator oracle, not physical Wii.']},indent=2) + '\n')
print('Prepared1024 original ordered compare cases, no DUT instruction replacement')
