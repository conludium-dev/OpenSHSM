"""Scoped indexed-float derivative, including every caller to prevent inline ODR mixing."""
from pathlib import Path
import hashlib
import json
import re
import struct


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unit_plans(parent, root, dol):
    layout = struct.unpack('>64I', dol[:256])
    changed = {item['objectPath']: item for item in parent['unitChanges']}
    plans = []
    for value in parent['linkCommand']:
        obj = Path(value)
        if obj.suffix != '.o' or not obj.name.startswith('output_'):
            continue
        source = obj.with_suffix('')
        text = source.read_text()
        if 'shsm_psq_indexed(ctx,' not in text:
            continue
        if value in changed:
            record = changed[value]
            assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
            command = list(record['compileCommand'])
        else:
            record_path = source.with_suffix('.cpp.record.json')
            record = json.loads(record_path.read_text())
            assert sha(source) == record['sourceSha256']
            assert sha(obj) == record['objectSha256'] == parent['retainedLinkInputs'][value]
            for path, digest in record['dependencies'].items():
                assert sha(path) == digest
            command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
                '-c', str(source), '-o', str(obj)]
        sites = []
        for match in re.finditer(r'shsm_psq_indexed\(ctx, 0x([0-9A-Fa-f]{8})u?, 0x([0-9A-Fa-f]{8})u?\)', text):
            opcode, address = int(match[1], 16), int(match[2], 16)
            index = next(i for i in range(18) if layout[18 + i] <= address
                and address + 4 <= layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[index] + address - layout[18 + index])[0] == opcode
            sites.append({'address': address, 'opcode': opcode})
        assert len(sites) == text.count('shsm_psq_indexed(ctx,')
        plans.append({'originalSourcePath': str(source), 'originalSourceSha256': sha(source),
            'originalObjectPath': value, 'originalObjectSha256': sha(obj),
            'compileCommand': command, 'sites': sites})
    assert len(plans) == 12 and sum(len(plan['sites']) for plan in plans) == 207
    return plans


def validate(path, parent_path, parent):
    path = path.resolve()
    assert path.parent.parent == Path('/private/tmp') and path.parent.name.startswith('openshsm-psq-float-build-')
    build = json.loads(path.read_text())
    assert build['result'] == 'INDEXED_PSQ_FLOAT_ALL_CALLERS_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert Path(build['parentBuildPath']).resolve() == parent_path.resolve()
    assert sha(parent_path) == build['parentBuildSha256']
    for file, digest in build['dependencies'].items():
        assert sha(file) == digest, file
    component_path = Path(build['componentPath'])
    assert sha(component_path) == build['componentSha256']
    component = json.loads(component_path.read_text())
    assert component['result'] == 'INDEXED_PSQ_FLOAT_CONVERSION_COMPONENT_PASS'
    for file, digest in component['dependencies'].items():
        assert sha(file) == digest, file
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    plans = unit_plans(parent, root, dol.read_bytes())
    assert len(plans) == len(build['unitChanges'])
    for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
        assert sha(path.parent / name) == sha(public / name)
    for plan, change in zip(plans, build['unitChanges']):
        for key in ('originalSourcePath', 'originalSourceSha256', 'originalObjectPath', 'originalObjectSha256', 'sites'):
            assert change[key] == plan[key]
        source, obj = Path(change['sourcePath']), Path(change['objectPath'])
        assert source.parent == obj.parent == path.parent
        assert source.read_bytes() == Path(plan['originalSourcePath']).read_bytes()
        assert sha(source) == change['sourceSha256'] and sha(obj) == change['objectSha256']
        command = list(plan['compileCommand'])
        command[command.index(plan['originalSourcePath'])] = str(source)
        command[command.index('-o') + 1] = str(obj)
        command.insert(1, '-H')
        assert command == change['compileCommand']
        trace = Path(change['compileLogPath'])
        assert sha(trace) == change['compileLogSha256']
        for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
            assert str(path.parent / name) in trace.read_text()
    replacements = {change['originalObjectPath']: change['objectPath'] for change in build['unitChanges']}
    link = [replacements.get(value, value) for value in parent['linkCommand']]
    link[link.index('-o') + 1] = build['executablePath']
    assert link == build['linkCommand']
    expected = {}
    for value in parent['linkCommand']:
        if value.endswith(('.o', '.a')) and value not in replacements:
            file = Path(value) if Path(value).is_absolute() else root / 'export/build' / value
            expected[str(file)] = sha(file)
    assert expected == build['retainedLinkInputs']
    exe = Path(build['executablePath'])
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    assert sha(exe) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    return exe
