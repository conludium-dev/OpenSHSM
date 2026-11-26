"""Require the actual OPEN producer and correct result on the combined sender path."""
from pathlib import Path
import hashlib
import json
import subprocess

parent = Path('experiments/wii-static-recomp/verify_stm_send_native.py')
prefix = parent.read_text().split("exe = output / 'stm-send-cycle'", 1)[0]
exec(compile(prefix, str(parent), 'exec'), globals())
results = []
for name, expected_code in (('stm-send-missing', 7), ('stm-send-wrong', 0)):
    directory = root / name
    negative = json.loads((directory / 'attempt.json').read_text())
    assert negative['builderSha256'] == sha(experiment / 'build_stm_send_cycle.py')
    assert negative['baseAttemptSha256'] == build['baseAttemptSha256']
    assert negative['returnCode'] == expected_code and negative['logSha256'] == sha(directory / 'native.log')
    for path, digest in {**negative['sourceHashes'], **negative['headerHashes']}.items():
        assert sha(Path(path)) == digest
    for row in negative['records']:
        assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    exe = directory / 'stm-send-cycle'
    assert sha(exe) == negative['executableSha256']
    fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
    assert fresh.returncode == expected_code and not fresh.stderr
    assert fresh.stdout == (directory / 'native.log').read_text()
    try:
        validate(fresh.stdout)
    except AssertionError:
        pass
    else:
        raise AssertionError('Incorrect combined sender production accepted')
    if name.endswith('missing'):
        assert 'entries=2 produced=0 reason=Interpreter fallback forbidden' in fresh.stdout
        assert 'STM_SEND_CASE ' not in fresh.stdout
    else:
        assert len([line for line in fresh.stdout.splitlines() if line.startswith('STM_SEND_CASE ')]) == 16
        assert '0000000800000042' in fresh.stdout
    results.append({'variant': name, 'attemptSha256': sha(directory / 'attempt.json'), 'oracleComparisonRejected': True})
(output / 'negative-comparison.json').write_text(json.dumps({'result': 'COMBINED_SENDER_MISSING_PRODUCER_AND_WRONG_RESULT_REJECTED',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent), 'results': results,
    'limits': ['Missing producer retains scheduled transport reply, so the guest may wake on invalid old data; this is not an original IOS timeout test.',
        'No produced OPEN means no successful lifecycle accepted; wrong66 return/payload fails the original comparison.']}, indent=2) + '\n')
print('PASS combined sender missing production and wrong result rejected; fresh compiled counterexamples')
