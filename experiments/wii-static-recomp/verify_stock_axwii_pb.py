"""Windowless wire-layout comparison against pinned, unmodified AXWii PB readers/writers."""
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
    base = args.reference.parent / 'dolphin/Source/Core'
    ucode = base / 'Core/HW/DSPHLE/UCodes'
    cpp = (ucode / 'AXWii.cpp').read_text()
    bodies = '\n'.join(function(cpp, signature) for signature in (
        'void AXWiiUCode::ReadPB(', 'void AXWiiUCode::WritePB('))
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-pb-', dir='/private/tmp'))
    shim = cache / 'shim/Common/CommonTypes.h'
    shim.parent.mkdir(parents=True)
    shim.write_text('#pragma once\n#include <cstdint>\nusing u8=uint8_t;using u16=uint16_t;'
        'using u32=uint32_t;using s16=int16_t;using s32=int32_t;\n')
    harness = cache / 'axwii-pb-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <stdexcept>
#include "Core/HW/DSPHLE/UCodes/AXStructs.h"
using namespace DSP::HLE;
namespace Memory {
class MemoryManager {
public:
    std::array<u8, 332> bytes{};
    template<class T> void CopyFromEmuSwapped(T* destination, u32 address, size_t size) {
        static_assert(sizeof(T)==2);
        if (size%2 || uint64_t(address)+size>bytes.size()) { throw std::runtime_error("Reference fixture bounds"); }
        for (size_t index=0;index<size/2;++index) {
            const u16 word=u16(u16(bytes[address+index*2])<<8|bytes[address+index*2+1]);
            std::memcpy(reinterpret_cast<char*>(destination)+index*2,&word,2);
        }
    }
    template<class T> void CopyToEmuSwapped(u32 address, const T* source, size_t size) {
        static_assert(sizeof(T)==2);
        if (size%2 || uint64_t(address)+size>bytes.size()) { throw std::runtime_error("Reference fixture bounds"); }
        for (size_t index=0;index<size/2;++index) {
            u16 word;
            std::memcpy(&word,reinterpret_cast<const char*>(source)+index*2,2);
            bytes[address+index*2]=u8(word>>8);
            bytes[address+index*2+1]=u8(word);
        }
    }
};
}
class AXWiiUCode {
public:
    u32 m_crc=0x4cc52064;
    void ReadPB(Memory::MemoryManager& memory,u32 addr,AXPBWii& pb);
    void WritePB(Memory::MemoryManager& memory,u32 addr,const AXPBWii& pb);
};
''' + bodies)
    source = public / 'stock_axwii_pb_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(cache / 'shim'), '-I', str(base), '-I', str(public),
        str(source), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS 8192 comparisons;14 refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_PB_REFERENCE_ROUNDTRIP_COMPONENT_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_pb.h', harness, shim, ucode / 'AXWii.cpp', ucode / 'AXStructs.h']},
        'limits': ['Reference ReadPB/WritePB bodies and AXStructs unchanged; bounded big-endian memory fixture adapter supplied.',
            '4096 synthetic blocks; read/modified-write comparisons, untouched canaries and exact roundtrip; no actual live PB captured.',
            'Only4CC52064 profile supported; updates field omitted; no sample decoder/mixer/voice execution.',
            'No game/window launch, input/focus changes or runtime integration.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
