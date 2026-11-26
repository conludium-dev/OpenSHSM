"""Check desktop QTE input state without starting a game or input devices."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(args):
    public = Path(__file__).resolve().parent
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise ValueError('Use a fresh output directory')
    compiler = shutil.which(args.compiler)
    if compiler is None:
        raise ValueError('C++ compiler not found')
    oracle = args.ps2_oracle.resolve(strict=True) if args.ps2_oracle else None
    output.mkdir(parents=True)
    source = public / 'stock_desktop_qte_probe.cpp'
    header = public / 'stock_desktop_qte.h'
    flags = ['-std=c++20', '-Wall', '-Wextra', '-Werror']
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    commands = [[compiler, *flags, '-I', str(public), str(source), '-o', str(output / 'probe')],
        [str(output / 'probe'), *([str(oracle)] if oracle else [])]]
    executions = []
    for i, command in enumerate(commands):
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        log = output / f'{i}.log'
        log.write_text(result.stdout + result.stderr)
        executions.append({'command': command, 'exitCode': result.returncode, 'logSha256': sha(log)})
        (output / 'execution.json').write_text(json.dumps(executions, indent=2) + '\n')
        assert result.returncode == 0, result.stdout + result.stderr
    assert 'DESKTOP_QTE_EDGES_FOCUS_GENERATION_ACK_TIMEOUT_WRAP_PASS cases=1024' in result.stdout
    negative = output / 'negative'
    negative.mkdir()
    mutant = header.read_text().replace('if ((pressed & ~correct) != 0)', 'if ((pressed & ~correct) != 0 && false)')
    assert mutant != header.read_text()
    (negative / header.name).write_text(mutant)
    shutil.copy2(public / 'stock_desktop_look.h', negative / 'stock_desktop_look.h')
    shutil.copy2(source, negative / source.name)
    command = [compiler, *flags, '-I', str(negative), str(negative / source.name), '-o', str(negative / 'probe')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (negative / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(negative / 'probe')], capture_output=True, text=True, timeout=60)
    (negative / 'run.log').write_text(result.stdout + result.stderr)
    assert result.returncode != 0 and 'Assertion' in result.stderr
    report = {'result': 'DESKTOP_QTE_STATE_PASS', 'sourceSha256': sha(source), 'headerSha256': sha(header),
        'scriptSha256': sha(__file__), 'sanitizers': args.sanitize,
        'oracleSha256': sha(oracle) if oracle else None, 'executions': executions,
        'negativeControl': {'mutation': 'Disable wrong-button priority', 'exitCode': result.returncode,
            'logSha256': sha(negative / 'run.log')},
        'limits': ['Input state helper only, not connected to runtime input/UI/guest hooks yet.',
            'Default1024 cases need no game assets. Optional1536 PS2 oracle rows are private research input.',
            'Focus/stale/generation/context/ack/cooldown wrap are PC adaptations; no physical controller or game acceptance.',
            'Actual enemy detach and live prompt/animation synchronization remain unverified.']}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', default='clang++')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--ps2-oracle', type=Path)
    main(parser.parse_args())
