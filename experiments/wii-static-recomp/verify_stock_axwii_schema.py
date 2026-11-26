"""Compare command routing against an untouched pinned dispatcher with observation-only method sinks."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
from verify_stock_paired_estimates import function


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['result'] == 'PINNED_AXWII_SCHEMA_REFERENCE_READY_NOT_RUNTIME_CODE'
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    evidence = json.loads(args.evidence.read_text())
    assert evidence['staticDOLFirmwareCandidate']['ectorHash'] == '4CC52064'
    public = Path(__file__).resolve().parent
    base = args.reference.parent / 'dolphin/Source/Core'
    ucode = base / 'Core/HW/DSPHLE/UCodes'
    cpp = (ucode / 'AXWii.cpp').read_text()
    hpp = (ucode / 'AXWii.h').read_text()
    assert 'm_new_filter = crc == 0x347112ba || crc == 0x4cc52064;' in cpp
    assert 'm_old_axwii = crc == 0xfa450138 || crc == 0x7699af32;' in cpp
    assert 'size * sizeof(u16)' in (ucode / 'AX.cpp').read_text()
    enums = ''.join(re.findall(r'  enum CmdType(?:Old)?\s*\{.*?\n  };', hpp, re.S))
    assert 'CMD_PROCESS = 0x04' in enums and 'CMD_END = 0x0E' in enums
    body = function(cpp, 'void AXWiiUCode::HandleCommandList()')
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-schema-', dir='/private/tmp'))
    shim = cache / 'shim/Common/CommonTypes.h'
    shim.parent.mkdir(parents=True)
    shim.write_text('#pragma once\n#include <cstdint>\nusing u8=uint8_t;using u16=uint16_t;'
        'using u32=uint32_t;using s16=int16_t;using s32=int32_t;\n')
    harness = cache / 'axwii-command-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdint>
#include <vector>
using u16=uint16_t; using u32=uint32_t;
#define HILO_TO_32(name) ((u32(name##_hi)<<16)|name##_lo)
struct SpyCall { u16 opcode; std::vector<u32> values; bool operator==(const SpyCall&) const = default; };
class AXWiiUCode {
public:
  bool m_old_axwii=false;
  u32 m_crc=0x4cc52064;
  std::vector<u16> m_cmdlist;
  std::vector<SpyCall> calls;
  void HandleCommandList();
  void SetupProcessing(u32 a) { calls.push_back({0,{a}}); }
  void AddToLR(u32 a,bool neg) { calls.push_back({u16(neg?2:1),{a}}); }
  void AddSubToLR(u32 a) { calls.push_back({3,{a}}); }
  void ProcessPBList(u32 a) { calls.push_back({4,{a}}); }
  void MixAUXSamples(int id,u32 a,u32 b,u16 v) { calls.push_back({u16(5+id),{v,a,b}}); }
  void UploadAUXMixLRSC(bool second,u32* a,u16 v) { calls.push_back({u16(second?9:8),{v,a[0],a[1],a[2],a[3],a[4],a[5]}}); }
  void RunCompressor(u16 t,u16 f,u32 a,u32 ms) { calls.push_back({10,{t,f,a,ms}}); }
  void OutputSamples(u32 lr,u32 s,u16 v,bool dpl2) { calls.push_back({u16(dpl2?12:11),{v,s,lr}}); }
  void OutputWMSamples(u32* a) { calls.push_back({13,{a[0],a[1],a[2],a[3]}}); }
''' + enums + '\n};\n' + body)
    inputs = []
    for row in evidence['snapshots']:
        if row['kind'] == 'list':
            assert sha(row['path']) == row['sha256']
            inputs.append(row['path'])
    widths = [2, 2, 2, 2, 2, 5, 5, 5, 13, 13, 4, 5, 5, 8]
    for opcode, count in enumerate(widths):
        words = [opcode, *(opcode * 100 + index for index in range(count)), 14, 0xffff]
        path = cache / f'synthetic-{opcode:02d}.bin'
        path.write_bytes(struct.pack('>' + 'H' * len(words), *words))
        inputs.append(str(path))
    source = public / 'stock_axwii_schema_probe.cpp'
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(cache / 'shim'), '-I', str(base), '-I', str(public),
        str(source), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe), *inputs], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'AXWII_COMMAND_SCHEMA_COMPONENT_PASS' in run.stdout, (run.returncode, run.stdout, run.stderr)
    layout = list(map(int, re.search(r'^PB_LAYOUT (.*)$', run.stdout, re.M)[1].split()))
    assert len(layout) == 8
    names = ['largestStructBytes', 'updatesOffset', 'updatesBytes', 'runningOffset',
        'audioAddressOffset', 'adpcmOffset', 'sampleRateOffset', 'volumeEnvelopeOffset']
    offsets = dict(zip(names, layout))
    offsets['variantWireBytes'] = layout[0] - layout[2]
    for field in ('audioAddressOffset', 'adpcmOffset', 'sampleRateOffset', 'volumeEnvelopeOffset'):
        offsets[field.replace('Offset', 'WireOffset')] = offsets[field] - layout[2]
    report = {'result': 'AXWII_4CC_COMMAND_ROUTING_PB_LAYOUT_COMPONENT_PASS',
        'output': run.stdout.strip(), 'realCapturedLists': len(inputs) - 14, 'syntheticCommandFamilies': 14,
        'pbLayout': offsets, 'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'evidencePath': str(args.evidence.resolve()), 'evidenceSha256': sha(args.evidence),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_commands.h', harness, shim, ucode / 'AXWii.cpp', ucode / 'AXWii.h', ucode / 'AXStructs.h']},
        'limits': ['Unmodified pinned dispatcher body/enum with observation-only method sinks: command routing, NOT voice/mixer execution.',
            'Real captured SHSM command byte order/argument boundaries match reference; malformed lists tested only on bounded candidate.',
            'PB layout measured from unmodified reference struct; actual live PB data and originalDSP/PCM behavior still unverified.',
            '4CC profile is newAXWii/newfilter/withoutupdates; do not reuse olderWii/GameCube format.',
            'No game windows started, focus/input/currentprocess changed or runtime mixer installed.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
