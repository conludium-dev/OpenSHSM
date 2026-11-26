"""Validate full caller coverage and rejection gates without launching the game."""
from pathlib import Path
import argparse
import copy
import json
import tempfile
from stock_psq_float_build import sha, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    build = json.loads(args.candidate.read_text())
    parent_path = Path(build['parentBuildPath'])
    parent = json.loads(parent_path.read_text())
    assert validate(args.candidate, parent_path, parent) == Path(build['executablePath'])
    results = []
    for name in ('missing-caller', 'object-hash', 'source-hash', 'compile-command', 'link-command', 'sites'):
        changed = copy.deepcopy(build)
        if name == 'missing-caller':
            changed['unitChanges'].pop()
        elif name == 'object-hash':
            changed['unitChanges'][0]['objectSha256'] = '0' * 64
        elif name == 'source-hash':
            changed['unitChanges'][0]['sourceSha256'] = '0' * 64
        elif name == 'compile-command':
            changed['unitChanges'][0]['compileCommand'].append('-ffast-math')
        elif name == 'link-command':
            changed['linkCommand'].insert(1, '/unproven/object.o')
        else:
            changed['unitChanges'][0]['sites'].pop()
        with tempfile.NamedTemporaryFile(mode='w', prefix='validation-negative-', suffix='.json',
                dir=args.candidate.parent, delete=False) as stream:
            stream.write(json.dumps(changed))
            path = Path(stream.name)
        try:
            validate(path, parent_path, parent)
        except AssertionError:
            results.append({'case': name, 'result': 'REJECTED', 'path': str(path), 'sha256': sha(path)})
        else:
            raise AssertionError(f'Malformed indexed PSQ derivative accepted: {name}')
    report = {'result': 'PSQ_FLOAT_BUILD_GATES_PASS', 'positivePath': str(args.candidate),
        'positiveSha256': sha(args.candidate), 'negativeCases': results,
        'limits': ['Source/header/provenance/caller/link gates, not live transition or Wii hardware test.']}
    path = args.candidate.parent / 'launcher-verification.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, len(results), flush=True)


if __name__ == '__main__':
    main()
