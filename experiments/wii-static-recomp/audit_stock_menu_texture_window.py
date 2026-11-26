"""Reuse existing packet/coherence checks in a menu-period owned run, private outputs only."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
parser.add_argument('--texture-capture-after-ms', type=int, choices=(25000, 33000), default=25000)
parser.add_argument('--bp-order', action='store_true')
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
public = Path(__file__).resolve().parent
root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
tag = 'bp-order-menu' if args.bp_order else 'context-stage-menu'
candidate = 'window-bp-order' if args.bp_order else 'window-context-stage'
component_result = ('BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED' if args.bp_order
    else 'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED')
run_path = artifacts / f'headless-sc-pc-headless-windowed-{tag}-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['seconds'] == 90
assert run['textureObserve'] and run['textureCoherence'] and run['textureCaptureAfterMs'] == args.texture_capture_after_ms
assert run['movieCaptureAfterMs'] == 10000 and run['temporaryEvidence']
build_path = root / candidate / 'build.json'
build = json.loads(build_path.read_text())
component_path = build_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == component_result
assert sha(build['executablePath']) == run['executableSha256'] == build['executableSha256']
log = artifacts / f'headless-sc-pc-headless-windowed-{tag}.log'
assert sha(log) == run['logSha256']
base = public / 'audit_stock_profile_packets.py'
script = base.read_text()
start = script.index('parser = argparse.ArgumentParser()')
end = script.index("base = Path(__file__)", start)
script = script[:start] + script[end:]
script = script[:script.index('if args.sample_symbols:')] + script[script.index('exec(compile(script, str(base)', script.index('if args.sample_symbols:')):]
script = script.replace('window-post-present', candidate)
script = script.replace('post-present-profile', tag)
script = script.replace('POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED',
    component_result)
scope = {'__file__': str(Path(__file__).resolve()), 'artifacts': artifacts}
exec(compile(script, str(base), 'exec'), scope)
packet_path = artifacts / 'profile-input-audit.json'
packet_audit = json.loads(packet_path.read_text())
phase_base = public / 'audit_stock_live_phases.py'
phase = phase_base.read_text()
phase_scope = {'re': re, 'text': log.read_text(), 'args': type('Options', (), {'timer_only': True})()}
exec(compile(phase[phase.index("fields = ['hostUs'"):phase.index('movie_path = root /')], str(phase_base), 'exec'), phase_scope)
coherence_base = public / 'audit_stock_texture_late.py'
code = coherence_base.read_text()
start = code.index("directory = Path(run['textureDirectory'])")
end = code.index('if movie_missing:\n    report', start)
coherence_scope = {'Path': Path, 'run': run, 'artifacts': artifacts, 'collections': collections, 'sha': sha,
    'scope': {'scope': {'sha': sha}}, 'packet': {'runSha256': sha(run_path), 'currentPhaseSummary': phase_scope['summary']},
    'movie_missing': False}
exec(compile(code[start:end], str(coherence_base), 'exec'), coherence_scope)
report = coherence_scope['report']
associations = []
address_matches = []
for texture in report['records']:
    for packet in packet_audit['records']:
        if not packet['end']:
            continue
        begin, end = packet['begin'], packet['end']
        for plane, field, size in [('Y', 'r4', (640, 480)), ('U', 'r5', (320, 240)), ('V', 'r6', (320, 240))]:
            if (texture['width'], texture['height']) != size:
                continue
            if (texture['address'] & 0x1FFFFFFF) != (begin[field] & 0x1FFFFFFF):
                continue
            address_matches.append({'textureSequence': texture['sequence'], 'plane': plane,
                'packetIndex': packet['capture']['index'],
                'intervalGapUs': max(begin['hostUs'] - texture['afterUs'],
                    texture['beforeUs'] - end['hostUs'], 0)})
            if texture['beforeUs'] <= end['hostUs'] and texture['afterUs'] >= begin['hostUs']:
                associations.append({'textureSequence': texture['sequence'], 'plane': plane,
                    'packetIndex': packet['capture']['index'], 'packetMatches': packet['moduloPositionMatches'],
                    'decoderBeginUs': begin['hostUs'], 'decoderEndUs': end['hostUs'],
                    'textureBeforeUs': texture['beforeUs'], 'textureAfterUs': texture['afterUs']})
images = []
prefix = Path(run['capturePrefix'])
for bmp in sorted(prefix.parent.glob(prefix.name + '_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as picture:
        rgb = picture.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.tobytes() == rgb.tobytes()
    images.append({'bmpPath': str(bmp), 'bmpSha256': sha(bmp), 'displayPath': str(png), 'displaySha256': sha(png)})
texture_begin = min(row['beforeUs'] for row in report['records'])
texture_end = max(row['afterUs'] for row in report['records'])
complete_packets = [row for row in packet_audit['records'] if row['end']]
packet_begin = min(row['begin']['hostUs'] for row in complete_packets)
packet_end = max(row['end']['hostUs'] for row in complete_packets)
loop_packets = [row for row in complete_packets
    if any(match['movie'] == 'LOOP' for match in row['moduloPositionMatches'])]
loop_begin = min(row['begin']['hostUs'] for row in loop_packets) if loop_packets else None
coverage = {'textureBeginUs': texture_begin, 'textureEndUs': texture_end,
    'packetBeginUs': packet_begin, 'packetEndUs': packet_end,
    'wholeWindowOverlapUs': max(min(texture_end, packet_end) - max(texture_begin, packet_begin), 0),
    'packetStartAfterTextureEndUs': max(packet_begin - texture_end, 0),
    'firstLoopPacketBeginUs': loop_begin,
    'addressMatchedPairs': len(address_matches),
    'minimumAddressMatchedIntervalGapUs': min(row['intervalGapUs'] for row in address_matches) if address_matches else None,
    'simultaneousAddressMatchedPairs': len(associations),
    'menuTextureDecodeAcceptance': 'UNPROVEN'}
if loop_begin is not None and texture_end < loop_begin:
    coverage['suggestedTextureDelayMs'] = min(180000,
        run['textureCaptureAfterMs'] + (loop_begin - texture_begin + 999999) // 1000000 * 1000)
report.update(result='OWNED_MENU_TEXTURE_WINDOW_AUDITED',
    dependencies={str(path): sha(path) for path in [Path(__file__).resolve(), base, phase_base, coherence_base,
        run_path, build_path, component_path, packet_path]},
    packetSummary=packet_audit['summary'], textureDecoderAssociations=associations,
    temporalCoverage=coverage, imageCaptures=images)
report['limits'].append('Physical/virtual buffer address and host interval overlap association, not proof exact original frame identity or write instruction.')
report['limits'].append('Early capped observer sample may not coincide with corrupt EFB; no whole-menu race elimination/TEV state/original Wii oracle.')
if args.bp_order:
    title_samples = []
    for frame in (1200, 1500, 1800):
        bmp = Path(str(prefix) + f'_{frame}.bmp')
        assert bmp.is_file()
        with Image.open(bmp) as picture:
            assert picture.size == (640, 480)
            pixels = picture.convert('RGB').resize((80, 60), Image.Resampling.BOX).tobytes()
        red, count = 0, 0
        for y in range(30, 56):
            for x in range(4, 76):
                offset = (y * 80 + x) * 3
                r, g, b = pixels[offset:offset + 3]
                red += r > g + 25 and r > b + 25
                count += 1
        title_samples.append({'presentationIndex': frame, 'rawEfbPath': str(bmp),
            'rawEfbSha256': sha(bmp), 'bottomRedDominantFraction': red / count})
    report['titleSamples'] = title_samples
    report['limits'].append('Three sampled title presentations only; no whole-video flicker elimination or exact same-frame baseline equivalence.')
path = artifacts / 'menu-texture-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps({key: report[key] for key in ['captures', 'changedPairs', 'decodedMixedPairs']}, indent=2))
print('decoder associations', len(associations))
