"""Isolated clock regression after the opt-in audio-startup FP profile extension."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parents = []
for name in ('build_ai_clock_native.py', 'verify_ai_clock_native.py'):
    parent = experiment / name
    body = parent.read_text().replace('ai-clock-native', 'audio-clock-regression')
    exec(compile(body, str(parent), 'exec'), {'__file__': str(parent)})
    parents.append({'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()})
output = Path('work/private-game/static-recomp/audio-clock-regression')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'regressions.json').write_text(json.dumps({'result': 'AUDIO_FP_OPT_IN_DEFAULT_CLOCK16_STALLED8_GUARDS_PASS',
    'runnerSha256': sha(Path(__file__)), 'parents': parents, 'comparisonSha256': sha(output / 'comparison.json'),
    'limits': ['Isolated output retains prior objects; original default clock MSR32/FP opt-in disabled.',
        'No full boot or physical Wii clock claim.']}, indent=2) + '\n')
