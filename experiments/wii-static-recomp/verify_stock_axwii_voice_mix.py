"""Compare main-channel post-SRC processing against the untouched pinned ProcessVoice body."""
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
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--resample-proof', type=Path, required=True)
    parser.add_argument('--remote', action='store_true')
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    proof = json.loads(args.resample_proof.read_text())
    assert proof['result'] == 'AXWII_RESAMPLE_REFERENCE_COMPONENT_PASS'
    for path, digest in proof['dependencies'].items():
        assert sha(path) == digest
    base = args.reference.parent / 'dolphin/Source/Core'
    voice = base / 'Core/HW/DSPHLE/UCodes/AXVoice.h'
    ax = base / 'Core/HW/DSPHLE/UCodes/AX.h'
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-mix-', dir='/private/tmp'))
    common = cache / 'shim/Common/CommonTypes.h'
    common.parent.mkdir(parents=True)
    common.write_text('#pragma once\n#include <cstdint>\nusing u8=uint8_t;using u16=uint16_t;'
        'using u32=uint32_t;using s16=int16_t;using s32=int32_t;using s64=int64_t;\n')
    shutil.copy2(args.resample_proof.parent / 'axwii-resample-reference.h', cache / 'axwii-resample-reference.h')
    text = voice.read_text()
    buffers = function(text, 'union AXBuffers') + ';\n'
    control = function(ax.read_text(), 'enum AXMixControl') + ';\n'
    bodies = '\n'.join(function(text, signature) for signature in (
        's16 ClampS16(', 'void MixAdd(', 'static void LowPassFilter(', 'static void BiquadFilter(', 'void ProcessVoice('))
    harness = cache / 'axwii-mix-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#define AX_WII
#define PB_TYPE AXPBWii
#define MAX_SAMPLES_PER_FRAME 96
#include <array>
#include <span>
#include <cstring>
#include "Core/HW/DSPHLE/UCodes/AXStructs.h"
#include "axwii-resample-reference.h"
using DSP::HLE::AXPBWii;
using DSP::HLE::VolumeData;
using DSP::HLE::PBLowPassFilter;
using DSP::HLE::PBBiquadFilter;
struct HLEAccelerator {};
inline std::span<const s16> fixture_input;
void GetInputSamples(HLEAccelerator*,AXPBWii&,s16* samples,u16 count,const s16*) {
    if (fixture_input.size()!=count) { throw std::runtime_error("Fixture sample count"); }
    std::copy(fixture_input.begin(),fixture_input.end(),samples);
}
enum class GameQuirk {UsesAXInitialTimeDelay,UsesAXWiimoteBiquad,UsesAXWiimoteLowPass};
struct DolphinAnalytics {
    static DolphinAnalytics& Instance() { static DolphinAnalytics instance;return instance; }
    void ReportGameQuirk(GameQuirk) {}
};
''' + buffers + control + bodies)
    source = public / 'stock_axwii_voice_mix_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(cache / 'shim'), '-I', str(base), '-I', str(public),
        str(source), '-o', str(exe)]
    if args.remote:
        command.insert(1, '-DOPENSHSM_TEST_REMOTE=1')
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    expected = 'PASS 8192 jobs;8 transactional refusals' if args.remote else 'PASS 8192 jobs;4 transactional refusals'
    assert run.returncode == 0 and expected in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_MAIN_REMOTE_MIX_REFERENCE_PASS' if args.remote else 'AXWII_MAIN_VOICE_MIX_REFERENCE_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'resampleProofPath': str(args.resample_proof.resolve()), 'resampleProofSha256': sha(args.resample_proof),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_voice_mix.h', public / 'stock_axwii_filters.h',
            public / 'stock_axwii_remote_mix.h', public / 'stock_axwii_resample.h', public / 'stock_axwii_pb.h', common, harness,
            cache / 'axwii-resample-reference.h', voice, ax]},
        'limits': ['Unmodified pinned ProcessVoice/filter/MixAdd bodies; input producer substituted with synthetic post-SRC samples and analytics sink.',
            'Main12channels/envelope/lowpass/biquad/PB state; newfilter true and initial time delay disabled. Remote enabled only with --remote.',
            'Remote fixtures cover8subchannels, disabled/enabled, bothfilters,32/96frames, provided synthetic512bank/missingbank fallback, two consecutive updates.' if args.remote else 'Remote disabled in this profile.',
            '4096 paired synthetic jobs; random/internal masks and singlebit flags; reference signed sums bounded to avoid UB.',
            'Malformed/overflow refusal transactionality is PC safety adaptation, not original hardware exception proof.',
            'No full live voice/command execution/actual DSP table/hardware/audio acceptance or game/window launch.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
