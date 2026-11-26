"""Compare whole compiled startup with original-code Dolphin captures, not playback."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'audio-init-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_audio_trace_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_audio_init_native.py')
assert build['originalSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
assert len(build['records']) == 125 and len(build['changes']) == 34
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in build['sourceHashes'].items():
    assert sha(Path(name)) == digest
for name, digest in build['headerHashes'].items():
    assert sha(Path(name)) == digest
assert build['vendorDspSha256'] == sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_dsp.cpp'))
base = json.loads((private / 'mass-flush-syscall-boot/boot.json').read_text())
input_source = Path(next(row['source'] for row in base['records'] if row['file'] == 'output_63.cpp'))
native_source = Path(next(row['source'] for row in build['records'] if row['file'] == 'output_63.cpp')).read_text()
reconstructed = native_source
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', original[:256])
for change in build['changes']:
    assert reconstructed.count(change['after']) == 1
    reconstructed = reconstructed.replace(change['after'], change['before'])
    site = change['site']
    section = next(i for i in range(18) if layout[18 + i] <= site < layout[18 + i] + layout[36 + i])
    opcode = struct.unpack_from('>I', original, layout[section] + site - layout[18 + section])[0]
    marker = f'    // 0x{site:08X}: {opcode:08X}\n'
    assert marker + change['after'] in native_source
assert reconstructed == input_source.read_text()
ghidra_dir = private / 'dolphin-audio-init/ghidra'
ghidra = json.loads((ghidra_dir / 'verification.json').read_text())
assert ghidra['result'] == 'OS_AUDIO_INIT_GHIDRA116_SPAN_DISCOVERED460_EXCLUDES_UNREACHABLE_NOP'
assert ghidra['records'][0]['assemblySha256'] == sha(ghidra_dir / '__OSInitAudioSystem.asm')
assert ghidra['records'][0]['decompiledSha256'] == sha(ghidra_dir / '__OSInitAudioSystem.c')
assert ghidra['membershipSha256'] == sha(ghidra_dir / 'body-membership.txt')
exe = output / 'audio-init-probe'
assert build['executableSha256'] == sha(exe)
original_capture = json.loads((private / 'dolphin-audio-init/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
original_data = base64.b64decode(original_capture['data'])
original_proof = json.loads((private / 'dolphin-audio-init/comparison.json').read_text())
trace_proof = json.loads((private / 'dolphin-audio-trace/comparison.json').read_text())
def validate_normal(text, count=16, wrong_mail=False):
    assert text.splitlines()[0] == 'AUDIO_CLOCK_GUARDS 3'
    cases, memories, accesses = {}, {}, {}
    for line in text.splitlines()[1:]:
        tag, *values = line.split()
        values = list(map(int, values))
        index, *values = values
        if tag == 'AUDIO_CASE':
            assert index not in cases
            cases[index] = values
        elif tag == 'AUDIO_MEMORY':
            assert index not in memories
            memories[index] = values
        else:
            assert tag == 'AUDIO_ACCESS'
            accesses.setdefault(index, []).append(values)
    assert set(cases) == set(memories) == set(accesses) == set(range(count))
    for index in range(count):
        expected = list(original_proof['states'][index])
        expected[7] = 0x807f0000
        if wrong_mail:
            expected[11] = 0x4349
        assert cases[index] == expected, (index, cases[index], expected)
        expected_memory = list(struct.unpack_from('>104I', original_data, index * 736 + 128))
        assert memories[index] == expected_memory
        expected_accesses = [[row['site'], row['value'], row['address']] for row in trace_proof['traces'][index]]
        if wrong_mail:
            expected_accesses[18][1] = 0x4349
        assert [row[:3] for row in accesses[index]] == expected_accesses
        ticks = [row[3] for row in accesses[index]]
        assert ticks == sorted(ticks) and ticks[9] - ticks[8] >= 2194
    return cases
results = {}
for mode in ('normal', 'lost-dma', 'lost-mail', 'wrong-mail'):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stderr == '', (mode, result.returncode, result.stderr)
    saved = (output / (mode + '.log')).read_text()
    assert build['results'][mode]['logSha256'] == sha(output / (mode + '.log'))
    if mode == 'normal':
        validate_normal(result.stdout)
        validate_normal(saved)
    elif mode == 'wrong-mail':
        validate_normal(result.stdout, 1, True)
        validate_normal(saved, 1, True)
        try:
            validate_normal(result.stdout, 1)
        except AssertionError:
            pass
        else:
            raise AssertionError('Wrong mailbox accepted as original behavior')
    else:
        command, completed, pc = (7, 0, 0x80212db0) if mode == 'lost-dma' else (14, 2, 0x80212e48)
        expected = f'AUDIO_CLOCK_GUARDS 3\nAUDIO_STOP {mode} {pc} {command} {completed} Audio instruction budget exceeded\n'
        assert result.stdout == saved == expected
    results[mode] = result.stdout
baseline = results['normal']
for tag, offset in [('AUDIO_CASE', 13), ('AUDIO_MEMORY', 2), ('AUDIO_ACCESS', 3)]:
    lines = baseline.splitlines()
    number = next(i for i, line in enumerate(lines) if line.startswith(tag + ' '))
    tokens = lines[number].split()
    tokens[offset] = str(int(tokens[offset]) ^ 1)
    lines[number] = ' '.join(tokens)
    try:
        validate_normal('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Mutated state/memory/access accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_WHOLE_AUDIO_INIT16_DSP24_CACHE_DMA_ABI_MATCH',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)),
    'originalProofSha256': sha(private / 'dolphin-audio-init/comparison.json'),
    'traceProofSha256': sha(private / 'dolphin-audio-trace/comparison.json'),
    'ghidraProofSha256': sha(ghidra_dir / 'verification.json'),
    'headerHashes': {str(experiment / name): sha(experiment / name) for name in
        ('ai_clock_profile.h', 'dsp_startup_frontend.h', 'dsp_startup_backend.h', 'flush_syscall.h')},
    'cases': 16, 'selectedAccesses': 24, 'memoryBytesPerCase': 416,
    'negatives': ['Lost DMA stalls before acknowledgement', 'Lost mailbox stalls before halt',
        'Wrong mailbox returns as in original control flow but differs from reference and is rejected by comparator'],
    'limits': ['Prepared arena/IPL/CPU/stack/bus and copied syscall vector; not retail boot or audio playback.',
        'Existing vendor DMA copy is synchronous; reset and startup-mail scheduling are bounded PC HLE adaptations.',
        'Selected access order/values and wait lower bound verified, not all polls/physical timing/DSP instruction emulation.']}, indent=2) + '\n')
print('PASS16whole compiled audio startups:24accesses/416memory bytes/ABI/tick wait; lostDMA/lostMail/wrongMail detected')
