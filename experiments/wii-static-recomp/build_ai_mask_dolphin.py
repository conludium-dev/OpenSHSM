"""Measure unchanged original Wii AI mask read/modify/write block."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_dsp_read_dolphin.py'
body = builder.read_text().replace('dsp-read', 'ai-mask').replace('dsp_read_dolphin', 'ai_mask_dolphin')
body = body.replace('0x802176f4', '0x8021772c').replace('0xa0a5500a', '0x54800211').replace('0xcc00500a', '0xcd006c00')
body = body.replace("'    pointer(code, 5, 0xcc000000)'", "'    pointer(code, 5, 0xcd000000)\\n    pointer(code, 3, 0x00800000)\\n    pointer(code, 4, 0xffffffff ^ ((index & 1) << 23))'")
body = body.replace("{'index': index, 'ni': index // 8}", "{'index': index, 'ni': index // 8, 'softwareMask': 0xffffffff ^ ((index & 1) << 23)}")
insertion = '''replace('store_offset + 4', 'store_offset + 0x28')
replace('store + 4', 'store + 0x28')
replace('    returns.append(len(code))', '    code.extend([dform(32, 0, 5, 0x6c00), dform(36, 0, 30, 32)])\\n    returns.append(len(code))')
'''
body = body.replace("start = body.index('observer = base + len(code) * 4')", insertion + "start = body.index('observer = base + len(code) * 4')")
body = body.replace('code.append(dform(36, 5, 30, 24))', 'code.extend([dform(36, 5, 30, 24), dform(32, 0, 4, 0x6c00), dform(36, 0, 30, 28)])\npointer(code, 4, 0xcc000000)')
body = body.replace('Generated16 original DSP read cases; unseeded DSP, one adjacent observer patch', 'Generated16 original Wii AI mask block cases; original read/modify/write unchanged')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-ai-mask/generation.json')
report = json.loads(path.read_text())
report['readGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original AI block8021772C..80217750 unchanged, BLR80217754 observer patch; unseeded Wii AI/CD006C00, synthetic masks/MSR/HID0/NI.'
report['limits'] = ['Quiescent mask block only; no streaming/sample-rate/timer/active AI interrupts or physical Wii behavior.']
path.write_text(json.dumps(report, indent=2) + '\n')
