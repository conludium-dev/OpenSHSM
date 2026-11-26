"""Execute the unchanged constructor prefix through its register-variant signed-int subtraction."""
from pathlib import Path
import struct
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_fp_initializer_dolphin.py')
body = parent.read_text().replace('dolphin-fp-initializer','dolphin-fsubs-variant').replace(
    'run_fp_initializer_dolphin.ps1','run_fsubs_variant_dolphin.ps1').replace(
    '0x8000c2f4','0x800a8ed8').replace('for reg in (0,1):','for reg in (0,1,2,3):')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
output = Path('work/private-game/static-recomp/dolphin-fsubs-variant')
path = output / 'fpr-init.dol'
image = bytearray(path.read_bytes())
header = struct.unpack('>64I',image[:256])
section = next(i for i in range(7) if header[18+i] <= 0x800a8f18 < header[18+i]+header[36+i])
offset = header[section] + 0x800a8f18 - header[18+section]
assert image[offset - 4:offset] == bytes.fromhex('ec401828')
image[offset:offset + 4] = bytes.fromhex('4e800020')
path.write_bytes(image)
report_path = output / 'generation.json'
report = json.loads(report_path.read_text())
report['harnessSha256'] = hashlib.sha256(image).hexdigest()
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['patchOffset'] = offset
report['functionBytes'] = 64
report['limits'] = ['Original first16 instructions through fsubs f2,f0,f3 unchanged; adjacent next lfs replaced by observer return.',
    'Prefix leaves stack frame allocated, no enclosing constructor/division/multiplication/physical Wii proof.']
report_path.write_text(json.dumps(report,indent=2) + '\n')
