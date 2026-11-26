"""Recompile all current indexed PSQ callers with verified float-bit conversion."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import shutil
import subprocess
import tempfile
from stock_paired_build_validation import validate as validate_paired
from stock_psq_float_build import sha, unit_plans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    args = parser.parse_args()
    parent = json.loads(args.parent.read_text())
    base_path = Path(parent['baseBuildPath'])
    validate_paired(args.parent, base_path, json.loads(base_path.read_text()))
    component = json.loads(args.component.read_text())
    assert component['result'] == 'INDEXED_PSQ_FLOAT_CONVERSION_COMPONENT_PASS'
    for file, digest in component['dependencies'].items():
        assert sha(file) == digest, file
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    plans = unit_plans(parent, root, dol.read_bytes())
    cache = Path(tempfile.mkdtemp(prefix='openshsm-psq-float-build-', dir='/private/tmp'))
    for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
        shutil.copyfile(public / name, cache / name)
    def compile_unit(plan):
        source = cache / Path(plan['originalSourcePath']).name
        obj = source.with_name(source.name + '.o')
        shutil.copyfile(plan['originalSourcePath'], source)
        command = list(plan['compileCommand'])
        command[command.index(plan['originalSourcePath'])] = str(source)
        command[command.index('-o') + 1] = str(obj)
        command.insert(1, '-H')
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        log = cache / (source.name + '.compile.log')
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-4000:]
        for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
            assert str(cache / name) in result.stderr
        print('COMPILED', source.name, len(plan['sites']), flush=True)
        return plan | {'sourcePath': str(source), 'sourceSha256': sha(source),
            'objectPath': str(obj), 'objectSha256': sha(obj), 'compileCommand': command,
            'compileLogPath': str(log), 'compileLogSha256': sha(log)}
    with ThreadPoolExecutor(max_workers=2) as pool:
        changes = list(pool.map(compile_unit, plans))
    replacements = {change['originalObjectPath']: change['objectPath'] for change in changes}
    link = [replacements.get(value, value) for value in parent['linkCommand']]
    exe = cache / 'OpenSHSM-0.0.42'
    link[link.index('-o') + 1] = str(exe)
    result = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    (cache / 'link.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    retained = {}
    for value in parent['linkCommand']:
        if value.endswith(('.o', '.a')) and value not in replacements:
            path = Path(value) if Path(value).is_absolute() else root / 'export/build' / value
            retained[str(path)] = sha(path)
    report = {'result': 'INDEXED_PSQ_FLOAT_ALL_CALLERS_COMPILED_LINKED_NOT_LIVE_VERIFIED',
        'parentBuildPath': str(args.parent.resolve()), 'parentBuildSha256': sha(args.parent),
        'componentPath': str(args.component.resolve()), 'componentSha256': sha(args.component),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'unitChanges': changes,
        'linkCommand': link, 'retainedLinkInputs': retained,
        'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
            public / 'stock_psq_float_build.py', public / 'stock_psq_indexed.h', public / 'stock_psq_float.h',
            args.parent, args.component, dol]},
        'limits': ['All12 static indexed-PSQ caller units recompiled together,207 sites DOL-verified.',
            'Pinned Dolphin bit conversions for GQR type0; non-float/MMIO/DSI profiles still refused.',
            'Previously verified242 paired estimates preserved; archive/main/other objects unchanged.',
            'No live transition/crash-fix, hardware or permanent-save acceptance yet.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
