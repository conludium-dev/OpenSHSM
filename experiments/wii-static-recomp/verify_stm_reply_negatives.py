"""Require native missing-result failure and wrong-result mismatch against the same original oracle."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

parent = Path('experiments/wii-static-recomp/verify_stm_reply_native.py')
spec = importlib.util.spec_from_file_location('stm_reply_comparison', parent)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
root = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
evidence = {}
for name in ('stm-reply-missing', 'stm-reply-wrong'):
    output = root / name
    build = json.loads((output / 'attempt.json').read_text())
    assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_reply_native.py'))
    for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
        assert sha(Path(path)) == digest
    exe = output / 'stm-irq-attempt'
    assert build['executableSha256'] == sha(exe)
    fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
    assert not fresh.stderr
    if name.endswith('missing'):
        assert fresh.returncode == 7 and 'produced=0' in fresh.stdout and 'STM_REPLY_BOUNDARY 0 ' in fresh.stdout
    else:
        assert fresh.returncode == 0
        try:
            module.validate(fresh.stdout)
        except AssertionError:
            pass
        else:
            raise AssertionError('Compiled wrong result accepted against original')
    evidence[name] = {'attemptSha256': sha(output / 'attempt.json'), 'executableSha256': sha(exe),
        'freshReturnCode': fresh.returncode}
output = root / 'stm-reply-native'
(output / 'negative-audit.json').write_text(json.dumps({'result': 'COMPILED_MISSING_AND_WRONG_STM_PRODUCER_NATIVE_CPU_PATH_REFUSED',
    'verifierSha256': sha(Path(__file__)), 'parentVerifierSha256': sha(parent), 'positiveProofSha256': sha(output / 'comparison.json'),
    'mutants': evidence}, indent=2) + '\n')
print('PASS compiled native CPU missing-production refuses; wrong result mismatches original')
