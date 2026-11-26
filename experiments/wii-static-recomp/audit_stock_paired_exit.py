"""Attribute the second owned estimate fatal to an unchanged retained unit, not stale PC."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    assert artifacts.parent == Path('/private/tmp') and artifacts.name.startswith('openshsm-pc-play-')
    path = artifacts / 'result.json'
    run = json.loads(path.read_text())
    assert run['result'] == 'USER_PLAY_EXITED' and run['exitCode'] == 1 and not run['deadlineEnabled']
    paired_path = Path(run['pairedBuildPath'])
    assert sha(paired_path) == run['pairedBuildSha256']
    build = json.loads(paired_path.read_text())
    assert sha(build['executablePath']) == build['executableSha256'] == run['executableSha256']
    tail_path = artifacts / 'runtime-tail.log'
    tail = tail_path.read_text()
    fatal = re.findall(r'UNIMPLEMENTED Opcode 4 \(ps_\*\) XO (\d+) XO_10 (\d+) at 0x([0-9a-f]+)', tail)
    assert fatal == [('26', '26', '8000eab8')]
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    original = root / 'window-input-sdk/output_1.cpp'
    record_path = original.parent / 'build.json'
    row = next(item for item in json.loads(record_path.read_text())['compiled'] if item['source'] == original.name)
    obj = original.with_name(original.name + '.o')
    assert sha(original) == row['sourceSha256']
    assert sha(obj) == row['objectSha256'] == build['retainedLinkInputs'][str(obj)]
    text = original.read_text()
    label = text.index('loc_8000EAB8: ;')
    start = text.rfind('\nvoid func_', 0, label)
    end = text.find('\nvoid func_', label)
    body = text[start:end if end >= 0 else len(text)]
    sites = []
    for match in re.finditer(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})\n'
            r'    stock_fp_preinstruction\([^\n]+\);\n'
            r'    std::cerr << "UNIMPLEMENTED Opcode 4 \(ps_\*\) XO " << (24|26)', body):
        sites.append({'address': int(match[1], 16), 'opcode': int(match[2], 16), 'xo': int(match[3])})
    assert sites == [{'address': 0x8000ebcc, 'opcode': 0x10400834, 'xo': 26},
        {'address': 0x8000ebd0, 'opcode': 0x13e01030, 'xo': 24}]
    dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == run['dolSha256']
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    def word(address):
        index = next(i for i in range(18) if layout[18 + i] <= address
            and address + 4 <= layout[18 + i] + layout[36 + i])
        return struct.unpack_from('>I', dol, layout[index] + address - layout[18 + index])[0]
    for site in sites:
        assert word(site['address']) == site['opcode']
    report = {'result': 'OTHER_RETAINED_UNIT_ESTIMATE_FATAL_IDENTIFIED',
        'loggedDispatchPc': 0x8000eab8, 'loggedPcOriginalWord': word(0x8000eab8),
        'candidateOriginalSites': sites,
        'dependencies': {str(file): sha(file) for file in
            (Path(__file__).resolve(), path, paired_path, tail_path, original, obj, record_path, dol_path)},
        'limits': ['Static exact-site attribution, not captured operand trace.',
            'Unit8 patch alone is insufficient; other retained units still contain estimate fatals.',
            'No full crash fix, permanent saves or image acceptance from this exit.']}
    output = artifacts / 'paired-exit-audit.json'
    assert not output.exists()
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, flush=True)


if __name__ == '__main__':
    main()
