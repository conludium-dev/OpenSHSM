"""Bound diagnostic data collection before installing it in the current device producer."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import struct
import tempfile
from stock_dsp_capture_patch import adapt


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-capture-contract-', dir='/private/tmp'))
    exe = cache / 'probe'
    source = public / 'stock_dsp_capture_contract.cpp'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-I', str(root / 'window-quantization/include'), '-I', str(public), str(source), '-o', str(exe)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    env = {key: value for key, value in os.environ.items() if key != 'OPENSHSM_DSP_CAPTURE_DIR'}
    runs = {}
    for variant in ('disabled', 'enabled', 'existing-file'):
        directory = cache / variant
        directory.mkdir()
        current_env = dict(env)
        if variant != 'disabled':
            current_env['OPENSHSM_DSP_CAPTURE_DIR'] = str(directory)
        if variant == 'existing-file':
            (directory / 'dsp-events.jsonl').write_bytes(b'preserved\n')
        run = subprocess.run([str(exe)], env=current_env, capture_output=True, text=True, timeout=30)
        (cache / (variant + '-run.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and 'BOUNDED_DSP_CAPTURE_RAM_STATE_PRESERVATION_PASS' in run.stdout
        files = list(directory.iterdir())
        if variant == 'disabled':
            assert not files
        elif variant == 'existing-file':
            assert len(files) == 1 and files[0].read_bytes() == b'preserved\n'
        else:
            rows = [json.loads(line) for line in (directory / 'dsp-events.jsonl').read_text().splitlines()]
            mails = [row for row in rows if row['kind'] == 'mail']
            lists = [row for row in rows if row['kind'] == 'list']
            dma = [row for row in rows if row['kind'] == 'dma-to-aram']
            assert len(mails) == 512 and len(lists) == 256 and len(dma) == 8
            assert not lists[0]['saved'] and lists[0]['capturedBytes'] == 0
            for row in lists[1:]:
                data = (directory / f'dsp-list-{row["index"]:03d}.bin').read_bytes()
                assert row['saved'] and row['capturedBytes'] == 256 and data == bytes(range(256))
            assert dma[0]['truncated'] and dma[0]['capturedBytes'] == 8192
            assert not dma[1]['saved']
            assert (directory / 'dsp-dma-01.bin').read_bytes() == bytes(range(256)) * 32
            assert len(files) == 263 and sum(path.stat().st_size for path in files) < 256 * 1024
        runs[variant] = {'output': run.stdout.strip(), 'files': len(files)}
    dol_path = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    address, size = 0x8043d680, 8192
    section = next(index for index in range(18) if layout[index + 18] <= address
        and address + size <= layout[index + 18] + layout[index + 36])
    offset = layout[section] + address - layout[section + 18]
    firmware = cache / 'private-firmware-fixture.bin'
    firmware.write_bytes(dol[offset:offset + size])
    assert sha(firmware) == 'd6d5952c5e6c55705513d89e58ba12314db23d8758c4acfd2c75b81b7140c0ed'
    for variant in ('pb', 'active', 'unsupported', 'badsize'):
        directory = cache / variant
        directory.mkdir()
        current_env = dict(env, OPENSHSM_DSP_CAPTURE_DIR=str(directory))
        run = subprocess.run([str(exe), str(firmware), variant], env=current_env,
            capture_output=True, text=True, timeout=30)
        (cache / (variant + '-run.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and 'BOUNDED_DSP_CAPTURE_RAM_STATE_PRESERVATION_PASS' in run.stdout, run.stderr
        rows = [json.loads(line) for line in (directory / 'dsp-events.jsonl').read_text().splitlines()]
        firmware_rows = [row for row in rows if row['kind'] == 'firmware-ram-candidate']
        chains = [row for row in rows if row['kind'] == 'pb-chain']
        pbs = [row for row in rows if row['kind'] == 'pb']
        assert len(firmware_rows) == 1
        if variant == 'pb':
            assert firmware_rows[0]['saved'] and firmware_rows[0]['ectorHash'] == 0x4cc52064
            assert (directory / 'dsp-firmware-01.bin').read_bytes() == firmware.read_bytes()
            assert [(row['nodes'], row['stop']) for row in chains] == [(2, 'end'), (2, 'cycle'), (0, 'invalid-ram'), (16, 'limit'), (16, 'limit')]
            assert len(pbs) == 36 and all(row['saved'] and row['capturedBytes'] == 300 for row in pbs)
            for row in pbs:
                data = (directory / f'dsp-pb-{row["job"]:02d}-{row["node"]:02d}.bin').read_bytes()
                assert len(data) == 300 and struct.unpack('>H', data[16:18])[0] == row['running'] == 1
                assert struct.unpack('>I', data[:4])[0] == row['nextAddress']
        elif variant == 'active':
            assert firmware_rows[0]['saved'] and firmware_rows[0]['ectorHash'] == 0x4cc52064
            assert len(chains) == 6 and len(pbs) == 2
            assert [(row['job'], row['nodes'], row['scanned'], row['stop']) for row in chains[:4]] == [(0, 0, 256, 'limit')] * 4
            assert [(row['job'], row['nodes'], row['scanned'], row['stop']) for row in chains[4:]] == [(1, 1, 34, 'end'), (2, 1, 34, 'end')]
            assert all(row['running'] == 1 and row['node'] == 1 for row in pbs)
        else:
            assert not chains and not pbs
            assert firmware_rows[0]['saved'] == (variant == 'unsupported')
        runs[variant] = {'output': run.stdout.strip(), 'files': len(list(directory.iterdir())),
            'pbNodes': len(pbs), 'chains': chains}
    original = root / 'window-adma-deadline/hw_dsp.cpp'
    text = original.read_text()
    patched = adapt(text)
    assert patched.count('reply(') == text.count('reply(')
    assert patched.count('schedule_after(') == text.count('schedule_after(')
    report = {'result': 'BOUNDED_DSP_CAPTURE_COMPONENT_PASS', 'runs': runs,
        'compileCommand': command, 'executableSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), source, original,
            public / 'stock_dsp_capture.h', public / 'stock_dsp_capture_patch.py',
            public / 'stock_axwii_commands.h', public / 'stock_axwii_pb.h', dol_path,
            public / 'stock_quantization_contract.cpp', root / 'window-quantization/include/runtime/cpu_context.h']},
        'limits': ['Synthetic recorder fixtures, not actual original command-list/uCode content or audio playback.',
            'Maximum512mail rows/256list snapshots/8DMA snapshots plus1 firmware,4x16 active PB nodes and4inactive/error summaries; each selected chain scans at most256 nodes, invalidRAM/cycles refuse without device changes.',
            'Declared list units interpreted as16bitword hint, explicitly provisional until actualprotocol verified.',
            'POSIX diagnostic writer; no Windows observer support claimed.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
