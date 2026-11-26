"""Control the known timebase-mode difference in the same uninterrupted packet fixture, not live IRQ context."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'live-packet-replay'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prior_path = output / 'verification.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'EXACT_LIVE_PACKET_UNINTERRUPTED_REPLAYS_IDENTICAL3_EACH'
assert prior['verifierSha256'] == sha(Path('experiments/wii-static-recomp/replay_stock_live_packets.py'))
exe = Path(prior['executablePath'])
assert sha(exe) == prior['executableSha256']
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == prior['snapshotSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_WALLTB'] = '1'
cases = []
for case in prior['cases']:
    packet = Path(case['packetPath'])
    assert sha(packet) == case['selectedLiveRecord']['capture']['packetSha256']
    cases.append({'movie': case['movie'], 'original': case, 'replays': []})
for iteration in range(3):
    order = cases if iteration % 2 == 0 else list(reversed(cases))
    for case in order:
        raw = output / f'{case["movie"].lower()}-wall-{iteration}.yuv'
        assert not raw.exists()
        result = subprocess.run([str(exe), str(snapshot), str(raw), case['original']['packetPath']],
            env=env, capture_output=True, text=True, timeout=30)
        log = output / f'{case["movie"].lower()}-wall-{iteration}.log'
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:]
        match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', result.stdout)
        assert match
        reference = output / f'{case["movie"].lower()}-0.yuv'
        assert raw.read_bytes() == reference.read_bytes()
        state = Path(str(raw) + '.state')
        assert state.read_bytes() == Path(str(reference) + '.state').read_bytes()
        case['replays'].append({'iteration': iteration, 'terminalReturncode': result.returncode,
            'decoderNs': int(match[1]), 'outputSha256': sha(raw), 'stateSha256': sha(state), 'logSha256': sha(log)})
summary = []
for case in cases:
    original = case['original']
    summary.append({'movie': case['movie'], 'frame': original['selectedLiveRecord']['moduloPositionMatches'][0]['frame'],
        'instructionTimebaseMedianUs': original['nativeMedianUs'],
        'wallTimebaseMedianUs': statistics.median(row['decoderNs'] / 1000 for row in case['replays']),
        'liveWallUs': original['selectedLiveRecord']['wallUs']})
(output / 'wall-verification.json').write_text(json.dumps({
    'result': 'EXACT_PACKET_WALL_TIMEBASE_OUTPUT_STATE_IDENTICAL3_EACH',
    'priorReplaySha256': sha(prior_path), 'executableSha256': sha(exe), 'snapshotSha256': sha(snapshot),
    'verifierSha256': sha(Path(__file__)), 'environment': {'NWII_WALLTB': '1'}, 'cases': cases, 'summary': summary,
    'limits': ['Same packet/executable/earlier snapshot/relocated input/MSR.EE=0; timebase mode only changed via existing environment switch.',
        'Complete YUV and selected final PPC state including instruction count equal to instruction-timebase replay.',
        'Live entry guest/device/memory context, enabled IRQs and callback state still differ.',
        'Default fixture tb_freq remains unchanged; not exact60.75MHz live timebase frequency/state equivalence.',
        'No original wait/timer removal or controlled live game speedup/audio/profile/hardware acceptance.']}, indent=2) + '\n')
print('EXACT_PACKET_WALL_TIMEBASE_OUTPUT_STATE_IDENTICAL3_EACH')
print(json.dumps(summary, indent=2))
