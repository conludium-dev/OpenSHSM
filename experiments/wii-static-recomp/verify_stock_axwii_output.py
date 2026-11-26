"""Compare output bytes and persistent mixer state to pinned Wii output methods, without opening windows."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import tempfile
from verify_stock_axwii_schema import sha
from verify_stock_paired_estimates import function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--buffers', action='store_true')
    parser.add_argument('--table-proof', type=Path)
    args = parser.parse_args()
    table = None
    if args.table_proof:
        assert args.buffers, '--table-proof requires --buffers'
        proof = json.loads(args.table_proof.read_text())
        assert proof['result'] == 'CAPTURED_AXWII_COMPRESSOR_POINTERS_MAPPED_TO_OWN_DOL'
        for path, digest in proof['dependencies'].items():
            assert sha(path) == digest
        assert len(proof['tables']) == 1
        table = proof['tables'][0]
        assert table['threshold'] == 32768 and table['releaseFrames'] == 10
        assert table['bytes'] == 4032 and table['entries'] == 21
        assert sha(table['path']) == table['sha256']
        dol = Path(__file__).resolve().parents[2] / 'work/private-game/disc/DATA/sys/main.dol'
        assert dol.read_bytes()[table['dolFileOffset']:table['dolFileOffset'] + 4032] == Path(table['path']).read_bytes()
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    base = args.reference.parent / 'dolphin/Source/Core/Core/HW/DSPHLE/UCodes'
    source_reference = base / 'AXWii.cpp'
    voice = base / 'AXVoice.h'
    ucodes = base / 'UCodes.h'
    constants = '\n'.join(re.findall(r'  static constexpr u32 (?:TASK_MAIL_TO_CPU|DSP_SYNC) = .*?;', ucodes.read_text()))
    assert "TASK_MAIL_TO_CPU = 0xDCD1'0000" in constants and 'DSP_SYNC = TASK_MAIL_TO_CPU | 0x0004' in constants
    text = source_reference.read_text()
    bodies = '\n'.join(function(text, signature) for signature in (
        'void AXWiiUCode::GenerateVolumeRamp(', 'void AXWiiUCode::OutputSamples(', 'void AXWiiUCode::OutputWMSamples('))
    template = ''
    if args.buffers:
        bodies += '\n' + '\n'.join(function(text, signature) for signature in (
            'void AXWiiUCode::SetupProcessing(', 'void AXWiiUCode::AddToLR(', 'void AXWiiUCode::AddSubToLR('))
        template = 'struct BufferDesc { int* ptr; int samples_per_milli; };\n'
        template += 'template <int Millis, size_t BufCount>\n' + function((base / 'AX.h').read_text(), 'void InitMixingBuffers(')
        bodies += '\n' + function((base / 'AX.cpp').read_text(), 'void AXUCode::RunCompressor(')
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-output-', dir='/private/tmp'))
    names = ['main_left', 'main_right', 'main_surround', 'auxA_left', 'auxA_right', 'auxA_surround',
        'auxB_left', 'auxB_right', 'auxB_surround', 'auxC_left', 'auxC_right', 'auxC_surround']
    fields = '\n'.join(f'    int* m_samples_{name}=main[{index}].data();' for index, name in enumerate(names))
    fields += '\n' + '\n'.join(f'    int* m_samples_wm{index}=remote[{index * 2}].data();' for index in range(4))
    fields += '\n' + '\n'.join(f'    int* m_samples_aux{index}=remote[{index * 2 + 1}].data();' for index in range(4))
    harness = cache / 'axwii-output-reference.h'
    harness.write_text('''// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <vector>
#include <cstring>
#include <algorithm>
#include <stdexcept>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s16=int16_t;using s32=int32_t;using s64=int64_t;
namespace Common {
inline u16 swap16(u16 value) { return u16(value>>8|value<<8); }
inline u32 swap32(u32 value) { return __builtin_bswap32(value); }
}
''' + function(voice.read_text(), 's16 ClampS16(') + '''
struct Memory {
    alignas(16) std::array<uint8_t,4096> bytes;
    std::vector<uint32_t>* events;
    explicit Memory(std::vector<uint32_t>* sink):events(sink) { bytes.fill(0xa5); }
    uint8_t* GetPointerForRange(u32 address,size_t size) {
        if(uint64_t(address)+size>bytes.size()) { throw std::runtime_error("Reference fixture bounds"); }
        events->push_back(address);
        return bytes.data()+address;
    }
    template<class T> void CopyToEmuSwapped(u32 address,const T* source,size_t size) {
        auto* destination=GetPointerForRange(address,size);
        for(size_t index=0;index<size/sizeof(T);++index) {
            for(size_t byte=0;byte<sizeof(T);++byte) {
                destination[index*sizeof(T)+byte]=uint8_t(uint64_t(source[index])>>((sizeof(T)-1-byte)*8));
            }
        }
    }
    void CopyToEmu(u32 address,const void* source,size_t size) {
        std::memcpy(GetPointerForRange(address,size),source,size);
    }
    void CopyFromEmuSwapped(u16* destination,u32 address,size_t size) {
        const auto* source=GetPointerForRange(address,size);
        for(size_t index=0;index<size/2;++index) {
            destination[index]=u16(u16(source[index*2])<<8|source[index*2+1]);
        }
    }
};
struct System {
    Memory memory;
    explicit System(std::vector<u32>* events):memory(events) {}
    System& GetSystem() { return *this; }
    Memory& GetMemory() { return memory; }
};
struct MailHandler {
    std::vector<u32>* events;
    void PushMail(u32 value,bool irq) {
        if(!irq) { throw std::runtime_error("Reference expected sync IRQ"); }
        events->push_back(value);
    }
};
class AXWiiUCode {
public:
    std::vector<u32> events;
    System system{&events};
    System* m_dsphle=&system;
    MailHandler m_mail_handler{&events};
    openshsm::experiment::AxWiiMainBuffers main{};
    openshsm::experiment::AxWiiRemoteBuffers remote{};
    u16 m_last_main_volume=0;
    u16 m_compressor_pos=0;
''' + fields + '\n' + constants + '\n' + template + '''
    void SetupProcessing(u32 address);
    void AddToLR(u32 address,bool neg);
    void AddSubToLR(u32 address);
    void RunCompressor(u16 threshold,u16 release_frames,u32 table_addr,u32 millis);
    void GenerateVolumeRamp(u16* output,u16 vol1,u16 vol2,size_t nvals);
    void OutputSamples(u32 lr_addr,u32 surround_addr,u16 volume,bool upload_auxc);
    void OutputWMSamples(u32* addresses);
};
using AXUCode=AXWiiUCode;
''' + bodies)
    source = public / ('stock_axwii_buffers_probe.cpp' if args.buffers else 'stock_axwii_output_probe.cpp')
    exe = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(cache), '-I', str(public), str(source), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe), *([table['path']] if table else [])], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    expected = 'PASS 12288 cases;16384 compressor frames;10 transactional refusals' if args.buffers else 'PASS 4096 cases;reference write-before-sync order;15 transactional refusals'
    if table:
        expected = 'PASS 12288 cases;65536 compressor frames;10 transactional refusals'
    assert run.returncode == 0 and expected in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_BUFFERS_REFERENCE_PASS' if args.buffers else 'AXWII_OUTPUT_PACKING_REFERENCE_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference.resolve()), 'referenceSha256': sha(args.reference),
        'compileCommand': command, 'probeSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_axwii_output.h', public / 'stock_axwii_buffers.h', public / 'stock_axwii_voice_mix.h',
            public / 'stock_axwii_filters.h', public / 'stock_axwii_pb.h',
            public / 'stock_axwii_resample.h', public / 'stock_axwii_remote_mix.h',
            harness, source_reference, voice, ucodes, base / 'AX.h', base / 'AX.cpp']},
        'limits': ['Untouched pinned ramp/OutputSamples/OutputWMSamples bodies; supplied bounded memory/byte-swap/System/mail fixture adapters.',
            '4096 synthetic fullsigned32 buffers/volumes compare right-left BE stereo, signed32 surround/optionalauxC,4WMmain outputs and mutated LR/volume state.',
            'Candidate WM/main commits compare all4096 fixture RAM bytes and buffer/volume state at DCD10004 callback; overlap write order and15 transactional bad-span/address refusals checked.',
            'Bounded RAM resolver and noexcept signal callback are explicit fixture adapters, not actual CPUContext mapping/PI IRQ execution.',
            'No real SHSM PCM/DSP command/ADMA integration or audible/physical Wii acceptance; no game/window/currentprocess changes.']}
    if args.buffers:
        report['limits'] = ['Untouched pinned InitMixingBuffers/SetupProcessing/AddToLR/AddSubToLR/RunCompressor; explicit bounded memory/endian/System fixtures and inherited class alias.',
            '4096 synthetic setup records compare all20 buffers and12288 add/sub/separate LR operations; reference signed arithmetic kept in defined range.',
            '16384 sequential compressor frames compare full main buffers and persistent position using synthetic ramps;10 candidate-only malformed/overflow refusals preserve state. Original overflow behavior unresolved, candidate fails closed.',
            'No actual SHSM setup/input/PB/memory mapping/command runtime integration or audible/physical Wii acceptance; no windows.']
    if table:
        report['compressorTableProofPath'] = str(args.table_proof.resolve())
        report['compressorTableProofSha256'] = sha(args.table_proof)
        report['compressorTableSha256'] = table['sha256']
        report['limits'][2] = '65536 sequential compressor frames with own-DOL coefficients and captured threshold/release compare buffers/state; synthetic PCM and initial positions, not real voice execution. Full release and retrigger tested;10 malformed/overflow refusals preserve state.'
        report['limits'].append('Static DOL table is not a live RAM table snapshot; runtime modification and original DSP/hardware acceptance remain unverified.')
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
