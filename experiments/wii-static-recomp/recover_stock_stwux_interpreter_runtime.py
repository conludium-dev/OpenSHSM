"""Reproduce the Wii-observed stwux fallback over the verified interpreter stage."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_interpreter_stwux import adapt, check_dol
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-stwux-interpreter-runtime-wii-us-r5wea4-rev0.json')
BASE_MANIFEST = Path(__file__).with_name('stock-interpreter-runtime-wii-us-r5wea4-rev0.json')


def recover(game_data, interpreter_runtime, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    interpreter_runtime = Path(interpreter_runtime).resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink() or \
            any(destination == source or source in destination.parents
                for source in (game, interpreter_runtime)):
        raise ValueError('Destination must be fresh and outside inputs')
    if shutil.disk_usage(destination.parent).free < 16 * 1024 * 1024:
        raise ValueError('Insufficient free space')
    expected = json.loads(MANIFEST.read_text())
    base_expected = json.loads(BASE_MANIFEST.read_text())
    base_report = json.loads((interpreter_runtime / 'recovery-result.json').read_text())
    dol_path = game / 'sys/main.dol'
    dol_sha = digest(dol_path)
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != BASE_MANIFEST.name or \
            base_report['result'] != 'OWNER_WII_ACTIVE_INTERPRETER_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD' or \
            base_report['dolSha256'] != dol_sha or \
            base_report['manifestSha256'] != digest(BASE_MANIFEST) or \
            base_report['interpreter'] != base_expected['interpreter']:
        raise ValueError('Interpreter stage differs from verified Wii US rev0')
    source = interpreter_runtime / 'interpreter.cpp'
    if record(source.read_bytes()) != base_expected['interpreter']:
        raise ValueError('Base interpreter source differs')
    check_dol(dol_path.read_bytes())
    data = adapt(source.read_text()).encode()
    if record(data) != expected['interpreter']:
        raise RuntimeError('stwux interpreter source differs')
    destination.mkdir(mode=0o700)
    (destination / 'interpreter.cpp').write_bytes(data)
    report = {'result': 'OWNER_WII_STWUX_INTERPRETER_SOURCE_REPRODUCED_NOT_RUNTIME_BUILD',
        'dolSha256': dol_sha, 'manifestSha256': digest(MANIFEST),
        'baseSourceSha256': digest(source), 'interpreter': record(data),
        'limits': ['Only Wii-observed opcode 31/XO183 semantics are added to the existing fallback.',
            'Invalid encodings and program exception routing are not accepted.',
            'Full game and performance acceptance remain unverified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--interpreter-runtime', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.interpreter_runtime,
        args.destination)['result'])


if __name__ == '__main__':
    main()
