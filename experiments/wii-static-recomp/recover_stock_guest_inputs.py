"""Regenerate missing paired/PSQ link inputs from retained source recipes on the SSD."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import shutil
import subprocess
from stock_paired_units import plans, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    ancestor_path = root / 'window-dispatch-select/build.json'
    ancestor = json.loads(ancestor_path.read_text())
    current = json.loads(args.current.read_text())
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    missing = {Path(value).name: value for value in current['linkCommand']
        if '/openshsm-paired-build-' in value or '/openshsm-psq-float-build-' in value}
    values = [value for value in ancestor['linkCommand'] if Path(value).name in missing]
    assert len(values) == 32
    for value in values:
        assert sha(value) == ancestor['retainedInputs'][value], value
    legacy_root = Path(values[0]).parents[1]
    dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    paired = plans({'linkCommand': values, 'retainedLinkInputs': ancestor['retainedInputs']},
        legacy_root, dol.read_bytes(), True)
    assert sum(len(plan['sites']) for plan in paired) == 242
    paired_by_object = {plan['originalObjectPath']: plan for plan in paired}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=args.resume)
    previous = {}
    if args.resume:
        previous = {row['objectPath']: row for row in
            json.loads((output / 'recovery.json').read_text())['inputs']}
    for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
        shutil.copy2(public / name, output / name)
    includes = ['-I', str(output), '-I', str(args.reference.parent / 'shim'),
        '-I', str(args.reference.parent / 'dolphin/Source/Core')]
    jobs = []
    for value in values:
        original = Path(value).with_suffix('')
        if value in paired_by_object:
            plan = paired_by_object[value]
            text, flags = plan['patched'], plan['arguments']
        else:
            record = json.loads(original.with_suffix('.cpp.record.json').read_text())
            assert sha(original) == record['sourceSha256']
            assert sha(value) == record['objectSha256']
            text, flags = original.read_text(), record['arguments']
        source = output / original.name
        source.write_text(text)
        obj = output / Path(value).name
        numeric_flags = ['-frounding-math', '-fno-fast-math'] if value in paired_by_object else []
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *includes, *flags,
            *numeric_flags, '-H', '-c', str(source), '-o', str(obj)]
        jobs.append({'sourcePath': str(source), 'sourceSha256': sha(source),
            'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
            'replaces': missing[obj.name], 'objectPath': str(obj), 'compileCommand': command,
            'psqSites': text.count('shsm_psq_indexed(ctx,')})
    assert sum(job['psqSites'] for job in jobs) == 207
    def compile_job(job):
        old = previous.get(job['objectPath'])
        if old and old['compileCommand'] == job['compileCommand'] and \
                old['sourceSha256'] == job['sourceSha256'] and \
                sha(job['objectPath']) == old['objectSha256']:
            job['objectSha256'] = old['objectSha256']
            return job
        result = subprocess.run(job['compileCommand'], capture_output=True, text=True, timeout=300)
        log = output / (Path(job['sourcePath']).name + '.compile.log')
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        if job['psqSites']:
            for name in ('stock_psq_indexed.h', 'stock_psq_float.h'):
                assert str(output / name) in result.stderr
        job['objectSha256'] = sha(job['objectPath'])
        print('RECOVERED', Path(job['objectPath']).name, flush=True)
        return job
    with ThreadPoolExecutor(max_workers=2) as pool:
        recovered = list(pool.map(compile_job, jobs))
    report = {'result': 'REGENERATED_PAIRED_PSQ_GUEST_INPUTS_NOT_LINKED', 'inputs': recovered,
        'pairedSites': 242, 'psqSites': 207,
        'dependencies': {str(p.resolve()): sha(p) for p in [Path(__file__), ancestor_path,
            args.current, args.reference, dol, public / 'stock_paired_units.py',
            public / 'stock_paired_estimate_patch.py', public / 'stock_paired_estimates.h',
            public / 'stock_psq_indexed.h', public / 'stock_psq_float.h']},
        'limits': ['Regenerated from retained original units using existing patches; no old temporary object hash claim.',
            'Missing numeric/main/dispatch/context/movie inputs and full link/runtime validation remain.']}
    (output / 'recovery.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(recovered), flush=True)


if __name__ == '__main__':
    main()
