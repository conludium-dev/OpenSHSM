"""Diagnose the exact linked mailbox adapter, without claiming a synthetic list is original audio."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    build = json.loads(args.build.read_text())
    assert sha(build['executablePath']) == build['executableSha256']
    archive = Path(build['archivePath'])
    assert sha(archive) == build['archiveSha256']
    dsp_path = root / 'window-adma-deadline/hw_dsp.cpp'
    dsp_record_path = dsp_path.parent / 'build.json'
    dsp_record = json.loads(dsp_record_path.read_text())
    assert sha(dsp_path) == dsp_record['sourceSha256']
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), 'hw_dsp.cpp.o'])
    assert hashlib.sha256(data).hexdigest() == dsp_record['objectSha256']
    text = dsp_path.read_text()
    start = text.index('                    if (s_ax_state == 1) {')
    end = text.index('                if (std::getenv("NWII_DSPTRACE"))', start)
    body = text[start:end]
    assert 'reply(0x0002)' in body and 's_ax_state = 2' in body
    assert 'mmu' not in body and 'read' not in body and 'mix' not in body
    nm = subprocess.check_output(['/usr/bin/nm', '-g', build['executablePath']], text=True)
    assert not any(name in nm for name in ['_AXAcquireVoice', '_AXSetVoiceState', '_AXInit'])
    dol_path = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    def word(address):
        section = next(i for i in range(18) if layout[18 + i] <= address
            and address + 4 <= layout[18 + i] + layout[36 + i])
        return struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    expected_sites = {0x8022e9b4: 0x4bfff4cd, 0x8022e9b8: 0x3c80babe,
        0x8022e9bc: 0x7c7d1b78, 0x8022e9c0: 0x38640080, 0x8022e9c4: 0x4800828d,
        0x8022e9d4: 0x7fa3eb78, 0x8022e9d8: 0x48008279,
        0x80236c50: 0x3c80cc00, 0x80236c54: 0x5460843e, 0x80236c58: 0xb0045000,
        0x80236c5c: 0xb0645002, 0x80236c60: 0x4e800020}
    for address, expected in expected_sites.items():
        assert word(address) == expected
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-mail-', dir='/private/tmp'))
    source = public / 'stock_dsp_mail_probe.cpp'
    obj = cache / 'probe.o'
    exe = cache / 'probe'
    arguments = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    command = list(build['linkCommand'])
    main_obj = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
    command.insert(1, str(obj))
    command[command.index('-o') + 1] = str(exe)
    linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
    (cache / 'link.log').write_text(linked.stdout + linked.stderr)
    assert linked.returncode == 0, linked.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'CURRENT_DSP_MAIL_ACK_WITHOUT_LIST_EXECUTION_REPRODUCED' in run.stdout, (run.returncode, run.stdout, run.stderr)
    report = {'result': 'CURRENT_DSP_MAILBOX_ADAPTER_EXECUTION_GAP_CONFIRMED',
        'buildPath': str(args.build.resolve()), 'buildSha256': sha(args.build),
        'output': run.stdout.strip(), 'linkCommand': command, 'probeSha256': sha(exe),
        'linkedDSPMemberSha256': hashlib.sha256(data).hexdigest(),
        'AXStubSymbolsLinked': False,
        'originalDOLSites': [{'address': f'{address:08X}', 'opcode': f'{value:08X}'}
            for address, value in expected_sites.items()],
        'originalStaticEvidence': 'The original frame code builds a list via8022DE80, sends BABE0080 then its pointer through80236C50; sender stores high/low toCC005000/CC005002.',
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source, dsp_path,
            dsp_record_path, archive, Path(build['executablePath']), dol_path]},
        'limits': ['Synthetic mailbox request illustrates actual adapter gap, not original Wii command-list validity or audio oracle.',
            'Acknowledgment does not decode/mix/execute guest DSP commands; changing HLE AX stubs would not address this linked path.',
            'Live game command-list/uCode identity and dialogue data flow remain unrecorded; no proven sole cause for missing voices.',
            'No game process, original assets, playback clock, mixer or runtime source changed.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
