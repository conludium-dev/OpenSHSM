"""Ensure AppleDouble filtering never weakens stock source fingerprint checks."""
import argparse
import hashlib
import json
from pathlib import Path
import export_stock_wii_us_copy as stock


def record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / 'export'
    runtime = root / 'nWiiRuntime'
    runtime.mkdir(parents=True)
    guest = [f'output_{i}.cpp' for i in range(75)] + ['main_output.cpp', 'functions.h', 'CMakeLists.txt']
    for name in guest:
        (root / name).write_text('fixture\n')
    (runtime / 'source.cpp').write_text('int fixture;\n')
    (runtime / 'include').mkdir()
    (runtime / 'include/header.h').write_text('#pragma once\n')
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps({'gameId': 'R5WEA4', 'revision': 0,
        'guest': {n: record(root / n) for n in guest},
        'runtime': {n: record(runtime / n) for n in ['source.cpp', 'include/header.h']}}))
    stock.STOCK_MANIFEST = manifest
    stock.verify_export(root)
    sidecar = runtime / '._source.cpp'
    metadata = b'\x00\x05\x16\x07\x00\x02\x00\x00' + b'fixture metadata' * 4
    sidecar.write_bytes(metadata)
    (runtime / '._include').write_bytes(metadata)
    stock.verify_export(root)
    rejected = []

    def refuses(label):
        try:
            stock.verify_export(root)
        except RuntimeError as error:
            rejected.append({'case': label, 'error': str(error)})
        else:
            raise AssertionError(label)

    sidecar.write_bytes(b'not metadata')
    refuses('ordinary source with sidecar-like name')
    sidecar.write_bytes(metadata)
    (runtime / 'source.cpp').write_text('changed actual source\n')
    refuses('changed pinned source with valid metadata')
    (runtime / 'source.cpp').write_text('int fixture;\n')
    stock.verify_export(root)
    (runtime / 'orphan.cpp').write_text('extra actual source\n')
    refuses('extra actual source')
    (runtime / '._orphan-without-pair').write_bytes(metadata)
    assert not stock.apple_double_sidecar(runtime / '._orphan-without-pair')
    report = {'result': 'STOCK_APPLEDOUBLE_METADATA_FILTER_AND_SOURCE_GUARDS_PASS',
        'rejected': rejected, 'scriptSha256': stock.digest(__file__),
        'exporterSha256': stock.digest(stock.__file__),
        'limits': ['Tiny synthetic source fixture only; no Wii/game/device acceptance.']}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
