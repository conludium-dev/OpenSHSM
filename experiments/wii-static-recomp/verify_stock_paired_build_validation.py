"""Positive and malformed-derivative launcher gates without launching a game."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import tempfile
from stock_paired_build_validation import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    base = json.loads(args.base.read_text())
    candidate = json.loads(args.candidate.read_text())
    assert validate(args.candidate, args.base, base) == Path(candidate['executablePath'])
    cases = []
    for name in ('missing-unit', 'source-hash', 'object-hash', 'numeric-command', 'link-command', 'sites'):
        changed = copy.deepcopy(candidate)
        if name == 'missing-unit':
            changed['unitChanges'].pop()
        elif name == 'source-hash':
            changed['unitChanges'][0]['sourceSha256'] = '0' * 64
        elif name == 'object-hash':
            changed['unitChanges'][0]['objectSha256'] = '0' * 64
        elif name == 'numeric-command':
            changed['numericCompileCommand'].append('-ffast-math')
        elif name == 'link-command':
            changed['linkCommand'].insert(1, '/unproven/object.o')
        else:
            changed['sites'].pop()
        with tempfile.NamedTemporaryFile(mode='w', prefix='validation-negative-', suffix='.json',
                dir=args.candidate.parent, delete=False) as stream:
            stream.write(json.dumps(changed))
            path = Path(stream.name)
        try:
            validate(path, args.base, base)
        except AssertionError:
            cases.append({'case': name, 'result': 'REJECTED', 'path': str(path),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        else:
            raise AssertionError(f'Malformed build accepted: {name}')
    report = {'result': 'PAIRED_BUILD_LAUNCH_GATES_PASS', 'positive': str(args.candidate),
        'positiveSha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(), 'negativeCases': cases,
        'limits': ['Metadata/source/recipe gates only; no game input, launch, transition or performance test.']}
    output = args.candidate.parent / 'launcher-verification.json'
    assert not output.exists()
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, len(cases), flush=True)


if __name__ == '__main__':
    main()
