"""Reproduce final Wii guest units with verified desktop, movie and VI adapters."""
from pathlib import Path
import argparse
import json
import shutil
import struct

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from stock_constant_fp_patch import specialize
from stock_observer_env_patch import idct
from stock_thp_dma_observation import adapt as dma
from stock_thp_update_observation import adapt as update
from stock_vi_path_observation import adapt_vi_path
from stock_desktop_look_guest_patch import adapt as desktop_look
from stock_pc_phone_audio_patch import adapt as phone_audio
from stock_fmod_event_accounting_patch import guest as fmod_events
from verify_wii_us_copy import audit_copy


MANIFEST = Path(__file__).with_name('stock-final-guest-wii-us-r5wea4-rev0.json')
MOVIE_11 = (0x8009C5E0, 0x8009C5E4, 0x8009C624, 0x8009C628,
    0x8009B760, 0x8009B76C)
MOVIE_37 = (0x80209D80, 0x8020A044)


def dol_word(dol, address):
    header = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18)
        if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]


def insert_timing(text, dol, addresses):
    for address in addresses:
        marker = f'loc_{address:08X}: ;\n'
        word = dol_word(dol, address)
        if text.count(marker) != 1 or f'// 0x{address:08X}: {word:08X}' not in text:
            raise ValueError(f'Movie timing site differs: {address:08X}')
        text = text.replace(marker,
            marker + f'    stock_movie_timing::observe(ctx, 0x{address:08X});\n')
    return text


def adapt11(text, dol):
    text = dma(update(text, dol), dol, 11)
    address = 0x8009BB98
    word = dol_word(dol, address)
    marker = f'loc_{address:08X}: ;\n'
    if text.count(marker) != 1 or f'// 0x{address:08X}: {word:08X}' not in text:
        raise ValueError('Movie context site differs')
    text = '#include "stock_context_observation.h"\n' + text.replace(marker,
        marker + f'    stock_loading_observation::observe_context(ctx, 8, 0x{address:08X});\n')
    return '#include "stock_movie_timing.h"\n' + insert_timing(text, dol, MOVIE_11)


def adapt37(text, dol):
    _, text, sites = specialize(Path(__file__).with_name('stock_fp_unavailable.h').read_text(),
        text, dol)
    if len(sites) != 933:
        raise ValueError('Constant FP site count changed')
    counts = {name: text.count(f'ctx.{name}(') for name in ('psq_load', 'psq_store')}
    if not all(counts.values()):
        raise ValueError('Expected PSQ operations missing')
    for name in counts:
        text = text.replace(f'ctx.{name}(', f'stock_{name}(ctx, ')
    text = '#include "psq_scale.h"\n' + text
    text = insert_timing(text, dol, MOVIE_37)
    marker = '#include "stock_fp_unavailable.h"'
    if text.count(marker) != 1:
        raise ValueError('FP include differs')
    text = text.replace(marker, '#include "stock_movie_timing.h"\n' + marker, 1)
    return idct(text)



def adapt38(text, dol):
    address = 0x80211D1C
    if dol_word(dol, address) != 0x48002184:
        raise ValueError('Wii OSRegisterVersion tail branch differs')
    before = '    // 0x80211D1C: 48002184\n    goto loc_80213EA0;'
    if text.count(before) != 1:
        raise ValueError('Wii OSReport tail route differs')
    return text.replace(before,
        '    // 0x80211D1C: 48002184\n    ctx.pc = 0x80213EA0;\n    return;')

def adapt39(text, dol):
    text = dma(text, dol, 39)
    text, stages, calls = adapt_vi_path(text)
    if len(stages) != 12 or calls != 102:
        raise ValueError('VI observer site counts changed')
    patches = (
        ('token=%x vi=%x:%x:%x:%x', 'token=%x counter=%x vi=%x:%x:%x:%x'),
        ('ctx.gpr[31], ctx.msr, token,',
            'ctx.gpr[31], ctx.msr, token, ctx.mmu.read32(0x8052AD4C),'))
    for before, after in patches:
        if text.count(before) != 1:
            raise ValueError('VI counter patch site differs')
        text = text.replace(before, after, 1)
    return text


def recover(game_data, scan_guest, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    scan_guest = Path(scan_guest).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a fresh directory')
    if any(destination == source or source in destination.parents
            for source in (game, scan_guest)):
        raise ValueError('Destination must be outside inputs')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space')

    expected = json.loads(MANIFEST.read_text())
    previous_manifest = Path(__file__).with_name(expected['source'])
    previous = json.loads(previous_manifest.read_text())
    previous_result = json.loads((scan_guest / 'recovery-result.json').read_text())
    dol_path = game / 'sys/main.dol'
    if expected['gameId'] != 'R5WEA4' or expected['revision'] != 0 or \
            set(expected['units']) != {f'output_{index}.cpp' for index in range(75)} or \
            previous_result['result'] != 'OWNER_WII_SCAN_GUEST_SOURCES_REPRODUCED_NOT_GAME_BUILD' or \
            previous_result['dolSha256'] != digest(dol_path) or \
            previous_result['manifestSha256'] != digest(previous_manifest) or \
            previous_result['units'] != previous['units']:
        raise ValueError('Scan guest stage does not match verified Wii DATA')
    dol = dol_path.read_bytes()
    destination.mkdir(mode=0o700)
    units = {}
    adapters = {7: lambda text, dol: desktop_look(text, dol, 7),
        8: lambda text, dol: desktop_look(text, dol, 8),
        11: adapt11, 15: lambda text, dol: desktop_look(phone_audio(text, dol), dol, 15),
        16: lambda text, dol: desktop_look(text, dol, 16),
        17: lambda text, dol: desktop_look(text, dol, 17),
        19: lambda text, dol: desktop_look(text, dol, 19),
        20: lambda text, dol: desktop_look(text, dol, 20),
        24: lambda text, dol: desktop_look(text, dol, 24),
        26: lambda text, dol: desktop_look(text, dol, 26),
        27: lambda text, dol: desktop_look(text, dol, 27),
        28: lambda text, dol: desktop_look(text, dol, 28),
        37: adapt37, 38: adapt38, 39: adapt39, 70: fmod_events}
    for index in range(75):
        name = f'output_{index}.cpp'
        original = (scan_guest / name).read_bytes()
        if record(original) != previous['units'][name]:
            raise RuntimeError(f'Scan guest changed: {name}')
        data = adapters[index](original.decode(), dol).encode() if index in adapters else original
        actual = record(data)
        if actual != expected['units'][name]:
            raise RuntimeError(f'Final guest differs from verified Wii rev0: {name}')
        (destination / name).write_bytes(data)
        units[name] = actual
    report = {'result': 'OWNER_WII_75_GUEST_SOURCES_REPRODUCED_NOT_GAME_BUILD',
        'gameData': str(game), 'scanGuest': str(scan_guest),
        'dolSha256': digest(dol_path), 'manifestSha256': digest(MANIFEST),
        'units': units, 'changedUnits': [f'output_{index}.cpp' for index in adapters],
        'limits': ['Generated guest source is private and must not enter a public package.',
            'Desktop look/phone audio and movie/VI observers are PC adapters; instruction sites are Wii DOL checked.',
            'Runtime, compilation, linking and full game acceptance remain.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--scan-guest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.game_data, args.scan_guest, args.destination)
    print(report['result'], len(report['units']))


if __name__ == '__main__':
    main()
