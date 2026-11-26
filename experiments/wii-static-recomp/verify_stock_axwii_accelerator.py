"""Windowless comparisons against unchanged pinned DSP accelerator and AX loop callback."""
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
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    base = args.reference.parent / 'dolphin/Source/Core'
    accelerator = base / 'Core/DSP/DSPAccelerator.cpp'
    header = base / 'Core/DSP/DSPAccelerator.h'
    voice = base / 'Core/HW/DSPHLE/UCodes/AXVoice.h'
    structs = base / 'Core/HW/DSPHLE/UCodes/AXStructs.h'
    callback = function(voice.read_text(), 'void OnSampleReadEndException() override')
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-accelerator-', dir='/private/tmp'))
    shim = cache / 'shim'
    shim_files = {
        'Common/CommonTypes.h': '''#pragma once
#include <cstdint>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s16=int16_t;using s32=int32_t;using s64=int64_t;
''',
        'Common/BitField.h': '''#pragma once
#include <cstdint>
template<unsigned Offset,unsigned Width,class T> struct BitField {
    uint16_t storage;
    operator T() const { return T((storage>>Offset)&((1u<<Width)-1)); }
};
''',
        'Common/Logging/Log.h': '''#pragma once
#define ERROR_LOG_FMT(...) ((void)0)
#define WARN_LOG_FMT(...) ((void)0)
''',
        'Common/ChunkFile.h': '''#pragma once
#include "Common/CommonTypes.h"
#include <algorithm>
#include <limits>
class PointerWrap { public: template<class T> void Do(T&) {} };
namespace MathUtil {
template<class T> T SaturatingCast(s64 value) {
    return T(std::clamp(value,s64(std::numeric_limits<T>::min()),s64(std::numeric_limits<T>::max())));
}
}
'''}
    for name, text in shim_files.items():
        path = shim / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    harness = cache / 'axwii-accelerator-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <span>
#include <stdexcept>
#include "Core/DSP/DSPAccelerator.h"
#include "Core/HW/DSPHLE/UCodes/AXStructs.h"
using DSP::HLE::AXPBWii;
class Oracle final : public DSP::Accelerator {
public:
    AXPBWii pb{};
    AXPBWii* acc_pb=&pb;
    std::span<const uint8_t> memory;
    Oracle(std::span<const uint8_t> bytes,const openshsm::experiment::AxWiiSampleState& state):memory(bytes) {
        SetStartAddress(state.start);SetEndAddress(state.end);SetCurrentAddress(state.current);
        SetSampleFormat(state.format);SetGain(state.gain);SetPredScale(state.pred_scale);
        SetYn1(state.yn1);SetYn2(state.yn2);
        pb.running=state.running;pb.audio_addr.looping=state.looping;pb.is_stream=state.is_stream;
        pb.adpcm_loop_info.pred_scale=state.loop_pred_scale;
        pb.adpcm_loop_info.yn1=state.loop_yn1;pb.adpcm_loop_info.yn2=state.loop_yn2;
    }
    bool stopped() const { return m_reads_stopped; }
    void OnRawReadEndException() override {}
    void OnRawWriteEndException() override {}
    uint8_t ReadMemory(uint32_t address) override {
        if(address>=memory.size()) { throw std::runtime_error("Reference fixture bounds"); }
        return memory[address];
    }
    void WriteMemory(uint32_t,uint8_t) override { throw std::runtime_error("Unexpected reference write"); }
''' + callback + '\n};\n')
    source = public / 'stock_axwii_accelerator_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(shim), '-I', str(base), '-I', str(public),
        str(source), str(accelerator), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS 884736 samples;5 refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_ACCELERATOR_REFERENCE_COMPONENT_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_accelerator.h', harness, accelerator, header, voice, structs,
            *(shim / name for name in shim_files)]},
        'limits': ['Unmodified pinned accelerator cpp/header and AX Wii end callback; synthetic bounded memory and bitfield/log/state/saturation adapters supplied.',
            'ADPCM/PCM8/PCM16, nonloop/loop/stream plus aligned end quirks compared; synthetic samples and bounded coefficients.',
            'Candidate refuses unverified32-bit accumulator overflow and unknown formats; not complete DSP hardware/MMIO/raw access.',
            'No real PB/sample job, actual DROM coefficients or listening acceptance; not integrated into runtime.',
            'No game/window launch or current-process/input/focus changes.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
