"""Verify the scoped paired-unit derivative before the existing play runner launches it."""
from pathlib import Path
import hashlib
import json
from stock_paired_estimate_patch import adapt
from stock_paired_units import plans


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, base_path, base):
    path = path.resolve()
    assert path.parent.parent == Path('/private/tmp') and path.parent.name.startswith('openshsm-paired-build-')
    build = json.loads(path.read_text())
    assert build['result'] == 'PAIRED_ESTIMATE_UNIT_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert Path(build['baseBuildPath']).resolve() == base_path.resolve()
    assert sha(base_path) == build['baseBuildSha256']
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    component_path = Path(build['componentPath'])
    assert sha(component_path) == build['componentSha256']
    component = json.loads(component_path.read_text())
    assert component['result'] == 'PAIRED_ESTIMATE_CPU_COMPONENT_DOL_LOWERING_PASS'
    for file, digest in component['dependencies'].items():
        assert sha(file) == digest, file
    reference_path = next(Path(file) for file in component['dependencies'] if file.endswith('/reference.json'))
    reference = json.loads(reference_path.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for file, digest in reference['dependencies'].items():
        assert sha(file) == digest, file
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    public = Path(__file__).resolve().parent
    current_root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    roots = {Path(value).parent.parent for value in base['linkCommand']
        if Path(value).parent.name == 'window-input-sdk'}
    assert len(roots) == 1
    root = roots.pop()
    assert root.resolve() == current_root.resolve()
    dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    unit_plans = plans(base, root, dol.read_bytes(), build.get('allUnits', False))
    changes = build['unitChanges']
    assert len(changes) == len(unit_plans)
    dolphin = reference_path.parent / 'dolphin/Source/Core'
    includes = ['-I', str(reference_path.parent / 'shim'), '-I', str(dolphin)]
    for plan, change in zip(unit_plans, changes):
        metadata = {key: value for key, value in plan.items() if key not in ('patched', 'arguments', 'dependencies')}
        assert metadata == {key: change[key] for key in metadata}
        resolved_plan = {str(Path(file).resolve()): digest for file, digest in plan['dependencies'].items()}
        resolved_change = {str(Path(file).resolve()): digest for file, digest in change['dependencies'].items()}
        assert len(resolved_plan) == len(plan['dependencies'])
        assert len(resolved_change) == len(change['dependencies'])
        assert resolved_plan == resolved_change
        assert Path(change['sourcePath']).read_text() == plan['patched']
        for key in ('source', 'object'):
            file = Path(change[key + 'Path'])
            assert file.parent == path.parent and sha(file) == change[key + 'Sha256']
        expected_compile = ['/Library/Developer/CommandLineTools/usr/bin/c++', *plan['arguments'],
            *includes, '-frounding-math', '-fno-fast-math', '-c', change['sourcePath'], '-o', change['objectPath']]
        assert change['compileCommand'] == expected_compile
    sites = [site for change in changes for site in change['sites']]
    assert sites == build['sites']
    assert all(site in sites for site in component['sites'])
    for key in ('source', 'object', 'numericObject', 'executable'):
        file = Path(build[key + 'Path'])
        assert file.parent == path.parent and sha(file) == build[key + 'Sha256']
    assert Path(build['numericSourcePath']) == dolphin / 'Common/FloatUtils.cpp'
    assert sha(build['numericSourcePath']) == build['numericSourceSha256']
    first = next(change for change in changes if Path(change['sourcePath']).name == 'output_8.cpp')
    assert build['compileCommand'] == first['compileCommand']
    expected_numeric = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-frounding-math', '-fno-fast-math', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', *includes,
        '-c', build['numericSourcePath'], '-o', build['numericObjectPath']]
    assert build['numericCompileCommand'] == expected_numeric
    link = list(base['linkCommand'])
    replacements = {change['originalObjectPath']: change['objectPath'] for change in changes}
    link = [replacements.get(value, value) for value in link]
    link.insert(1, build['numericObjectPath'])
    link[link.index('-o') + 1] = build['executablePath']
    assert build['linkCommand'] == link
    retained = dict(base['retainedLinkInputs'])
    for old_object in replacements:
        retained.pop(old_object)
    retained[base['objectPath']] = base['objectSha256']
    assert build['retainedLinkInputs'] == retained
    exe = Path(build['executablePath'])
    assert exe.name == 'OpenSHSM-0.0.42' and b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    return exe
