"""Independently check DEC replay and counter-read ISA, preserving old fixture proof."""
from pathlib import Path
import ast
import hashlib

parent = Path('experiments/wii-static-recomp/verify_playrecord_events_fixture.py')
body = parent.read_text().replace('dolphin-playrecord-events','dolphin-playrecord-dec-events').replace(
    'build_playrecord_events_dolphin.py','build_playrecord_dec_events_dolphin.py').replace(
    'run_playrecord_events_disc_dolphin.ps1','run_playrecord_dec_events_disc_dolphin.ps1')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.Assign)
    and any(isinstance(target,ast.Name) and target.id == 'expected_sites' for target in node.targets))
sites = ast.literal_eval(node.value) + [(8,0x802106e0,0x7c7603a6),(9,0x802106e4,0x4e800020)]
body = body.replace(ast.get_source_segment(body,node.value),repr(sites)).replace(
    "    start = next(i for i in range(len(span) - 4)",
    "    assert sum(span[i:i + 2] == [0x7c1602a6,0x900b003c] for i in range(len(span) - 1)) == 1\n    start = next(i for i in range(len(span) - 4)")
body = body.replace('seven exact replay sites','nine exact replay sites/DEC slot60').replace('1792 stride','2304 stride')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
