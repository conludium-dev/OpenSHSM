"""Join actual pinned sample accelerator and GetInputSamples/SRC for a windowless voice input oracle."""
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
    parser.add_argument('--accelerator-proof', type=Path, required=True)
    parser.add_argument('--resample-proof', type=Path, required=True)
    args = parser.parse_args()
    proofs = {}
    for name, path, result in [('accelerator', args.accelerator_proof, 'AXWII_ACCELERATOR_REFERENCE_COMPONENT_PASS'),
            ('resample', args.resample_proof, 'AXWII_RESAMPLE_REFERENCE_COMPONENT_PASS')]:
        proof = json.loads(path.read_text())
        assert proof['result'] == result
        for file, digest in proof['dependencies'].items():
            assert sha(file) == digest, file
        reference_path = Path(proof['referencePath'])
        assert sha(reference_path) == proof['referenceSha256']
        reference = json.loads(reference_path.read_text())
        assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
        for row in reference['references']:
            assert sha(row['path']) == row['sha256']
        proofs[name] = proof
    base = Path(proofs['accelerator']['referencePath']).parent / 'dolphin/Source/Core'
    voice = base / 'Core/HW/DSPHLE/UCodes/AXVoice.h'
    other_voice = Path(proofs['resample']['referencePath']).parent / 'dolphin/Source/Core/Core/HW/DSPHLE/UCodes/AXVoice.h'
    assert sha(voice) == sha(other_voice)
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-voice-input-', dir='/private/tmp'))
    shutil.copytree(args.accelerator_proof.parent / 'shim', cache / 'shim')
    shutil.copy2(args.accelerator_proof.parent / 'axwii-accelerator-reference.h', cache / 'axwii-accelerator-reference.h')
    shutil.copy2(args.resample_proof.parent / 'axwii-resample-reference.h', cache / 'axwii-resample-reference.h')
    bodies = '\n'.join(function(voice.read_text(), signature) for signature in (
        'void AcceleratorSetup(', 'u16 AcceleratorGetSample(', 'void GetInputSamples('))
    harness = cache / 'axwii-voice-input-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include "axwii-accelerator-reference.h"
#include "axwii-resample-reference.h"
using HLEAccelerator=Oracle;
#define PB_TYPE AXPBWii
#define HILO_TO_32(name) ((u32(name##_hi)<<16)|name##_lo)
''' + bodies)
    source = public / 'stock_axwii_voice_input_probe.cpp'
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
    assert run.returncode == 0 and 'PASS 18432 jobs;5 transactional refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_VOICE_INPUT_REFERENCE_CHAIN_PASS', 'output': run.stdout.strip(),
        'compileCommand': command, 'probeSha256': sha(exe),
        'parentProofs': {str(path): sha(path) for path in [args.accelerator_proof, args.resample_proof]},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_voice_input.h', public / 'stock_axwii_pb.h',
            public / 'stock_axwii_accelerator.h', public / 'stock_axwii_resample.h', harness, voice,
            *(path for path in cache.rglob('*') if path.is_file() and path.suffix == '.h')]},
        'limits': ['Unmodified reference GetInputSamples/AcceleratorSetup/GetSample/SRC/accelerator/loop callback; previous explicit fixture adapters retained.',
            '18432 synthetic96-sample input jobs (paired consecutive updates) compare samples and entire310byte expanded PB.',
            'All3 sample formats/all3 SRC modes plus absent-bank fallback/4banks/nonloop-loop-stream; bounded coef_select/refusal is candidate adaptation.',
            'Input stage only: no envelope/filter/mixer/output job/ACK or real SHSM PB/sample evidence.',
            'No original DSP DROM table/Wii sample-address mapping or audible dialogue acceptance; not integrated into runtime.',
            'No game/window/input/focus/current-process changes.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
