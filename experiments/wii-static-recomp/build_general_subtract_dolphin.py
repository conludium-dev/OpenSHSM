"""Capture the exact original general subtraction, with no replacement of the DUT word."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_fcmp_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp', 'dolphin-general-subtract').replace(
    'run_fcmp_dolphin.ps1', 'run_general_subtract_dolphin.ps1').replace('0x700000', '0x800000').replace(
    'for reg in (0,1):', 'for reg in (0,1,2,3):').replace(
    'dform(50,1,4,(pair // 16) * 8)', 'dform(50,2,4,(pair // 16) * 8)').replace(
    '0x801f5028', '0x800d8dfc').replace('0x801f502c', '0x800d8e00').replace('fc010040', 'ec020028').replace(
    "'initialCr':0xa5a55a5a}", "'initialCr':0xa5a55a5a,'operation':0,'opcode':0xec020028}").replace(
    "'patchOffset':offset + 4", "'patchOffsets':[offset + 4]").replace(
    'original ordered compare', 'original general subtraction')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-general-subtract/generation.json')
report = json.loads(path.read_text())
report['parentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original800D8DFC:EC020028 unchanged, adjacent800D8E00 observer branch only.',
    'Raw IEEE16x16/NI0-NI1/two status controls, not whole constructor or physical Wii proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
