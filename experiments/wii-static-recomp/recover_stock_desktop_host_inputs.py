"""Reproduce desktop help and host pacing from the verified own-Wii host stage."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_desktop_input_host_patch import adapt
from stock_gx_profile_window_patch import host as profile_host
from stock_desktop_look_guest_patch import adapt_qte_dispatch
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-desktop-host-inputs-wii-us-r5wea4-rev0.json')
HOST_MANIFEST = Path(__file__).with_name('stock-host-inputs-wii-us-r5wea4-rev0.json')


def recover(game_data, host_inputs, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    host_inputs = Path(host_inputs).resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be fresh')
    if any(destination == source or source in destination.parents
            for source in (game, host_inputs)):
        raise ValueError('Destination overlaps inputs')
    if shutil.disk_usage(destination.parent).free < 16 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    host_expected = json.loads(HOST_MANIFEST.read_text())
    host_report = json.loads((host_inputs / 'recovery-result.json').read_text())
    dol_sha = digest(game / 'sys/main.dol')
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            expected['source'] != HOST_MANIFEST.name or \
            host_report['result'] != 'OWNER_WII_ACTIVE_HOST_SOURCES_REPRODUCED_NOT_GAME_BUILD' or \
            host_report['dolSha256'] != dol_sha or \
            host_report['manifestSha256'] != digest(HOST_MANIFEST) or \
            host_report['outputs'] != host_expected['outputs']:
        raise ValueError('Host inputs differ from verified Wii US rev0')

    generated = {}
    for name, fingerprint in host_expected['outputs'].items():
        original = (host_inputs / name).read_bytes()
        if record(original) != fingerprint:
            raise ValueError(f'Host source changed: {name}')
        generated[name] = adapt(original.decode()).encode() if name == 'main.cpp' else original
    if {name: record(data) for name, data in generated.items()} != expected['outputs']:
        raise RuntimeError('Desktop host sources differ')
    from stock_adma_reporting_patch import host as reporting
    generated['main.cpp'] = reporting(generated['main.cpp'].decode()).encode()
    if record(generated['main.cpp']) != expected['reportingOutput']:
        raise RuntimeError('Host ADMA reporting stage differs')
    generated['main.cpp'] = profile_host(generated['main.cpp'].decode()).encode()
    if record(generated['main.cpp']) != expected['profileReadbackOutput']:
        raise RuntimeError('Host profile readback stage differs')
    generated['fixed.cpp'] = adapt_qte_dispatch(generated['fixed.cpp'].decode(),
        (game / 'sys/main.dol').read_bytes()).encode()
    if record(generated['fixed.cpp']) != expected['desktopQteDispatchOutput']:
        raise RuntimeError('Desktop QTE dispatch stage differs')

    destination.mkdir(mode=0o700)
    for name, data in generated.items():
        (destination / name).write_bytes(data)
    report = {'result': 'OWNER_WII_DESKTOP_HOST_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'dolSha256': dol_sha, 'manifestSha256': digest(MANIFEST),
        'outputs': {name: record(data) for name, data in generated.items()},
        'limits': ['F1 help, host-loop pacing and optional ADMA reporting are PC host adapters.',
            'Actual mouse focus and physical controllers require live verification.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--host-inputs', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(recover(args.game_data, args.host_inputs, args.destination)['result'])


if __name__ == '__main__':
    main()
