"""Compare Wii bank selection and mapped decoding with pinned unchanged reference bodies."""
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
    parser.add_argument('--accelerator-proof', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    proof = json.loads(args.accelerator_proof.read_text())
    assert proof['result'] == 'AXWII_ACCELERATOR_REFERENCE_COMPONENT_PASS'
    for path, digest in proof['dependencies'].items():
        assert sha(path) == digest, path
    base = args.reference.parent / 'dolphin/Source/Core'
    dsp = base / 'Core/HW/DSP.cpp'
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-sample-memory-', dir='/private/tmp'))
    shutil.copytree(args.accelerator_proof.parent / 'shim', cache / 'shim')
    body = function(dsp.read_text(), 'u8 DSPManager::ReadARAM(u32 address) const')
    body = body.replace('u8 DSPManager::ReadARAM', 'uint8_t ReadARAM', 1)
    harness = cache / 'axwii-mapped-reference.h'
    oracle = (args.accelerator_proof.parent / 'axwii-accelerator-reference.h').read_text()
    oracle = oracle.replace('std::span<const uint8_t> memory;', 'ReferenceMemory& memory;')
    oracle = oracle.replace('Oracle(std::span<const uint8_t> bytes,', 'Oracle(ReferenceMemory& bytes,')
    old_read = function(oracle, 'uint8_t ReadMemory(uint32_t address) override')
    oracle = oracle.replace(old_read, 'uint8_t ReadMemory(uint32_t address) override { return memory.ReadARAM(address); }')
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <span>
#include <cstdint>
#include <stdexcept>
using u32=uint32_t;
struct ReferenceMemory {
    struct Memory {
        std::span<const uint8_t> bytes;
        uint32_t mask;
        uint32_t GetRamMask() const { return mask; }
        uint8_t Read_U8(uint32_t address) const { if(address>=bytes.size()) { throw std::runtime_error("fixture bounds"); } return bytes[address]; }
    };
    struct System { Memory memory; const Memory& GetMemory() const { return memory; } } m_system;
    struct Aram { bool wii_mode; const uint8_t* ptr; uint32_t mask; } m_aram;
    ReferenceMemory(std::span<const uint8_t> mem1,std::span<const uint8_t> mem2,uint32_t mask1,uint32_t mask2):
        m_system{{mem1,mask1}},m_aram{true,mem2.data(),mask2} {}
''' + body + '\n};\n' + oracle)
    source = public / 'stock_axwii_sample_memory_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-I', str(cache),
        '-I', str(cache / 'shim'), '-I', str(base), '-I', str(public), str(source),
        str(base / 'Core/DSP/DSPAccelerator.cpp'), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and '131072 addresses;3456 samples;5 refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_SAMPLE_MEMORY_REFERENCE_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference), 'referenceSha256': sha(args.reference),
        'acceleratorProof': str(args.accelerator_proof), 'acceleratorProofSha256': sha(args.accelerator_proof),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source, harness, dsp,
            public / 'stock_axwii_sample_memory.h', public / 'stock_axwii_accelerator.h']},
        'limits': ['Unchanged pinned Wii ReadARAM and DSP decoder; explicit synthetic RAM/System adapters.',
            'Synthetic banks/masks, ADPCM/PCM8/PCM16 addressing and loop state, not actual SHSM samples.',
            'Backed-span bounds/uint64 overflow refusal are PC adaptations; no physical Wii acceptance.',
            'No command executor, runtime integration, original DROM or audible-game acceptance.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
