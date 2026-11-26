"""Call the complete unchanged original initializer with signed-int/NI/status fixtures."""
from pathlib import Path
import ast
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fp-initializer')
output.mkdir(exist_ok=True)
source = Path('work/private-game/disc/DATA/sys/main.dol')
original = source.read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
layout = list(struct.unpack('>64I',original[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node,ast.FunctionDef):
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(helpers),'exec'),namespace)
dform,spr,pointer,branch,capture = (namespace[name] for name in ('dform','spr','pointer','branch','capture'))
base,result_base,stride = 0x80600000,0x680000,736
values = [0,1,-1,528,2,-2,127,-127,32767,-32768,65535,-65536,8388607,-8388607,
    8388608,-8388608,16777215,-16777215,16777216,-16777216,16777217,-16777217,
    16777218,-16777218,16777219,-16777219,2147483647,-2147483648,2147483646,-2147483647,
    123456789,-123456789]
data,code,records,returns = bytearray(128 * stride),[],[],[]
for index in range(128):
    if returns:
        replacement = []
        pointer(replacement,31,base + len(code) * 4)
        code[returns[-1]:returns[-1] + 2] = replacement
    ni,status,value = index // 64,(index // 32) % 2,values[index % 32]
    initial = 0x82024000 if status else 0
    data[index * stride:index * stride + 16] = b'OSHSM_PPC_DLP001'
    struct.pack_into('>I',data,index * stride + 20,index)
    struct.pack_into('>Q',data,index * stride + 48,initial)
    struct.pack_into('>Q',data,index * stride + 56,0x4008000000000000)
    code.extend([dform(14,0,0,0x2030),(31 << 26) | (146 << 1)])
    pointer(code,0,0xc200)
    code.append(spr(0,1008,True))
    pointer(code,0,0xa0000000)
    code.append(spr(0,920,True))
    pointer(code,1,0x80540000)
    pointer(code,2,0x805335e0)
    pointer(code,13,0x8052e720)
    pointer(code,29,0xc0000000 + result_base + index * stride)
    code.extend([dform(50,31,29,48),(63 << 26) | (255 << 17) | (31 << 11) | (711 << 1),dform(50,31,29,56)])
    for reg in (0,1):
        code.append((4 << 26) | (reg << 21) | (31 << 16) | (31 << 11) | (528 << 1))
    if ni:
        code.append(branch(base + len(code) * 4,0x80210830,True))
    pointer(code,12,0x8052861c)
    pointer(code,0,value & 0xffffffff)
    code.append(dform(36,0,12,0))
    pointer(code,12,0x80529158)
    pointer(code,0,0xa5a5a5a5)
    code.extend([dform(36,0,12,0),dform(36,0,12,4)])
    returns.append(len(code))
    pointer(code,31,0)
    code.append(branch(base + len(code) * 4,0x8000c2f4,True))
    observer = []
    capture(observer,result_base,uncached=True)
    observer[1:3] = [dform(24,29,12,0),0x60000000]
    marker = observer[-3:]
    code.extend(observer[:-3])
    pointer(code,11,0x80529158)
    code.extend([dform(32,0,11,0),dform(36,0,12,24),dform(32,0,11,4),dform(36,0,12,28)])
    code.extend(marker)
    code.extend([spr(31,9,True),0x4e800420])
    records.append({'index':index,'ni':ni,'initialFpscr':initial,'value':value})
halt = base + len(code) * 4
replacement = []
pointer(replacement,31,halt)
code[returns[-1]:returns[-1] + 2] = replacement
code.append(branch(halt,halt))
while len(code) % 8:
    code.append(0x60000000)
image = bytearray(original)
for text,address,content in [(True,base,struct.pack('>' + 'I' * len(code),*code)),(False,0x80000000 + result_base,data)]:
    slot = next(i for i in (range(7) if text else range(7,18)) if not layout[36 + i])
    layout[slot],layout[18 + slot],layout[36 + slot] = len(image),address,len(content)
    image.extend(content)
layout[56] = base
image[:256] = struct.pack('>64I',*layout)
(output / 'fpr-init.dol').write_bytes(image)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'generation.json').write_text(json.dumps({'generatorSha256':sha(Path(__file__)),
    'helperSha256':sha(helpers),'originalSha256':sha(source),'harnessSha256':hashlib.sha256(image).hexdigest(),
    'baseRunnerSha256':sha(experiment / 'run_dolphin_probe.ps1'),
    'wrapperSha256':sha(experiment / 'run_fp_initializer_dolphin.ps1'),'records':records,
    'function':0x8000c2f4,'functionBytes':56,
    'limits':['Whole original14-instruction function and NI setter unchanged; no original instruction patches.',
        'Synthetic signed integer/SDA/FP/stack/status fixtures; outputs captured through CPU cached loads.',
        'No pending IOS/whole retail startup or physical Wii proof.']},indent=2) + '\n')
print('Prepared128 whole original initializer calls/NI0-NI1/status controls/all original instruction bytes unchanged')
