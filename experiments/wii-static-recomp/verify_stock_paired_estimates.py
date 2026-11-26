"""Compare actual CPU adapter with pinned, untouched Dolphin paired/helper bodies."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from stock_paired_estimate_patch import adapt


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.reference.read_text())
    assert manifest['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    assert manifest['result'] == 'PINNED_DOLPHIN_NUMERIC_ESTIMATE_REFERENCE_EXECUTED'
    for path, digest in manifest['dependencies'].items():
        assert sha(Path(path)) == digest, path
    for row in manifest['references']:
        assert sha(Path(row['path'])) == row['sha256']
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-paired-component-', dir='/private/tmp'))
    dolphin = args.reference.parent / 'dolphin/Source/Core'
    helpers = (dolphin / 'Core/PowerPC/Interpreter/Interpreter_FPUtils.h').read_text()
    paired = (dolphin / 'Core/PowerPC/Interpreter/Interpreter_Paired.cpp').read_text()
    state = (dolphin / 'Core/PowerPC/PowerPC.h').read_text()
    reference = '''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include "Common/FloatUtils.h"
#include <array>
constexpr uint32_t FPSCR_ZX = 0x04000000, FPSCR_VXSNAN = 0x01000000, FPSCR_VXSQRT = 0x200;
constexpr uint32_t FPSCR_VX_ANY = 0x01f80700, FPSCR_ANY_E = 0xf8;
union UReg_FPSCR {
    uint32_t Hex;
    struct { uint32_t RN:2, NI:1, XE:1, ZE:1, UE:1, OE:1, VE:1, VXCVI:1,
        VXSQRT:1, VXSOFT:1, reserved:1, FPRF:5, FI:1, FR:1, VXVC:1, VXIMZ:1,
        VXZDZ:1, VXIDI:1, VXISI:1, VXSNAN:1, XX:1, ZX:1, UX:1, OX:1, VX:1, FEX:1, FX:1; };
    void ClearFIFR() { FI = 0; FR = 0; }
};
struct Pair {
    double a = 0, b = 0;
    double PS0AsDouble() const { return a; }
    double PS1AsDouble() const { return b; }
    void SetBoth(double first, double second) { a = first; b = second; }
};
struct ReferenceCR {
    unsigned field = 0;
    void SetField(unsigned index, unsigned value) { if (index != 1) { throw std::runtime_error("CR"); } field = value; }
};
namespace PowerPC {
struct PowerPCState {
    UReg_FPSCR fpscr{};
    union { uint32_t Hex; struct { uint32_t low:8, FE1:1, middle:2, FE0:1, high:20; }; } msr{};
    std::array<Pair, 32> ps;
    ReferenceCR cr;
    bool program_exception = false;
    void UpdateFPRFSingle(float value) { fpscr.FPRF = Common::ClassifyFloat(value); }
'''
    reference += function(state, '  void UpdateCR1()')
    reference += '''}; }
enum class ProgramExceptionCause { FloatingPoint };
void GenerateProgramException(PowerPC::PowerPCState& state, ProgramExceptionCause) { state.program_exception = true; }
struct { bool bFlushToZero = false; } cpu_info;
'''
    for signature in ('inline void CheckFPExceptions(', 'inline void UpdateFPExceptionSummary(',
            'inline void SetFPException(', 'inline float ForceSingle('):
        reference += function(helpers, signature)
    reference += '''struct UGeckoInstruction { unsigned FD, FB; bool Rc; };
struct Interpreter {
    PowerPC::PowerPCState m_ppc_state;
    static void ps_res(Interpreter&, UGeckoInstruction);
    static void ps_rsqrte(Interpreter&, UGeckoInstruction);
};
'''
    reference += function(paired, 'void Interpreter::ps_res(')
    reference += function(paired, 'void Interpreter::ps_rsqrte(')
    header = cache / 'paired-reference.h'
    header.write_text(reference)
    source = public / 'stock_paired_estimate_contract.cpp'
    exe = cache / 'contract'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-frounding-math', '-fno-fast-math', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(root / 'window-quantization/include'), '-I', str(public), '-I', str(cache),
        '-I', str(args.reference.parent / 'shim'), '-I', str(dolphin), str(source),
        str(dolphin / 'Common/FloatUtils.cpp'), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    corpus = args.reference.parent / 'estimate-bits.txt'
    run = subprocess.run([str(exe), str(corpus)], capture_output=True, text=True, timeout=60)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'PAIRED_ESTIMATE_COMPONENT_PASS' in run.stdout
    original = root / 'window-fp-guard/output_8.cpp'
    record_path = original.with_suffix('.cpp.record.json')
    record = json.loads(record_path.read_text())
    assert sha(original) == record['sourceSha256'] and sha(Path(record['object'])) == record['objectSha256']
    dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    patched, sites = adapt(original.read_text(), dol_path.read_bytes())
    assert {0x80071168, 0x8007116c}.issubset({site['address'] for site in sites})
    (cache / 'output_8.cpp').write_text(patched)
    changed = bytearray(dol_path.read_bytes())
    import struct
    layout = struct.unpack('>64I', changed[:256])
    site = sites[0]['address']
    index = next(i for i in range(18) if layout[18 + i] <= site < layout[18 + i] + layout[36 + i])
    offset = layout[index] + site - layout[18 + index]
    changed[offset] ^= 1
    try:
        adapt(original.read_text(), changed)
    except AssertionError:
        pass
    else:
        raise AssertionError('Changed original opcode must reject lowering')
    paths = [Path(__file__).resolve(), args.reference, source, header, corpus, exe,
        public / 'stock_paired_estimates.h', public / 'stock_paired_estimate_patch.py',
        public / 'stock_quantization_contract.cpp', root / 'window-quantization/include/runtime/cpu_context.h',
        original, record_path, dol_path, cache / 'output_8.cpp']
    report = {'result': 'PAIRED_ESTIMATE_CPU_COMPONENT_DOL_LOWERING_PASS', 'output': run.stdout.strip(),
        'referenceRevision': manifest['revision'], 'sites': sites, 'command': command,
        'dependencies': {str(path): sha(path) for path in paths},
        'limits': ['Pinned untouched Dolphin paired/helper bodies on a minimal state shim, not Wii hardware.',
            'Actual retained CPUContext tested for lanes/alias/FPSCR/CR1/NI/RN/host-round restoration.',
            'Enabled FP program delivery fails closed; exact Wii exception routing is not implemented.',
            'Pre-instruction guards retained by lowering; their separate prior tests are not rerun here.',
            'Original unit is not replaced; lowered private unit not compiled/linked/live-verified yet.',
            'No persistent saving, game transition or full crash fix acceptance.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
