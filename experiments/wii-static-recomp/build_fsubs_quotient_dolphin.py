"""Retain the original twenty-six-instruction prefix, including integer quotient and stores."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fsubs_variant_dolphin.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-quotient').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_quotient_dolphin.ps1').replace(
    '0x800a8ed8', '0x8017ace8').replace('0x800a8f18', '0x8017ad50').replace(
    'ec401828', 'ec001028').replace("report['functionBytes'] = 64", "report['functionBytes'] = 104").replace(
    'first16', 'first26').replace('fsubs f2,f0,f3', 'fsubs f0,f0,f2').replace('adjacent next lfs', 'adjacent next stfs')
marker = "exec(compile(body,str(parent),'exec'),{'__file__':__file__})"
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace('0x80529158', '0x8052a350')\n" + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
