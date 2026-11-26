"""Execute complete pinned voice processing with real reference sample decoder, not substituted audio input."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import tempfile
from verify_stock_axwii_schema import sha
from verify_stock_paired_estimates import function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-proof', type=Path, required=True)
    parser.add_argument('--mix-proof', type=Path, required=True)
    args = parser.parse_args()
    proofs = {}
    for name, path, result in [('input', args.input_proof, 'AXWII_VOICE_INPUT_REFERENCE_CHAIN_PASS'),
            ('mix', args.mix_proof, 'AXWII_MAIN_REMOTE_MIX_REFERENCE_PASS')]:
        proof = json.loads(path.read_text())
        assert proof['result'] == result
        for file, digest in proof['dependencies'].items():
            assert sha(file) == digest, file
        proofs[name] = proof
    reference_path = Path(proofs['mix']['referencePath'])
    assert sha(reference_path) == proofs['mix']['referenceSha256']
    reference = json.loads(reference_path.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    base = reference_path.parent / 'dolphin/Source/Core'
    voice = base / 'Core/HW/DSPHLE/UCodes/AXVoice.h'
    ax = base / 'Core/HW/DSPHLE/UCodes/AX.h'
    wii = base / 'Core/HW/DSPHLE/UCodes/AXWii.cpp'
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-full-voice-', dir='/private/tmp'))
    shutil.copytree(args.input_proof.parent / 'shim', cache / 'shim')
    for name in ('axwii-voice-input-reference.h', 'axwii-accelerator-reference.h', 'axwii-resample-reference.h'):
        source = args.input_proof.parent / name
        assert str(source) in proofs['input']['dependencies']
        shutil.copy2(source, cache / name)
    bodies = '\n'.join(function(voice.read_text(), signature) for signature in (
        's16 ClampS16(', 'void MixAdd(', 'static void LowPassFilter(', 'static void BiquadFilter(', 'void ProcessVoice('))
    harness = cache / 'axwii-full-voice-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include "axwii-voice-input-reference.h"
#define AX_WII
#define MAX_SAMPLES_PER_FRAME 96
using DSP::HLE::VolumeData;
using DSP::HLE::PBLowPassFilter;
using DSP::HLE::PBBiquadFilter;
enum class GameQuirk {UsesAXInitialTimeDelay,UsesAXWiimoteBiquad,UsesAXWiimoteLowPass};
struct DolphinAnalytics {
    static DolphinAnalytics& Instance() { static DolphinAnalytics instance;return instance; }
    void ReportGameQuirk(GameQuirk) {}
};
''' + function(voice.read_text(), 'union AXBuffers') + ';\n' +
        function(ax.read_text(), 'enum AXMixControl') + ';\n' + bodies + '''
class AXWiiUCode { public: AXMixControl ConvertMixerControl(u32 mixer_control); };
''' + function(wii.read_text(), 'AXMixControl AXWiiUCode::ConvertMixerControl('))
    source = public / 'stock_axwii_voice_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(cache / 'shim'), '-I', str(base), '-I', str(public),
        str(source), str(base / 'Core/DSP/DSPAccelerator.cpp'), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS 9216 jobs;1048576 masks;1024 inactive;3 transactional refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_FULL_VOICE_REFERENCE_PASS', 'output': run.stdout.strip(),
        'compileCommand': command, 'probeSha256': sha(exe),
        'parentProofs': {str(path): sha(path) for path in [args.input_proof, args.mix_proof]},
        'referencePath': str(reference_path), 'referenceSha256': sha(reference_path),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_voice.h', public / 'stock_axwii_pb.h', public / 'stock_axwii_voice_input.h',
            public / 'stock_axwii_accelerator.h', public / 'stock_axwii_resample.h', public / 'stock_axwii_sample_memory.h',
            public / 'stock_axwii_voice_mix.h', public / 'stock_axwii_filters.h', public / 'stock_axwii_remote_mix.h',
            voice, ax, wii, base / 'Core/DSP/DSPAccelerator.cpp', base / 'Core/DSP/DSPAccelerator.h',
            *(path for path in cache.rglob('*') if path.is_file() and path.suffix == '.h')]},
        'limits': ['Full unchanged pinned ProcessVoice/GetInputSamples/SRC/accelerator/loop callback/mask conversion; no substituted audio input.',
            'Synthetic bounded sample memory/tables and previous bitfield/log/state/saturation/analytics fixture adapters retained.',
            '9216 paired96-sample jobs compare full PB and20 buffers; exhaustive relevant20-bit control combinations and1024 inactive states.',
            'Half the jobs use the callback-backed memory reader through the full voice chain; mapped read refusal preserves whole voice state.',
            'Candidate initial time delay refuses: original Wii unresolved and pinned reference TODO; overflow guards are PC adaptations.',
            'Not actual SHSM PB/sample/DROM/Wii memory mapping or live DSP command/ACK/output/audio acceptance; no runtime integration.',
            'No game/window/input/focus/current-process changes.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
