"""Reuse the original NI/frsp measurement with additional sticky-status input fixtures."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_ni_dolphin.py'
body = builder.read_text().replace('dolphin-ni-probe', 'dolphin-frsp-flags')
body = body.replace("constants = b''.join(struct.pack('>Q', value) for value in values) + bytes(8)",
                    "seeds = [0, 0x80000000, 0x02000000, 0x00060000, 0x0001f000, 0x01000000, 0x81000000, 0xa2000000]\nconstants = b''.join(struct.pack('>Q', value) for value in values + seeds)")
body = body.replace('bytearray(32 * stride)', 'bytearray(256 * stride)').replace('for index in range(32):', 'for index in range(256):')
body = body.replace('ni, value_index = index // 16, index % 16', 'ni, value_index, seed_index = (index // 16) % 2, index % 16, index // 32')
body = body.replace('constant_base + 16 * 8', 'constant_base + (16 + seed_index) * 8')
body = body.replace("'inputBits': values[value_index]", "'inputBits': values[value_index], 'initialFpscr': seeds[seed_index]")
body = body.replace("'run_ni_dolphin.ps1'", "'run_frsp_flags_dolphin.ps1'")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-frsp-flags/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
