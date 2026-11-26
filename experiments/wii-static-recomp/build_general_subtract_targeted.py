"""Extend the separate original oracle with startup, cancellation and rounding boundaries."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_general_subtract_dolphin.py')
body = parent.read_text().replace('dolphin-general-subtract', 'dolphin-general-subtract-targeted').replace(
    'run_general_subtract_dolphin.ps1', 'run_general_subtract_targeted.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, '''body = body.replace('constants = b', 'values += [0x3fcf07c200000000,0xbfcf07c200000000,0x3fefffffffffffff,0x3ff0000000000001,0x3ff0000010000000,0x3ff000000fffffff,0x3ff0000010000001,0xbff0000010000000,0x3810000000000000,0x380fffffffffffff,0x36a0000000000000,0x47efffffe0000000,0x3e70000000000000,0xbe70000000000000,0x37f0000000000000,0x3ff0000020000000]\\nconstants = b')
body = body.replace('count = 1024', 'count = 4096').replace('index // 512,(index // 256) % 2,index % 256', 'index // 2048,(index // 1024) % 2,index % 1024')
body = body.replace('pair // 16', 'pair // 32').replace('pair % 16', 'pair % 32').replace('dform(50,31,4,128)', 'dform(50,31,4,256)')
body = body.replace('Prepared1024', 'Prepared4096')
''' + marker)
body = body.replace('Raw IEEE16x16/NI0-NI1/two status controls', 'IEEE32x32/actual startup operand/cancellation/rounding/NI0-NI1/two status controls')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
