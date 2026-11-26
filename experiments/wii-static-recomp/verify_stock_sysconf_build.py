"""Positive build validation and altered-metadata contract checks; no game launch."""
from pathlib import Path
import argparse
import copy
import json
from stock_sysconf_build import sha, validate, validate_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    path = args.build.resolve()
    build = json.loads(path.read_text())
    parent_path = Path(build['parentBuildPath'])
    parent = json.loads(parent_path.read_text())
    validate(path, parent_path, parent)
    mutations = [('source-hash', lambda row: row.update(sourceSha256='0' * 64)),
        ('object-hash', lambda row: row.update(objectSha256='0' * 64)),
        ('runtime-members', lambda row: row['retainedRuntimeMembers'].pop(next(iter(row['retainedRuntimeMembers'])))),
        ('compile-command', lambda row: row['compileCommand'].insert(1, '-ffast-math')),
        ('native-config', lambda row: row['nativeProbe'].update(preparedSysconfSha256='0' * 64)),
        ('link-command', lambda row: row['linkCommand'].insert(1, '-ffast-math'))]
    rejected = []
    for name, mutate in mutations:
        record = copy.deepcopy(build)
        mutate(record)
        try:
            validate_record(path, parent_path, parent, record)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError('Invalid metadata accepted: ' + name)
    report = {'result': 'SYSCONF_BUILD_NATIVE_ORIGINAL_PROOF_GATE_PASS', 'buildSha256': sha(path),
        'negativeMetadataCasesRejected': rejected,
        'validatorSha256': sha(Path(__file__).with_name('stock_sysconf_build.py')),
        'verifierSha256': sha(Path(__file__)),
        'limits': ['Altered in-memory metadata contracts, not malformed file paths or live game acceptance.']}
    output = path.parent / 'launcher-verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(rejected), 'altered metadata fixtures rejected', output)


if __name__ == '__main__':
    main()
