"""Assemble verified Wii-derived guest, runtime and host sources in a fresh tree."""
from pathlib import Path
import argparse
import json
import shutil

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy


STAGES = {
    'unchanged': {},
    'interpreter': {'interpreter.cpp': 'src/hle/interpreter.cpp'},
    'os_hle': {'os_hle_stubs.cpp': 'src/core/os_hle_stubs.cpp'},
    'ipc': {'hw_ipc.cpp': 'src/hw/hw_ipc.cpp'},
    'input': {
        'mouse_keyboard_source.cpp': 'src/input/sources/mouse_keyboard_source.cpp',
        'gamepad_source.cpp': 'src/input/sources/gamepad_source.cpp',
    },
    'core': {},
    'cpu_cp': {},
    'dsp': {},
    'graphics': {},
    'ios': {'src/hle/ios.cpp': 'src/hle/ios.cpp'},
    'nand': {},
    'scheduler': {},
}
COUNTS = {'unchanged': 22, 'interpreter': 1, 'os_hle': 1, 'ipc': 1,
    'input': 3, 'core': 3, 'cpu_cp': 4, 'dsp': 1, 'graphics': 5,
    'ios': 1, 'nand': 2, 'scheduler': 1}


def stage_entries(name, directory, dol_sha):
    directory = Path(directory).expanduser().resolve(strict=True)
    report = json.loads((directory / 'recovery-result.json').read_text())
    if report['dolSha256'] != dol_sha:
        raise ValueError(f'{name}: different Wii DOL')
    fingerprints = report.get('outputs') or report.get('files')
    if fingerprints is None:
        field = {'interpreter': 'interpreter', 'os_hle': 'osHle',
            'ipc': 'ipc', 'ios': 'output'}[name]
        filename = {'interpreter': 'interpreter.cpp', 'os_hle': 'os_hle_stubs.cpp',
            'ipc': 'hw_ipc.cpp', 'ios': 'src/hle/ios.cpp'}[name]
        fingerprints = {filename: report[field]}
    entries = {}
    for source_name, fingerprint in fingerprints.items():
        path = directory / source_name
        if not path.is_file() or path.is_symlink() or record(path.read_bytes()) != fingerprint:
            raise ValueError(f'{name}: recovered source differs: {source_name}')
        target = STAGES[name].get(source_name, source_name)
        if target in entries:
            raise ValueError(f'{name}: duplicate target: {target}')
        entries[target] = path
    sources = sum(target.endswith(('.cpp', '.mm')) for target in entries)
    if sources != COUNTS[name]:
        raise ValueError(f'{name}: runtime source count {sources} differs')
    return entries


def assemble(game_data, stock_export, dma_quantization, final_guest, host_inputs,
        stages, destination, prepare_desktop_qte=False):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    dol_sha = digest(game / 'sys/main.dol')
    stock_export = Path(stock_export).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be fresh')
    public = Path(__file__).resolve().parent
    if destination == public or public in destination.parents:
        raise ValueError('Private generated sources cannot be placed in the public source tree')
    inputs = [stock_export, Path(dma_quantization).resolve(strict=True),
        Path(final_guest).resolve(strict=True),
        Path(host_inputs).resolve(strict=True)] + list(stages.values())
    if any(destination == source or source in destination.parents for source in inputs + [game]):
        raise ValueError('Destination overlaps an input')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space')
    stock_result = json.loads((stock_export.parent / 'export-result.json').read_text())
    if stock_result['dolSha256'] != dol_sha or \
            stock_result['result'] != 'OWNER_WII_US_R5WEA4_REV0_STOCK_SOURCE_EXPORTED_NOT_GAME_BUILD':
        raise ValueError('Stock export differs from Wii DATA')
    guest_dir = Path(final_guest).resolve(strict=True)
    guest_report = json.loads((guest_dir / 'recovery-result.json').read_text())
    if guest_report['dolSha256'] != dol_sha or len(guest_report['units']) != 75:
        raise ValueError('Final guest stage differs')
    quant_dir = Path(dma_quantization).resolve(strict=True)
    quant_report = json.loads((quant_dir / 'recovery-result.json').read_text())
    if quant_report['dolSha256'] != dol_sha or \
            set(quant_report['headers']) != {
                'include/runtime/cpu_context.h', 'processor_adapter.h', 'carry_adapter.h'}:
        raise ValueError('DMA/quantization headers differ')
    host_dir = Path(host_inputs).resolve(strict=True)
    host_report = json.loads((host_dir / 'recovery-result.json').read_text())
    if host_report['dolSha256'] != dol_sha or len(host_report['outputs']) != 5:
        raise ValueError('Host stage differs')
    if set(stages) != set(STAGES):
        raise ValueError('Exactly the twelve runtime stages are required')

    overlays = {}
    for name, fingerprint in guest_report['units'].items():
        path = guest_dir / name
        if not path.is_file() or path.is_symlink() or record(path.read_bytes()) != fingerprint:
            raise ValueError(f'Guest source differs: {name}')
        overlays[name] = path
    for name, fingerprint in quant_report['headers'].items():
        path = quant_dir / name
        if not path.is_file() or path.is_symlink() or record(path.read_bytes()) != fingerprint:
            raise ValueError(f'DMA/quantization header differs: {name}')
        target = 'nWiiRuntime/' + name if name.startswith('include/') else name
        overlays[target] = path
    for name, directory in stages.items():
        for target, path in stage_entries(name, directory, dol_sha).items():
            target = 'nWiiRuntime/' + target
            if target in overlays:
                raise ValueError(f'Runtime source collision: {target}')
            overlays[target] = path
    for name, fingerprint in host_report['outputs'].items():
        path = host_dir / name
        if not path.is_file() or path.is_symlink() or record(path.read_bytes()) != fingerprint:
            raise ValueError(f'Host source differs: {name}')
        overlays[name] = path
    shutil.copytree(stock_export, destination)
    for target, source in overlays.items():
        output = destination / target
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
    import stock_desktop_settings_patch as desktop_settings
    stock_manifest = json.loads((public / 'stock-export-wii-us-r5wea4-rev0.json').read_text())
    for name, adapter in (('include/runtime/config.h', desktop_settings.header),
            ('src/core/config.cpp', desktop_settings.source)):
        target = 'nWiiRuntime/' + name
        output = destination / target
        if record(output.read_bytes()) != stock_manifest['runtime'][name]:
            raise ValueError(f'Desktop settings config input differs: {name}')
        output.write_text(adapter(output.read_text()))
        overlays[target] = output
    host_main = destination / 'main.cpp'
    host_main.write_text(desktop_settings.host(host_main.read_text()))
    overlays['main.cpp'] = host_main
    qte_payload = None
    if prepare_desktop_qte:
        from types import SimpleNamespace
        from prepare_desktop_qte_glyphs import main as prepare_glyphs
        from stock_desktop_qte_payload import HEADER, write_descriptor
        prepare_glyphs(SimpleNamespace(game_data=game, output=destination / 'desktop-qte'), emit_result=False)
        qte_payload = write_descriptor(destination / 'desktop-qte', destination / HEADER)
        overlays[HEADER] = destination / HEADER
    report = {'result': 'OWNER_WII_SOURCES_ASSEMBLED_NOT_COMPILED',
        'dolSha256': dol_sha, 'guestSources': 75, 'runtimeSources': sum(COUNTS.values()),
        'hostSources': 4, 'desktopSettingsAdapterSha256': digest(public / 'stock_desktop_settings_patch.py'),
        'desktopQtePayload': qte_payload,
        'overlays': {target: record(source.read_bytes())
            for target, source in overlays.items()},
        'limits': ['This tree includes private Wii-derived source and must not be published.',
            'Compilation dependencies and portable launch remain unverified.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'owner-source-assembly-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--stock-export', type=Path, required=True)
    parser.add_argument('--dma-quantization', type=Path, required=True)
    parser.add_argument('--final-guest', type=Path, required=True)
    parser.add_argument('--host-inputs', type=Path, required=True)
    parser.add_argument('--runtime-stage', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--prepare-desktop-qte', action='store_true')
    args = parser.parse_args()
    stages = {}
    for entry in args.runtime_stage:
        name, separator, path = entry.partition('=')
        if not separator or name in stages or name not in STAGES:
            parser.error(f'Invalid runtime stage: {entry}')
        stages[name] = Path(path).expanduser().resolve(strict=True)
    print(assemble(args.game_data, args.stock_export, args.dma_quantization, args.final_guest,
        args.host_inputs, stages, args.destination, args.prepare_desktop_qte)['result'])


if __name__ == '__main__':
    main()
