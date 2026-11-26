"""Record the owned abort as an indexed-float guard failure without guessing its call site."""
from pathlib import Path
import argparse
import hashlib
import json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    assert artifacts.parent == Path('/private/tmp') and artifacts.name.startswith('openshsm-pc-play-')
    path = artifacts / 'result.json'
    run = json.loads(path.read_text())
    assert run['result'] == 'USER_PLAY_EXITED' and run['exitCode'] == -6 and not run['deadlineEnabled']
    build_path = Path(run['pairedBuildPath'])
    assert sha(build_path) == run['pairedBuildSha256']
    build = json.loads(build_path.read_text())
    exe = Path(build['executablePath'])
    assert sha(exe) == run['executableSha256'] == build['executableSha256']
    tail = artifacts / 'runtime-tail.log'
    text = tail.read_text()
    message = 'Unverified indexed PSQ float conversion profile'
    assert 'terminating due to uncaught exception' in text and message in text
    assert message.encode() in exe.read_bytes()
    assert 'UNIMPLEMENTED Opcode 4' not in text
    report = {'result': 'INDEXED_PSQ_FLOAT_PROFILE_GUARD_ABORT_IDENTIFIED',
        'exitCode': -6, 'exceptionMessage': message,
        'elapsedSeconds': run['endedUnix'] - run['startedUnix'],
        'dependencies': {str(file): sha(file) for file in
            (Path(__file__).resolve(), path, build_path, exe, tail)},
        'limits': ['Exact indexed instruction address and input values were not captured; do not infer them from stale PC.',
            'This is a runtime unsupported-conversion guard, not the previous estimate exit1 or a timer.',
            'No post-movie transition or permanent-save acceptance from this abort.']}
    output = artifacts / 'psq-exit-audit.json'
    assert not output.exists()
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, flush=True)


if __name__ == '__main__':
    main()
