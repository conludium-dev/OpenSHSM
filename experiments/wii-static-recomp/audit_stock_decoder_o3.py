"""Pin unchanged decoder source/guards, numerical flags, replay proof and actual GUI observations."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-decoder-o3'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
source, obj, exe = output / 'output_37.cpp', output / 'output_37.cpp.o', output / 'OpenSHSMStockDecoderO3'
assert sha(source) == build['sourceSha256'] and sha(obj) == build['objectSha256'] and sha(exe) == build['executableSha256']
assert source.read_bytes() == (root / 'headless-psq-scale/output_37.cpp').read_bytes()
guard = (output / 'constant_fp_guard.h').read_text().replace(build['accessorBody'] + '\n', '', 1)
assert guard.replace('stock_inline_read_hid2(ctx)', 'experiment_read_hid2(ctx)') == (
    root / 'headless-constant-fp/constant_fp_guard.h').read_text()
inline_path = root / 'window-hid2-inline/build.json'
inline = json.loads(inline_path.read_text())
assert sha(inline_path) == build['inlineBuildSha256']
arguments = list(inline['arguments'])
arguments[arguments.index('-O2')] = '-O3'
assert arguments == build['arguments'] and '-ffp-contract=off' in arguments
assert not any('fast-math' in arg for arg in arguments)
parent_path = root / 'window-audio-callback/build.json'
assert sha(parent_path) == build['parentBuildSha256']
command = json.loads(parent_path.read_text())['linkCommand']
old = next(arg for arg in command if Path(arg).name == 'output_37.cpp.o')
command[command.index(old)] = str(obj)
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
proof_path = output / 'verification.json'
proof = json.loads(proof_path.read_text())
assert proof['buildSha256'] == sha(build_path) and proof['guardCases'] == 19760
assert proof['verifierSha256'] == sha(public / 'verify_stock_hid2_inline.py')
assert proof['result'] == 'DECODER_O3_GUARD_FRAME_STATE_IDENTICAL12' and len(proof['rows']) == 12
assert sha(output / 'guard-probe.log') == proof['guardLogSha256']
assert 'CONSTANT_FP_DIFFERENTIAL_PASS 19760' in (output / 'guard-probe.log').read_text()
assert sha(public / 'stock_constant_fp_probe.cpp') == proof['guardSourceSha256']
assert sha(output / 'constant_fp_cases.h') == proof['casesSha256']
assert sha(output / 'frame-probe.cpp') == proof['fixtureSourceSha256']
assert sha(output / 'frame-probe.cpp.o') == proof['fixtureObjectSha256']
reference_state = None
for row in proof['rows']:
    raw = output / f"{row['variant']}-{row['iteration']}.yuv"
    state = Path(str(raw) + '.state')
    assert sha(raw) == row['outputSha256'] and sha(state) == row['stateSha256']
    if reference_state is None:
        reference_state = state.read_bytes()
    assert state.read_bytes() == reference_state
run_path = root / 'headless-sc-pc-headless-windowed-decoder-o3-observed-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['windowed'] and run['capture'] and run['dspSupply'] and run['wallTimebase'] and run['skipWiiNotices']
assert run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-decoder-o3-observed.log'
assert sha(log) == run['logSha256']
text = log.read_text()
callback_fields = ['wallUs', 'calls', 'requested', 'supplied', 'missing', 'short', 'errors', 'final']
callback = [dict(zip(callback_fields, map(int, row))) for row in re.findall(
    r'^\[AudioCallback\] ' + ' '.join(key + r'=(\d+)' for key in callback_fields) + r'$', text, re.M)]
assert callback and callback[-1]['final'] == 1 and callback[-1]['errors'] == 0
assert callback[-1]['requested'] == callback[-1]['supplied'] + callback[-1]['missing']
adma_fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
adma = [dict(zip(adma_fields, map(int, row))) for row in re.findall(
    r'^\[ADMAAccounting\] ' + ' '.join(key + r'=(\d+)' for key in adma_fields) + r'$', text, re.M)]
assert adma
for row in adma:
    assert row['accepted'] - row['supplied'] == row['ring']
    if not row['input48']:
        assert row['input32'] == row['accepted'] + row['dropped']
assert '[ GPU Hang detected ]' not in text
captures = {}
for bmp in root.glob('headless-sc-pc-decoder-o3-observed-efb_debug_*.bmp'):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'DECODER_O3_SOURCE_REPLAY_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'proofSha256': sha(proof_path), 'runSha256': sha(run_path),
    'auditorSha256': sha(Path(__file__)), 'lastCallback': callback[-1], 'admaRows': adma,
    'lastAdma': adma[-1], 'maxRing': max(row['ring'] for row in adma), 'captures': captures,
    'excludedAdmaRows': text.count('[ADMAAccounting] ') - len(adma),
    'limits': ['Single-frame alternating controlled native benchmark; live sequences differ, no controlled FPS speedup claim.',
        'Full YUV and selected final PPC state exact; all original RAM/hardware/IRQ context not independently proved.',
        'No full game/profile/save/controller/sound/video quality acceptance or release promotion.']}, indent=2) + '\n')
print('DECODER_O3_SOURCE_REPLAY_LIVE_AUDITED', len(captures))
print(json.dumps({'lastCallback': callback[-1], 'lastAdma': adma[-1]}, indent=2))
