"""Reject malformed fallback derivative records before any game launch."""
from pathlib import Path
import argparse
import copy
import json
import tempfile
from stock_interpreter_reached_build import sha, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    path = args.build.resolve()
    original = json.loads(path.read_text())
    parent_path = Path(original['parentBuildPath'])
    parent = json.loads(parent_path.read_text())
    validate(path, parent_path, parent)
    component = json.loads((path.parent / 'verification.json').read_text())
    mutations = [('source', lambda row: row.update(sourceSha256='0' * 64)),
        ('object', lambda row: row.update(objectSha256='0' * 64)),
        ('archive', lambda row: row.update(archiveSha256='0' * 64)),
        ('members', lambda row: row['retainedRuntimeMembers'].pop(next(iter(row['retainedRuntimeMembers'])))),
        ('compile', lambda row: row['compileCommand'].insert(1, '-ffast-math')),
        ('link', lambda row: row['linkCommand'].insert(1, '-ffast-math'))]
    cache = Path(tempfile.mkdtemp(prefix='openshsm-reached-negative-', dir='/private/tmp'))
    relocated = copy.deepcopy(original)
    for name in ('interpreter.cpp.o', 'libnwiiruntime.a', 'OpenSHSM-0.0.42'):
        (cache / name).symlink_to(path.parent / name)
    relocated['compileCommand'][-1] = str(cache / 'interpreter.cpp.o')
    for key in ('archivePath', 'executablePath'):
        old_path = relocated[key]
        new_path = str(cache / Path(old_path).name)
        relocated[key] = new_path
        relocated['linkCommand'][relocated['linkCommand'].index(old_path)] = new_path
    control = cache / 'control.json'
    control.write_text(json.dumps(relocated, indent=2) + '\n')
    proof = copy.deepcopy(component)
    proof['buildSha256'] = sha(control)
    (cache / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n')
    validate(control, parent_path, parent)
    rejected = []
    for name, mutate in mutations:
        row = copy.deepcopy(relocated)
        mutate(row)
        target = cache / (name + '.json')
        target.write_text(json.dumps(row, indent=2) + '\n')
        proof = copy.deepcopy(component)
        proof['buildSha256'] = sha(target)
        (cache / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n')
        try:
            validate(target, parent_path, parent)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError('Malformed candidate accepted: ' + name)
    assert len(rejected) == len(mutations)
    report = {'result': 'REACHED_INTERPRETER_BUILD_GATE_PASS', 'buildSha256': sha(path),
        'componentSha256': sha(path.parent / 'verification.json'), 'negativeCasesRejected': rejected,
        'validatorSha256': sha(Path(__file__).with_name('stock_interpreter_reached_build.py')),
        'verifierSha256': sha(Path(__file__)), 'limits': ['No game launch or gameplay acceptance.']}
    output = path.parent / 'launcher-verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(rejected), 'malformed records rejected', output)


if __name__ == '__main__':
    main()
