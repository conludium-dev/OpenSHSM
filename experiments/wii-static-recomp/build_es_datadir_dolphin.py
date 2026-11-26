"""Measure whole original GetDataDir using a title returned by original GetTitleId."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_title_dolphin.py')
body = parent.read_text().replace('dolphin-es-title', 'dolphin-es-datadir').replace(
    'run_es_title_dolphin.ps1', 'run_es_datadir_disc_dolphin.ps1')
for name in ('prep', 'capture'):
    tree = ast.parse(body)
    node = next(node for node in tree.body if isinstance(node, ast.Assign) and
        any(isinstance(target, ast.Name) and target.id == name for target in node.targets))
    value = ast.literal_eval(node.value)
    if name == 'prep':
        value += '''            if index >= 6:
                pointer(code, 11, 0x80500080)
                code.extend([dform(32, 3, 11, 0), dform(32, 4, 11, 4)])
                pointer(code, 5, 0x80500000)
'''
    else:
        value = '''        if index >= 5:
            pointer(code, 11, 0x80500000)
            for offset in range(0, 32, 4):
                code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 608 + offset)])
            if index == 5:
                pointer(code, 12, 0x80500080)
                for offset in (0, 4):
                    code.extend([dform(32, 0, 11, offset), dform(36, 0, 12, offset)])
            for slot, address, size in [(656, 0x8053fee0 if index == 5 else 0x8053ff00, 8),
                (664, 0xc053fee0 if index == 5 else 0xc053ff00, 8),
                (672, 0x8053ffb0 if index == 5 else 0x8053ffd0, 8 if index == 5 else 16),
                (680 if index == 5 else 688, 0xc053ffb0 if index == 5 else 0xc053ffd0, 8 if index == 5 else 16)]:
                pointer(code, 11, address)
                for offset in range(0, size, 4):
                    code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, slot + offset)])
'''
    literal = ast.get_source_segment(body, node.value)
    assert body.count(literal) == 1
    body = body.replace(literal, repr(value))
body = body.replace('0x80249c40 if index >= 5 else', '0x80249ba0 if index >= 6 else 0x80249c40 if index == 5 else')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-datadir/generation.json')
report = json.loads(path.read_text())
report['datadirParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
for case in report['records']:
    if case['index'] >= 6:
        case.update(kind='ESP_GetDataDir', callerOutput=0x80500000, inputTitle=0x8053ff00,
            vector=0x8053ffd0, outputBytes=30)
        case.pop('temporaryOutput', None)
report['limits'] = ['Two prepared original STM send exchanges, whole async registration/FS OPEN/ESP init/GetTitleId then ten WHOLE GetDataDir calls.',
    'Title arguments come from the preceding original GetTitleId response, never supplied constants; output32 is seeded A5, original service may write30.',
    'Prepared thread/stack/heap/vector context; own-disc context is required separately. No file writes, credentials, power/network, callback completion or retail gameplay proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
