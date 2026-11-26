"""Prove the observer-only relink and restore the existing source instrumentation against current parents."""
from pathlib import Path
import hashlib
import json
import re
import struct
from stock_vi_path_observation import adapt_vi_path

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-ios-o2-phases'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-ios-o2/build.json'
phase_path = root / 'window-live-phases/build.json'
assert sha(parent_path) == build['parentBuildSha256'] and sha(phase_path) == build['phaseBuildSha256']
parent, phase = json.loads(parent_path.read_text()), json.loads(phase_path.read_text())
component_path = root / 'window-ios-o2/component-verification.json'
assert sha(component_path) == build['parentComponentSha256']
assert json.loads(component_path.read_text())['result'] == 'IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS'
expected = Path(phase['mainOriginalPath']).read_text()
for before, after in phase['patches']:
    assert expected.count(before) == 1
    expected = expected.replace(before, after, 1)
main_source = root / 'window-live-phases/main.cpp'
assert '#include "stock_host_phases.h"\n' + expected == main_source.read_text()
vi_original = Path(phase['viOriginalPath'])
vi, stages, calls = adapt_vi_path(vi_original.read_text())
for before, after in phase['viPatches']:
    assert vi.count(before) == 1
    vi = vi.replace(before, after, 1)
assert vi == (root / 'window-live-phases/output_39.cpp').read_text()
markers = lambda text: re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text)
assert markers(vi) == markers(vi_original.read_text())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
words = 0
for address, word in markers(vi):
    address = int(address, 16)
    if 0x802280F0 <= address < 0x80228900:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == int(word, 16)
        words += 1
expected_command = list(parent['linkCommand'])
for name in ('main.cpp.o', 'output_39.cpp.o'):
    old = next(arg for arg in expected_command if Path(arg).name == name)
    expected_command[expected_command.index(old)] = str(root / 'window-live-phases' / name)
expected_command[expected_command.index('-o') + 1] = build['executablePath']
assert expected_command == build['linkCommand']
assert sha(Path(build['executablePath'])) == build['executableSha256']
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'IOS_O2_EXISTING_OBSERVERS_SOURCE_LINK_VERIFIED', 'buildSha256': sha(build_path),
    'phaseBuildSha256': sha(phase_path), 'parentComponentSha256': sha(component_path),
    'verifierSha256': sha(Path(__file__)), 'sdkMarkersChecked': words, 'stages': stages, 'observedCalls': calls,
    'limits': ['Exact reused main/VI instrumentation restores original statements/opcode markers; aliases/duplicates included in SDK marker count.',
        'Relink changes only main/guest39 observer objects from current IOSO2; parent native callback/frame/SDK/SC checks inherited.',
        'No new original guest statements/renderer/clock/sleep/IRQ policy, but observers add timing/MMIO-read overhead.',
        'Not original Wii hardware or complete fresh guest39 execution equivalence; bounded live phase observations pending.']}, indent=2) + '\n')
print('IOS_O2_EXISTING_OBSERVERS_SOURCE_LINK_VERIFIED', words)
