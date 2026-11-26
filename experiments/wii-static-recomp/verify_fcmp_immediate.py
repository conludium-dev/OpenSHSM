"""Compare immediate FPSCR with the shared observer and retain original discrepancy proof."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fcmp_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp','dolphin-fcmp-immediate').replace(
    'build_fcmp_dolphin.py','build_fcmp_immediate_dolphin.py').replace(
    'run_fcmp_dolphin.ps1','run_fcmp_immediate_dolphin.ps1')
marker = "    assert struct.unpack_from('>Q',row,704)[0] & 0xffffffff == expected(record)[1]"
assert body.count(marker) == 1
body = body.replace(marker,marker + "\n    assert struct.unpack_from('>Q',row,712)[0] & 0xffffffff == expected(record)[1]")
body = body.replace('(28,160,708,192,200,448,456):','(28,160,708,716,192,200,448,456):').replace('7168','8192')
body = body.replace('FPCC_OR_DISCREPANCY_UNRESOLVED','IMMEDIATE_OR_SOURCE_MASK_BUG_CONFIRMED')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
