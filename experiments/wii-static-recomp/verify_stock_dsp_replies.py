"""Compare bounded replies with unchanged pinned MailHandler, not physical DSP timing."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
from verify_stock_axwii_schema import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    assert reference['revision'] == 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
    for row in reference['references']:
        assert sha(row['path']) == row['sha256']
    base = args.reference.parent / 'dolphin/Source/Core'
    source_reference = base / 'Core/HW/DSPHLE/MailHandler.cpp'
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-replies-', dir='/private/tmp'))
    files = {
        'Common/CommonTypes.h': '#pragma once\n#include <cstdint>\nusing u16=uint16_t;using u32=uint32_t;\n',
        'Common/ChunkFile.h': '#pragma once\nclass PointerWrap { public:template<class T>void Do(T&) {} };\n',
        'Common/Logging/Log.h': '#pragma once\n#define DEBUG_LOG_FMT(...) ((void)0)\n',
        'Core/HW/DSP.h': '''#pragma once
#include <vector>
namespace DSP {
constexpr unsigned INT_DSP=128;
struct DSPManager {
    std::vector<int> interrupts;
    void GenerateDSPInterruptFromDSPEmu(unsigned interrupt,int delay=0) {
        if(interrupt!=INT_DSP) { throw std::runtime_error("unexpected reference interrupt"); }
        interrupts.push_back(delay);
    }
};
}
'''}
    for name, text in files.items():
        path = cache / 'shim' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    exe = cache / 'probe'
    source = public / 'stock_dsp_replies_probe.cpp'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-I', str(cache / 'shim'),
        '-I', str(base), '-I', str(public), str(source), str(source_reference), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'DSP_REPLIES_REFERENCE_PASS' in run.stdout, run.stdout + run.stderr
    report = {'result': 'DSP_REPLIES_PINNED_REFERENCE_PASS', 'output': run.stdout.strip(),
        'referencePath': str(args.reference), 'referenceSha256': sha(args.reference),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source,
            public / 'stock_dsp_replies.h', source_reference, base / 'Core/HW/DSPHLE/MailHandler.h',
            *(cache / 'shim' / name for name in files)]},
        'limits': ['Unchanged pinned MailHandler.cpp/header; explicit interrupt/log/state fixture adapters.',
            'Ordered mails/IRQ requests/high-low/halted/clear/lastmail behavior compared.',
            '32mail cap/negative-delay refusal are PC adaptations, not physical DSP queue behavior.',
            'Not actual scheduler/PI/register binding or measured original Wii interrupt timing, no runtime audio acceptance.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, run.stdout.strip(), flush=True)


if __name__ == '__main__':
    main()
