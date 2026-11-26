"""Reuse read harness for the unchanged original DSP mask block."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_dsp_read_dolphin.py'
body = builder.read_text().replace('dsp-read', 'dsp-mask').replace('dsp_read_dolphin', 'dsp_mask_dolphin')
body = body.replace('0x802176f4', '0x802176ec').replace('0xa0a5500a', '0x3ca0cc00')
body = body.replace("'    pointer(code, 5, 0xcc000000)'", "'    pointer(code, 3, 0x04000000)\\n    pointer(code, 4, 0xffffffff ^ ((index & 7) << 24))'")
body = body.replace("{'index': index, 'ni': index // 8}", "{'index': index, 'ni': index // 8, 'softwareMask': 0xffffffff ^ ((index & 7) << 24)}")
insertion = '''replace('store_offset + 4', 'store_offset + 0x3c')
replace('store + 4', 'store + 0x3c')
replace('    returns.append(len(code))', '    code.extend([dform(40, 0, 5, 0x500a), dform(36, 0, 30, 32)])\\n    returns.append(len(code))')
'''
# The original block initializes r5 itself; the pre-observation needs its base.
body = body.replace('    pointer(code, 3, 0x04000000)\\n', '    pointer(code, 5, 0xcc000000)\\n    pointer(code, 3, 0x04000000)\\n')
body = body.replace("start = body.index('observer = base + len(code) * 4')", insertion + "start = body.index('observer = base + len(code) * 4')")
body = body.replace('code.append(dform(36, 5, 30, 24))', 'code.extend([dform(36, 5, 30, 24), dform(40, 0, 4, 0x500a), dform(36, 0, 30, 28)])')
body = body.replace('Generated16 original DSP read cases; unseeded DSP, one adjacent observer patch', 'Generated16 original DSP mask block cases; original read/modify/write unchanged')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-dsp-mask/generation.json')
report = json.loads(path.read_text())
report['readGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original DSP block802176EC..80217724 unchanged, BLR80217728 observer patch only; unseeded DSP and synthetic software masks/MSR/HID0/NI.'
report['limits'] = ['All8 mask combinations on no-pending loader DSP; no general DMA/audio/interrupt delivery or physical Wii.']
path.write_text(json.dumps(report, indent=2) + '\n')
