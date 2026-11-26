"""Compare actual linked interpret_one with software 750CL single steps, not fabricated game state."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import platform
import random
import re
import struct
import subprocess
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    assert platform.machine() == 'x86_64', 'Run installed Unicorn under Rosetta'
    public = Path(__file__).resolve().parent
    sys.path.insert(0, str(public.parents[1] / '_scratch/tmp/wii-static-recomp-tools/python-x64'))
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    from unicorn import ppc_const as ppc
    build = json.loads(args.build.read_text())
    for path, digest in build['dependencies'].items():
        assert sha(path) == digest, path
    for path, digest in build['retainedLinkInputs'].items():
        assert sha(path) == digest, path
    assert sha(build['archivePath']) == build['archiveSha256']
    assert sha(build['executablePath']) == build['executableSha256']
    cases = []
    values = [0, 1, 2, 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff]
    for site in build['sites']:
        word = site['opcode']
        if ((word >> 1) & 1023) == 55:
            for base, value in itertools.product([0x80000000, 0x90000000, 0xc0000000, 0xd0000000], values):
                cases.append((word, base + 0x4000, 16, 0xe000007f, value))
        else:
            for a, b, xer in itertools.product(values, values, [0, 0x20000000, 0x80000000, 0xe000007f]):
                cases.append((word, a, b, xer, 0))
    for xo, a, b, xer, rc, rd in itertools.product([8, 136], values, values,
            [0, 0x20000000, 0x80000000, 0xe000007f], [0, 1], [0, 3, 4]):
        word = (31 << 26) | (rd << 21) | (3 << 16) | (4 << 11) | (xo << 1) | rc
        cases.append((word, a, b, xer, 0))
    for base, ra, rb, rd, offset, value in itertools.product(
            [0x80000000, 0x90000000, 0xc0000000, 0xd0000000], [1, 4, 31],
            [0, 4, 6], [0, 6, 31], [0, 4, 0xfffffff0], values):
        if ra == rd:
            continue
        word = (31 << 26) | (rd << 21) | (ra << 16) | (rb << 11) | (55 << 1)
        a = base + 0x4000
        b = (base + 0x4000) // 2 if ra == rb else offset
        cases.append((word, a, b, 0xe000007f, value))
    rng = random.Random(0x5348534d)
    for _ in range(4000):
        xo = rng.choice([8, 136])
        ra, rb, rd = [rng.randrange(32) for _ in range(3)]
        word = (31 << 26) | (rd << 21) | (ra << 16) | (rb << 11) | (xo << 1) | rng.randrange(2)
        cases.append((word, rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32) & 0xe000007f, 0))
    request = ''.join(' '.join(map(str, row)) + '\n' for row in cases)
    runs = {}
    for variant in ('baseline', 'candidate'):
        probe = build['probes'][variant]
        assert sha(probe['path']) == probe['sha256']
        run = subprocess.run([probe['path']], input=request, capture_output=True, text=True, timeout=30)
        log = args.build.parent / (variant + '-execution.log')
        log.write_text(run.stdout + run.stderr)
        assert run.returncode == 0, (run.returncode, run.stderr[-4000:])
        rows = [list(map(int, row.split())) for row in re.findall(r'^RESULT (.*)$', run.stdout, re.M)]
        assert len(rows) == len(cases) and all(len(row) == 36 for row in rows)
        runs[variant] = {'rows': rows, 'logPath': str(log), 'logSha256': sha(log)}
    uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
    for base in [0x80000000, 0x90000000, 0xc0000000, 0xd0000000]:
        uc.mem_map(base, 0x10000)
    pc = 0x80007000
    mismatches = {'baseline': [], 'candidate': []}
    for index, (word, a, b, xer, value) in enumerate(cases):
        regs = [0x12340000 + i * 256 for i in range(32)]
        ra, rb = (word >> 16) & 31, (word >> 11) & 31
        regs[ra] = a
        regs[rb] = b
        for reg, initial in enumerate(regs):
            uc.reg_write(getattr(ppc, f'UC_PPC_REG_{reg}'), initial)
        uc.reg_write(ppc.UC_PPC_REG_CR, 0xaaaaaaaa)
        uc.reg_write(ppc.UC_PPC_REG_30, xer)
        uc.mem_write(pc - 4, struct.pack('>III', (31 << 26) | (30 << 21) | (1 << 16) | (467 << 1),
            word, (31 << 26) | (31 << 21) | (1 << 16) | (339 << 1)))
        uc.emu_start(pc - 4, pc, count=1)
        uc.reg_write(ppc.UC_PPC_REG_30, regs[30])
        if ((word >> 1) & 1023) == 55:
            uc.mem_write((regs[ra] + regs[rb]) & 0xffffffff, struct.pack('>I', value))
        uc.emu_start(pc, pc + 4, count=1)
        result_regs = [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{reg}')) for reg in range(32)]
        cr = uc.reg_read(ppc.UC_PPC_REG_CR)
        uc.emu_start(pc + 4, pc + 8, count=1)
        expected = [pc + 4, uc.reg_read(ppc.UC_PPC_REG_31), cr, 91, *result_regs]
        for variant in ('baseline', 'candidate'):
            actual = runs[variant]['rows'][index]
            if actual != expected:
                mismatches[variant].append({'case': index, 'instruction': f'{word:08X}',
                    'expected': expected, 'actual': actual})
    assert mismatches['baseline'] and not mismatches['candidate'], {
        variant: rows[:3] for variant, rows in mismatches.items()}
    report = {'result': 'REACHED_INTERPRETER_750CL_COMPONENT_PASS', 'cases': len(cases),
        'buildPath': str(args.build.resolve()), 'buildSha256': sha(args.build),
        'baselineMismatchCount': len(mismatches['baseline']), 'candidateMismatchCount': 0,
        'baselineExamples': mismatches['baseline'][:3],
        'runs': {name: {key: value for key, value in run.items() if key != 'rows'} for name, run in runs.items()},
        'verifierSha256': sha(Path(__file__)), 'unicornVersion': __import__('unicorn').__version__,
        'limits': ['Actual retained runtime plus software PPC750CL oracle; not physical Wii.',
            'Valid aligned RAM lwzux and non-OE subfc/subfe with Rc/alias/carry cases only.',
            'No DSI/MMIO/invalid-encoding exception delivery verification, live graphics or performance acceptance.']}
    path = args.build.parent / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], len(cases), 'cases', report['baselineMismatchCount'], 'baseline mismatches', path)


if __name__ == '__main__':
    main()
