"""Compare all three AX SRC paths without launching a game or window."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
from verify_stock_axwii_schema import sha
from verify_stock_paired_estimates import function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['result'] == 'PINNED_AXWII_SCHEMA_REFERENCE_READY_NOT_RUNTIME_CODE'
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    voice = args.reference.parent / 'dolphin/Source/Core/Core/HW/DSPHLE/UCodes/AXVoice.h'
    body = function(voice.read_text(), 'u32 ResampleAudio(')
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-src-', dir='/private/tmp'))
    harness = cache / 'axwii-resample-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdint>
#include <functional>
#include <cstring>
#include <algorithm>
#include <limits>
using s16=int16_t;using u16=uint16_t;using s32=int32_t;using u32=uint32_t;using s64=int64_t;
enum {SRCTYPE_POLYPHASE=0,SRCTYPE_LINEAR=1,SRCTYPE_NEAREST=2};
namespace MathUtil {
template<class T> T SaturatingCast(s64 value) {
    return T(std::clamp(value,s64(std::numeric_limits<T>::min()),s64(std::numeric_limits<T>::max())));
}
}
''' + body)
    source = public / 'stock_axwii_resample_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(public), str(source), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS 16384 comparisons;10 refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_RESAMPLE_REFERENCE_COMPONENT_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_resample.h', harness, voice]},
        'limits': ['Unmodified pinned ResampleAudio body; supplied synthetic callback/enums and bounded integer saturation adapter.',
            'All3 paths plus missing-coefficients polyphase fallback compared; synthetic coefficients, not verified DSP DROM table.',
            'Output samples, ordered callback reads, fractional position and4 history values compared under ASan/UBSan.',
            'No sample accelerator/ADPCM/end-loop/voice filters/mixer/real PB job or physical Wii verification.',
            'Not integrated into runtime; no game/window/input/focus/clock/audio device changes.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
