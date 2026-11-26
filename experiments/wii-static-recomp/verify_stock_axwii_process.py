"""Execute unchanged pinned ProcessPBList with declared bounded fixture services."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from verify_stock_axwii_schema import sha
from verify_stock_paired_estimates import function


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--voice-proof', type=Path, required=True)
    args = parser.parse_args()
    proof = json.loads(args.voice_proof.read_text())
    assert proof['result'] == 'AXWII_FULL_VOICE_REFERENCE_PASS'
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest, file
    reference_path = Path(proof['referencePath'])
    assert sha(reference_path) == proof['referenceSha256']
    reference = json.loads(reference_path.read_text())
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    base = reference_path.parent / 'dolphin/Source/Core'
    wii = base / 'Core/HW/DSPHLE/UCodes/AXWii.cpp'
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-process-', dir='/private/tmp'))
    shutil.copytree(args.voice_proof.parent / 'shim', cache / 'shim')
    for name in ('axwii-voice-input-reference.h', 'axwii-accelerator-reference.h', 'axwii-resample-reference.h'):
        shutil.copy2(args.voice_proof.parent / name, cache / name)
    full = (args.voice_proof.parent / 'axwii-full-voice-reference.h').read_text().replace('AXWiiUCode', 'MaskReference')
    bodies = '\n'.join(function(wii.read_text(), signature) for signature in (
        'void AXWiiUCode::ReadPB(', 'void AXWiiUCode::WritePB(', 'void AXWiiUCode::ProcessPBList(',
        'void AXWiiUCode::GenerateVolumeRamp(', 'void AXWiiUCode::OutputSamples(',
        'void AXWiiUCode::OutputWMSamples(', 'void AXWiiUCode::MixAUXSamples(',
        'void AXWiiUCode::UploadAUXMixLRSC('))
    names = list(dict.fromkeys(re.findall(r'm_samples_[a-zA-Z0-9_]+', bodies)))
    assert len(names) == 20
    fields = '\n'.join(f'int* {name} = {"main" if index < 12 else "remote"}[{index if index < 12 else index - 12}].data();'
        for index, name in enumerate(names))
    harness = cache / 'axwii-chain-reference.h'
    harness.write_text(full + '''
#include <memory>
using namespace DSP::HLE;
namespace Common { inline u16 swap16(u16 value) { return u16(value>>8|value<<8); } inline u32 swap32(u32 value) { return __builtin_bswap32(value); } }
constexpr u32 DSP_SYNC=0xdcd10004;
namespace Memory {
struct MemoryManager {
    std::array<u8,8192> bytes{};
    template<class T> void CopyFromEmuSwapped(T* dst,u32 address,size_t size) {
        if(uint64_t(address)+size>bytes.size()) { throw std::runtime_error("fixture bounds"); }
        for(size_t i=0;i<size/sizeof(T);++i) { uint64_t word=0;for(size_t j=0;j<sizeof(T);++j) { word=(word<<8)|bytes[address+i*sizeof(T)+j]; } T value=T(word);std::memcpy(reinterpret_cast<char*>(dst)+i*sizeof(T),&value,sizeof(T)); }
    }
    template<class T> void CopyToEmuSwapped(u32 address,const T* src,size_t size) {
        if(uint64_t(address)+size>bytes.size()) { throw std::runtime_error("fixture bounds"); }
        for(size_t i=0;i<size/sizeof(T);++i) { for(size_t j=0;j<sizeof(T);++j) { bytes[address+i*sizeof(T)+j]=u8(uint64_t(src[i])>>((sizeof(T)-1-j)*8)); } }
    }
    u8* GetPointerForRange(u32 address,size_t size) { if(uint64_t(address)+size>bytes.size()) { throw std::runtime_error("fixture bounds"); } return bytes.data()+address; }
    void CopyToEmu(u32 address,const void* src,size_t size) { std::memcpy(GetPointerForRange(address,size),src,size); }
};
}
struct ChainSystem { Memory::MemoryManager& memory; Memory::MemoryManager& GetMemory() { return memory; } };
struct ChainDSP { ChainSystem system; ChainSystem& GetSystem() { return system; } };
class AXWiiUCode : public MaskReference {
public:
    Memory::MemoryManager memory;
    openshsm::experiment::AxWiiMainBuffers main{};
    openshsm::experiment::AxWiiRemoteBuffers remote{};
    u32 m_crc=0x4cc52064;
    u16 m_last_main_volume=0;
    std::array<u16,3> m_last_aux_volumes{};
    std::vector<u32> signals;
    struct Mail { std::vector<u32>& signals; void PushMail(u32 value,bool irq) { if(!irq) { throw std::runtime_error("expected IRQ"); } signals.push_back(value); } } m_mail_handler{signals};
    bool m_old_axwii=false,m_new_filter=true,m_coeffs_checksum=false;
    std::array<s16,2048> m_coeffs{};
    std::unique_ptr<Oracle> m_accelerator;
    ChainDSP dsp{{memory}};
    ChainDSP* m_dsphle=&dsp;
''' + fields + '''
    AXWiiUCode(std::span<const uint8_t> samples):m_accelerator(std::make_unique<Oracle>(samples,openshsm::experiment::AxWiiSampleState{})) {}
    void ReadPB(Memory::MemoryManager&,u32,AXPBWii&);
    void WritePB(Memory::MemoryManager&,u32,const AXPBWii&);
    void ProcessPBList(u32);
    static void GenerateVolumeRamp(u16*,u16,u16,size_t);
    void OutputSamples(u32,u32,u16,bool);
    void OutputWMSamples(u32*);
    void MixAUXSamples(int,u32,u32,u16);
    void UploadAUXMixLRSC(int,u32*,u16);
    PBUpdateData LoadPBUpdates(Memory::MemoryManager&,AXPBWii&) { throw std::runtime_error("old variant outside fixture scope"); }
    void ApplyUpdatesForMs(int,AXPBWii&,const u16*,PBUpdateData) { throw std::runtime_error("old variant outside fixture scope"); }
};
''' + bodies)
    source = public / 'stock_axwii_process_probe.cpp'
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
    assert run.returncode == 0 and 'PASS 512 chains;6 guarded refusals;256 output programs;2 program refusals;5120 aux jobs;10 aux refusals' in run.stdout, run.stdout + run.stderr
    report = {'result': 'AXWII_PB_CHAIN_REFERENCE_PASS', 'output': run.stdout.strip(),
        'voiceProofPath': str(args.voice_proof), 'voiceProofSha256': sha(args.voice_proof),
        'referencePath': str(reference_path), 'referenceSha256': sha(reference_path),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source, harness, wii,
            public / 'stock_axwii_process.h', public / 'stock_axwii_voice.h', public / 'stock_axwii_execute.h',
            public / 'stock_axwii_commands.h', public / 'stock_axwii_buffers.h', public / 'stock_axwii_output.h', public / 'stock_axwii_aux.h',
            *(path for path in cache.rglob('*') if path.is_file() and path.suffix == '.h')]},
        'limits': ['Unchanged pinned ProcessPBList/ReadPB/WritePB and full voice algorithms, profile4CC only.',
            'Explicit bounded RAM/System/accelerator adapters; unreachable old-update services refuse.',
            'Per-node writes/buffer commits in original order; later failure retains prior successful nodes, not global rollback.',
            '256node/cycle/alignment guards are PC safety adaptations, not physicalWii behavior.',
            '256 joined PROCESS/WM_OUTPUT/OUTPUT or DPL2/END programs compare whole RAM/buffers/volume/sync with pinned routines.',
            'SETUP/LR/COMPRESSOR dispatch reuses prior component algorithms but joined-reference coverage is pending.',
            '5120 auxiliary jobs compare unchanged MixAUXSamples/UploadAUXMixLRSC, half through command dispatch, includes upload/read aliases and persistent ramps.',
            '2 malformed programs and10 malformed auxiliary inputs refuse before mutation. Arithmetic-overflow refusal after uploads is not whole-RAM rollback.',
            'Synthetic1..16node/fourframe fixtures; no actual sample data/DROM/mail/IRQ/runtime/audio acceptance.']}
    output = cache / 'verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
