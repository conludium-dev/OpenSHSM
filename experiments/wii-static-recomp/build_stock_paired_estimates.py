"""Private estimate-unit derivative of a verified existing PC build; never overwrite it."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile
from stock_paired_estimate_patch import adapt
from stock_paired_units import plans
from concurrent.futures import ThreadPoolExecutor


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    parser.add_argument('--all-units', action='store_true')
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    base = json.loads(args.base.read_text())
    component = json.loads(args.component.read_text())
    assert base['result'] == 'PC_BRANDING_MAIN_ONLY_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert component['result'] == 'PAIRED_ESTIMATE_CPU_COMPONENT_DOL_LOWERING_PASS'
    for path, digest in {**base['dependencies'], **base['retainedLinkInputs'],
            **component['dependencies']}.items():
        assert sha(path) == digest, path
    for key in ('executable', 'source', 'object'):
        assert sha(base[key + 'Path']) == base[key + 'Sha256']
    reference_path = next(Path(path) for path in component['dependencies'] if path.endswith('/reference.json'))
    reference = json.loads(reference_path.read_text())
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    for path, digest in reference['dependencies'].items():
        assert sha(path) == digest, path
    cache = Path(tempfile.mkdtemp(prefix='openshsm-paired-build-', dir='/private/tmp'))
    dol = project / 'work/private-game/disc/DATA/sys/main.dol'
    unit_plans = plans(base, root, dol.read_bytes(), args.all_units)
    dolphin = reference_path.parent / 'dolphin/Source/Core'
    includes = ['-I', str(reference_path.parent / 'shim'), '-I', str(dolphin)]
    def compile_unit(plan):
        source = cache / Path(plan['originalSourcePath']).name
        obj = source.with_name(source.name + '.o')
        source.write_text(plan['patched'])
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *plan['arguments'],
            *includes, '-frounding-math', '-fno-fast-math', '-c', str(source), '-o', str(obj)]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=240)
        (cache / (source.name + '.compile.log')).write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, compiled.stderr[-4000:]
        print('COMPILED', source.name, len(plan['sites']), flush=True)
        return {key: value for key, value in plan.items() if key not in ('patched', 'arguments')} | {
            'sourcePath': str(source), 'sourceSha256': sha(source),
            'objectPath': str(obj), 'objectSha256': sha(obj), 'compileCommand': command}
    with ThreadPoolExecutor(max_workers=2) as pool:
        changes = list(pool.map(compile_unit, unit_plans))
    first = next(change for change in changes if Path(change['sourcePath']).name == 'output_8.cpp')
    source, obj = Path(first['sourcePath']), Path(first['objectPath'])
    command = first['compileCommand']
    sites = [site for change in changes for site in change['sites']]
    numeric_source = dolphin / 'Common/FloatUtils.cpp'
    numeric_obj = cache / 'FloatUtils.cpp.o'
    numeric_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-frounding-math', '-fno-fast-math', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', *includes,
        '-c', str(numeric_source), '-o', str(numeric_obj)]
    numeric = subprocess.run(numeric_command, capture_output=True, text=True, timeout=60)
    (cache / 'numeric-compile.log').write_text(numeric.stdout + numeric.stderr)
    assert numeric.returncode == 0, numeric.stderr
    link = list(base['linkCommand'])
    replacements = {change['originalObjectPath']: change['objectPath'] for change in changes}
    link = [replacements.get(value, value) for value in link]
    link.insert(1, str(numeric_obj))
    exe = cache / 'OpenSHSM-0.0.42'
    link[link.index('-o') + 1] = str(exe)
    linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    (cache / 'link.log').write_text(linked.stdout + linked.stderr)
    assert linked.returncode == 0, linked.stderr[-4000:]
    old_inputs = [value for value in base['linkCommand'] if value.endswith(('.o', '.a'))]
    new_inputs = [value for value in link if value.endswith(('.o', '.a'))]
    assert len(new_inputs) == len(old_inputs) + 1
    assert [value for value in new_inputs if value != str(numeric_obj)] == [
        replacements.get(value, value) for value in old_inputs]
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    dependencies = {str(path): sha(path) for path in [Path(__file__).resolve(), args.base,
        args.component, reference_path, dol, public / 'stock_paired_estimates.h',
        public / 'stock_paired_estimate_patch.py', public / 'stock_paired_units.py']}
    for change in changes:
        dependencies.update(change['dependencies'])
        dependencies[change['originalSourcePath']] = change['originalSourceSha256']
    report = {'result': 'PAIRED_ESTIMATE_UNIT_COMPILED_LINKED_NOT_LIVE_VERIFIED',
        'baseBuildPath': str(args.base.resolve()), 'baseBuildSha256': sha(args.base),
        'componentPath': str(args.component.resolve()), 'componentSha256': sha(args.component),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'sites': sites,
        'allUnits': args.all_units, 'unitChanges': changes,
        'sourcePath': str(source), 'sourceSha256': sha(source),
        'objectPath': str(obj), 'objectSha256': sha(obj),
        'numericSourcePath': str(numeric_source), 'numericSourceSha256': sha(numeric_source),
        'numericObjectPath': str(numeric_obj), 'numericObjectSha256': sha(numeric_obj),
        'compileCommand': command, 'numericCompileCommand': numeric_command, 'linkCommand': link,
        'dependencies': dependencies,
        'retainedLinkInputs': {str(Path(path) if Path(path).is_absolute() else root / 'export/build' / path):
            sha(Path(path) if Path(path).is_absolute() else root / 'export/build' / path)
            for path in old_inputs if path not in replacements},
        'limits': ['Only DOL-verified estimate fatal blocks replaced; all original guards/counts retained.',
            'Pinned GPL-2.0-or-later Dolphin numeric source separately compiled; private derivative, not published.',
            'Enabled FP program exceptions fail closed; original Wii delivery not implemented.',
            'No live post-movie transition/crash-fix acceptance yet; strict play runner registration pending.',
            'No persistence/input/performance or interpreter-fallback instruction fixes.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, len(sites), flush=True)


if __name__ == '__main__':
    main()
