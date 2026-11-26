"""Check source22-instruction prefix and unchanged helper for the aliasing register variant."""
from pathlib import Path
import struct

original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I',original[:256])
address = 0x8052c3d8
section = next(i for i in range(18) if header[18+i] <= address < header[18+i]+header[36+i])
offset = header[section] + address - header[18+section]
constant = struct.unpack('>Q',struct.pack('>d',struct.unpack_from('>f',original,offset)[0]))[0]
parent = Path('experiments/wii-static-recomp/verify_fsubs_variant.py')
body = parent.read_text().replace('dolphin-fsubs-variant','dolphin-fsubs-second').replace(
    'build_fsubs_variant_dolphin.py','build_fsubs_second_dolphin.py').replace(
    'run_fsubs_variant_dolphin.ps1','run_fsubs_second_dolphin.ps1').replace('ec401828','ec421828')
body = body.replace('0x4330000000000000 | ((value & 0xffffffff) ^ 0x80000000)','constant').replace(
    '0x4330000080000000,0x4008000000000000,0x4008000000000000','0x4330000080000000,constant,0x4008000000000000')
marker = "runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')"
assert body.count(marker) == 1
body = body.replace(marker,marker + '''
probe = output / 'second-probe.cpp'
source = (experiment / 'fsubs_variant_probe.cpp').read_text().replace('0xec401828','0xec421828').replace(
    'context.fpr[0] = std::bit_cast<double>(0x4330000000000000ull | (uint32_t(value) ^ 0x80000000u));',
    'context.fpr[2] = std::bit_cast<double>(0x4330000000000000ull | (uint32_t(value) ^ 0x80000000u));\\n        context.fpr[0] = std::bit_cast<double>(' + str(constant) + 'ull);\\n        context.ps1[0] = context.fpr[0];')
probe.write_text(source)
''')
body = body.replace("str(experiment / 'fsubs_variant_probe.cpp')","str(probe)").replace(
    "sha(experiment / 'fsubs_variant_probe.cpp')","sha(probe)").replace('PREFIX16','PREFIX22').replace(
    'prefix16','prefix22').replace('first16','first22').replace('F2-F0-F3','F2-F2-F3').replace('leftF0','leftF2')
exec(compile(body,str(parent),'exec'),{'__file__':__file__,'constant':constant})
