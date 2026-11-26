"""Verify main-only relink, exact source restoration and unchanged DOL-backed SDK observer."""
from pathlib import Path
import hashlib
import json
import re
import struct
from stock_vi_path_observation import adapt_vi_path

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-current-vi-timer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-dec-ee-gate/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
parent_component_path = parent_path.parent / 'component-verification.json'
assert sha(parent_component_path) == build['parentComponentSha256']
assert json.loads(parent_component_path.read_text())['result'] == 'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
before, after = build['patch']
assert Path(build['mainOriginalPath']).read_text().replace(before, after, 1) == Path(build['mainSourcePath']).read_text()
expected = list(parent['linkCommand'])
old = next(arg for arg in expected if Path(arg).name == 'main.cpp.o')
expected[expected.index(old)] = build['mainObjectPath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
phase_path = root / 'window-live-phases/build.json'
assert sha(phase_path) == build['phaseBuildSha256']
phase = json.loads(phase_path.read_text())
vi_original = Path(phase['viOriginalPath'])
assert sha(vi_original) == phase['viOriginalSha256']
vi, stages, calls = adapt_vi_path(vi_original.read_text())
for old, new in phase['viPatches']:
    assert vi.count(old) == 1
    vi = vi.replace(old, new, 1)
vi_source = root / 'window-live-phases/output_39.cpp'
assert vi == vi_source.read_text()
vi_obj = vi_source.with_suffix('.cpp.o')
assert str(vi_obj) in build['linkCommand'] and sha(vi_obj) == phase['viObjectSha256']
markers = lambda text: re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text)
assert markers(vi) == markers(vi_original.read_text())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
count = 0
for address, word in markers(vi):
    address = int(address, 16)
    if 0x802280F0 <= address < 0x80228900:
        section = next(i for i in range(18) if layout[18+i] <= address < layout[18+i] + layout[36+i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18+section])[0] == int(word, 16)
        count += 1
assert sha(Path(build['executablePath'])) == build['executableSha256']
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED',
    'buildSha256': sha(build_path), 'parentComponentSha256': sha(parent_component_path),
    'verifierSha256': sha(Path(__file__)), 'sdkMarkersChecked': count,
    'limits': ['Exact reused timer-only main/current original matched; all other linked objects/archive retained.',
        'DOL-backed SDK observer markers unchanged; count includes duplicate/alias markers, not unique instructions.',
        'Parent native DEC9/callback4/SDK7/SC3/late18 gates inherited because CPU/runtime/guest objects unchanged.',
        'Changed native GUI-to-VI publication policy requires fresh live timing/visual/audio/profile acceptance; not physical Wii proof or promotion.']}, indent=2) + '\n')
print('CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED', count)
