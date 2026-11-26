"""Regenerate the one Wii scan function needed by the existing guest recovery."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

from export_stock_wii_us_copy import digest
from verify_wii_us_copy import audit_copy


SOURCE_SHA256 = {
    'nWiiAnalyzer/src/analyzer.cpp': '2d283a2765281086f24036fa50fadf33138411b0d47cf3263be8031b8c000fcc',
    'nWiiAnalyzer/src/signature_scanner.cpp': 'dd12d3e98e4529baf7cc00bb403ac5a8dafb02fff611321dfb627f92370f87fc',
    'nWiiAnalyzer/src/dolphin_sigdb.cpp': '6b512bd933692586b6f3abf412ba99c9d98507cf262fa61194dfddb23b1c287d',
    'nWiiRecomp/src/recompiler.cpp': 'c07b510be13beda21b85c47cc14a20c93385a7e9d4a813d9785e790fb5fe5088',
    'nWiiRecomp/src/symbols.cpp': 'a382e7026f032a3afcd00b5d1cc3cc1b42474b045567895862e32d726e6b5199',
    'nWiiRuntime/src/core/loader.cpp': '5966945e8b60859cb6112e1c06d76ee7856828908b952044cee90dc786bad883',
}
FUNCTION_SHA256 = '025545ecbf9aeb7204e7ad9af52f7575595e6977f7a256b7023d6b38de94401b'


def generate(game_data, nwii_source, destination):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    nwii = Path(nwii_source).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    public = Path(__file__).resolve().parent
    if destination.exists() or destination.is_symlink() or \
            destination == game or game in destination.parents or \
            destination == nwii or nwii in destination.parents or \
            destination == public or public in destination.parents:
        raise ValueError('Destination must be fresh and outside the inputs')
    if shutil.disk_usage(destination.parent).free < 512 * 1024 * 1024:
        raise ValueError('Insufficient free space')
    for name, expected in SOURCE_SHA256.items():
        if digest(nwii / name) != expected:
            raise ValueError(f'Pinned NWiiRecomp source differs: {name}')
    destination.mkdir(mode=0o700)
    driver = destination / 'scan-driver'
    includes = [nwii / name for name in
        ('nWiiAnalyzer/include', 'nWiiRecomp/include', 'nWiiRuntime/include')]
    command = ['clang++', '-std=c++20', '-O2',
        *[part for path in includes for part in ('-I', str(path))],
        str(public / 'nwii_scan_driver.cpp'),
        *[str(nwii / name) for name in SOURCE_SHA256], '-o', str(driver)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (destination / 'compile.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise RuntimeError(f'Scan generator compilation failed: {built.stderr[-800:]}')
    output = destination / 'scan.cpp'
    generated = subprocess.run([str(driver), str(game / 'sys/main.dol'), str(output)],
        capture_output=True, text=True, timeout=180)
    (destination / 'generation.log').write_text(generated.stdout + generated.stderr)
    if generated.returncode:
        raise RuntimeError(f'Scan generation failed: {generated.stderr[-800:]}')
    normalized = output.read_text().rstrip('\n') + '\n'
    if hashlib.sha256(normalized.encode()).hexdigest() != FUNCTION_SHA256:
        raise ValueError('Generated scan function differs from verified Wii rev0')
    output.write_text(normalized)
    report = {'result': 'OWNER_WII_SCAN_INPUT_GENERATED_NOT_GAME_VERIFIED',
        'dolSha256': digest(game / 'sys/main.dol'),
        'driverSha256': digest(public / 'nwii_scan_driver.cpp'),
        'functionSha256': digest(output), 'functionWords': 76,
        'limits': ['Generated Wii-derived source is private and must not enter the public package.',
            'This is one function for scan guest recovery; it does not validate the full game.']}
    (destination / 'generation-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--nwii-source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.game_data, args.nwii_source, args.destination)['result'])


if __name__ == '__main__':
    main()
