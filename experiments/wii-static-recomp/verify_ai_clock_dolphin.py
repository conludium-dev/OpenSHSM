"""Verify original clock programming and waits; identify Dolphin hardware stubs."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dolphin-ai-clock'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
reports = []
for name in ('dolphin-ai-clock', 'dolphin-ai-clock-unobserved'):
    directory = private / name
    generation_path = directory / 'generation.json'
    capture_path = directory / 'fpr-init-true-dolphin.json'
    generation = json.loads(generation_path.read_text())
    capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
    for key, filename in [('generatorSha256', 'build_ai_clock_dolphin.py'), ('parentGeneratorSha256', 'build_si_query_dolphin.py'),
            ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
        assert generation[key] == sha(experiment / filename)
    assert generation['originalSha256'] == sha(original_path)
    assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_ai_clock_dolphin.ps1')
    assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(directory / 'fpr-init.dol')
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    assert capture['accurateCache'] == 'True' and capture['records'] == len(generation['records']) == 16
    for flag in ('Dolphin.Core.CPUCore=0', 'dolphin-ai-clock-user', '-v Null'):
        assert flag in capture['arguments']
    observed = name == 'dolphin-ai-clock'
    assert generation['observed'] == observed and len(generation['patches']) == (7 if observed else 0)
    image = (directory / 'fpr-init.dol').read_bytes()
    layout = struct.unpack('>64I', image[:256])
    def offset(address):
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        return layout[section] + address - layout[18 + section]
    allowed = set()
    for patch in generation['patches']:
        assert patch['offset'] == offset(patch['address'])
        assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
        word = struct.unpack_from('>I', image, patch['offset'])[0]
        assert word >> 26 == 18 and word & 3 == 0
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        assert patch['address'] + displacement == patch['trampoline']
        words = patch['words']
        assert list(struct.unpack_from('>' + 'I' * len(words), image, offset(patch['trampoline']))) == words
        assert words[:3] == [patch['opcode'], 0x9161fff8, 0x9181fffc] and words[-3:-1] == [0x8161fff8, 0x8181fffc]
        displacement = words[-1] & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        assert words[-1] >> 26 == 18 and words[-1] & 3 == 0
        assert patch['trampoline'] + (len(words) - 1) * 4 + displacement == patch['address'] + 4
        allowed.update(range(patch['offset'], patch['offset'] + 4))
    assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
    data = base64.b64decode(capture['data'])
    assert len(data) == 16 * 736
    values = []
    for case in generation['records']:
        index, mode = case['index'], case['mode']
        row = data[index * 736:(index + 1) * 736]
        assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
        final = list(struct.unpack_from('>12I', row, 24))
        assert final == [0, 0, 0, 243000000, 0, 0, 0, 0x32, 0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736]
        phases, elapsed = [], []
        if observed:
            assert struct.unpack_from('>I', row, 72)[0] == 6
            expected = [(mode << 8, 0x80212af8), (0, 0x80212b04),
                (0x04640fc0 if mode == 0 else 0x04b0ffce, 0x80212b6c if mode == 0 else 0x80212b94),
                (0, 0x80212be0), (0x40000000, 0x80212c30), (0x80000000, 0x80212c80)]
            for phase, (written, instruction) in enumerate(expected):
                values_phase = list(struct.unpack_from('>4I', row, 128 + phase * 32))
                assert values_phase[0:2] == [written, 0] and values_phase[3] == instruction
                phases.append(values_phase)
            timestamps = [phase[2] for phase in phases] + [struct.unpack_from('>I', row, 76)[0]]
            quantum = ((0x431cde83 * (final[3] >> 2)) >> 32) >> 15
            for left, right, threshold in zip(timestamps[1:], timestamps[2:], (100, 100, 1000, 1000, 1000)):
                delta = (right - left) & 0xffffffff
                assert delta >= (threshold * quantum + 7) // 8 and delta < 0x80000000
                elapsed.append(delta)
        else:
            assert struct.unpack_from('>I', row, 72)[0] == 0 and row[128:320] == bytes(192)
        values.append({**case, 'final': final, 'phases': phases, 'waitTicks': elapsed})
    reports.append({'values': values, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path)})
assert [row['final'] for row in reports[0]['values']] == [row['final'] for row in reports[1]['values']]
ghidra_path = output / 'ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['runnerSha256'] == sha(experiment / 'verify_ai_clock_ghidra.py')
assert ghidra['scriptSha256'] == sha(experiment / 'ExportFormatSpan.java')
for row in ghidra['records']:
    assert row['discoveredBodyBytes'] == row['bytes'] == 544
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_AI_CLOCK16_COMMANDS_REAL_WAITS_UNPATCHED16_DOLPHIN_STUB_PROFILE',
    'reports': reports, 'verifierSha256': sha(Path(__file__)), 'ghidraSha256': sha(ghidra_path),
    'originalBehavior': ['Own-DOL PPC arithmetic/branches emit six register writes in each mode; original OSGetTick wait loops execute.',
        'Observed store timestamps meet five SDK wait thresholds; restored fixture SP/r2/r13/r30 and final fields match the unpatched control.'],
    'pcAdaptation': ['Dolphin implements offsets180/1CC/1D0 as constant-zero reads/no-op writes; measured zeros do not prove physical Wii PLL behavior.'],
    'source': 'https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/HW/WII_IPC.cpp',
    'limits': ['Prepared MSR32/HID0/r2-r13/loader bus frequency; observation overhead, not cycle-exact timing/all registers.',
        'Native clock adapter/boot advance/audio output/physical Wii behavior remain unverified.']}, indent=2) + '\n')
print('PASS16 original clock commands/5real SDK waits +16unpatched controls; Dolphin zero/no-op profile explicitly distinguished')
