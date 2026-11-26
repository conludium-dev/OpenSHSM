"""Real native snapshot persistence across independent processes, with synthetic data only."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = Path(__file__).resolve().parent
    cache = Path(tempfile.mkdtemp(prefix='openshsm-nand-storage-', dir='/private/tmp'))
    source = public / 'stock_nand_storage_contract.cpp'
    exe = cache / 'contract-build-a'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-I', str(public), str(source), '-o', str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    replacement = cache / 'another-build/contract-build-b'
    replacement.parent.mkdir()
    shutil.copyfile(exe, replacement)
    replacement.chmod(0o700)
    records = []
    def run(program, mode, directory, expected):
        result = subprocess.run([str(program), mode, str(directory)], capture_output=True, text=True, timeout=25)
        (cache / (mode + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and expected in result.stdout, (mode, result.returncode, result.stdout, result.stderr)
        records.append({'mode': mode, 'output': result.stdout.strip()})
    saved = cache / 'stable-user-data/nand/R5WEA4'
    run(exe, 'write', saved, 'SYNTHETIC_NAND_DURABLE_WRITE')
    run(replacement, 'read', saved, 'SYNTHETIC_NAND_FRESH_PROCESS_RELOAD')
    run(exe, 'contracts', cache / 'contracts/nand/R5WEA4', 'NAND_STORAGE_COMPONENT_PASS')
    holder = subprocess.Popen([str(exe), 'hold', str(saved)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'LOCKED'
        run(replacement, 'locked', saved, 'SECOND_WRITER_REFUSED')
        holder.communicate(timeout=20)
        assert holder.returncode == 0
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.communicate(timeout=5)
    paths = [Path(__file__).resolve(), source, public / 'stock_nand_snapshot.h', public / 'stock_nand_storage.h',
        exe, replacement, saved / 'nand.bin']
    report = {'result': 'NAND_NATIVE_STORAGE_FRESH_PROCESS_COMPONENT_PASS', 'records': records,
        'command': command, 'dependencies': {str(path): sha(path) for path in paths},
        'limits': ['Synthetic registry bytes, not a live SHSM profile or story checkpoint.',
            'Original FS backend is not wired to storage yet; current user game still uses RAM only.',
            'POSIX implementation tested on macOS only; Windows storage deliberately fails closed and remains pending.',
            'Actual disk-full/rename/fsync interruption and game save/reload integration still pending.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
