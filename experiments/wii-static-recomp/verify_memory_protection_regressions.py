"""Isolated audio proof after extending MI storage; prior boot objects remain intact."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parents = []
for name in ('build_audio_init_native.py', 'verify_audio_init_native.py'):
    parent = experiment / name
    body = parent.read_text().replace('audio-init-native', 'memory-audio-regression')
    exec(compile(body, str(parent), 'exec'), {'__file__': str(parent)})
    parents.append({'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()})
output = Path('work/private-game/static-recomp/memory-audio-regression')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'regressions.json').write_text(json.dumps({'result': 'MI_EXTENSION_ORIGINAL_AUDIO16_DMA_MAIL_REGRESSION_PASS',
    'runnerSha256': sha(Path(__file__)), 'parents': parents, 'comparisonSha256': sha(output / 'comparison.json'),
    'limits': ['Isolated rebuild; memory-protection profile not enabled in this previous audio fixture.',
        'Same DSP HLE/startup scope, not playback or full boot.']}, indent=2) + '\n')
