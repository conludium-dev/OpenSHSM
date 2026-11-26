"""Retain the original aliasing bias subtraction and its twelve-instruction prefix."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fsubs_variant_dolphin.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-alias').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_alias_dolphin.ps1').replace(
    '0x800a8ed8', '0x800d8dc4').replace('0x800a8f18', '0x800d8df4').replace(
    'ec401828', 'ec211828').replace("report['functionBytes'] = 64", "report['functionBytes'] = 48").replace(
    'first16', 'first12').replace('fsubs f2,f0,f3', 'fsubs f1,f1,f3').replace(
    'adjacent next lfs', 'adjacent next fdivs')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
