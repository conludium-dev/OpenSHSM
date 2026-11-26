"""Build pinned NWiiRecomp and static macOS dependencies from supplied source archives."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import time

from export_stock_wii_us_copy import digest
ARCHIVES = {
    'tomlplusplus': '8517f65938a4faae9ccf8ebb36631a38c1cadfb5efa85d9a72e15b9e97d25155',
    'sdl2': '9f0556e4a24ef5b267010038ad9e9948b62f236d5bcc4b22179f95ef62d84023',
    'glad': '8470ed1b0e9fbe88e10c34770505c8a1dc8ccb78cadcf673331aaf5224f963d2',
}


def run(command, log, timeout):
    started = time.monotonic()
    with log.open('wb') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
            timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{log.name}: exit {result.returncode}; see {log}')
    return round(time.monotonic() - started, 2)


def prepare(nwii_source, cmake, archives, destination, jobs):
    nwii = Path(nwii_source).expanduser().resolve(strict=True)
    cmake = Path(cmake).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    public = Path(__file__).resolve().parent
    if destination.exists() or destination.is_symlink() or \
            destination == public or public in destination.parents or \
            destination == nwii or nwii in destination.parents:
        raise ValueError('Destination must be fresh and outside source and public files')
    if shutil.disk_usage(destination.parent).free < 4 * 1024 ** 3:
        raise ValueError('At least 4 GiB of free space is required')
    public_manifest = public / 'stock-nwii-source-revision-595f176f.json'
    upstream = json.loads(public_manifest.read_text())
    if upstream['revision'] != '595f176f1d24cc54ff2e8389feed12d7fb553cc2' or \
            len(upstream['files']) != 89:
        raise ValueError('Pinned NWiiRecomp source manifest differs')
    for name, expected in upstream['files'].items():
        if digest(nwii / name) != expected:
            raise ValueError(f'Pinned NWiiRecomp source differs: {name}')
    if not cmake.is_file():
        raise ValueError('CMake executable is missing')
    archive_paths = {}
    for name, expected in ARCHIVES.items():
        path = Path(archives[name]).expanduser().resolve(strict=True)
        if digest(path) != expected:
            raise ValueError(f'Pinned dependency archive differs: {name}')
        archive_paths[name] = path
    destination.mkdir(mode=0o700)
    source = destination / 'cmake-source'
    source.mkdir()
    shutil.copyfile(public / 'stock-macos-toolchain.cmake.txt', source / 'CMakeLists.txt')
    shutil.copyfile(public / 'stock_sdl_mfi_hint_patch.py', source / 'stock_sdl_mfi_hint_patch.py')
    build = destination / 'build'
    definitions = [f'-D{name.upper()}_ARCHIVE={archive_paths[name]}'
        for name in ARCHIVES] + [f'-D{name.upper()}_SHA256={ARCHIVES[name]}'
        for name in ARCHIVES]
    configure = [str(cmake), '-S', str(source), '-B', str(build),
        '-DCMAKE_BUILD_TYPE=Debug', f'-DNWII_SOURCE={nwii}', *definitions]
    configure_seconds = run(configure, destination / 'configure.log', 900)
    build_seconds = run([str(cmake), '--build', str(build), '--target',
        'nwiirecomp', 'SDL2-static', 'glad', '--parallel', str(jobs)],
        destination / 'build.log', 1800)
    artifacts = {
        'recompiler': build / 'nWiiRecomp/nwiirecomp',
        'sdlLib': build / '_deps/sdl2-build/libSDL2d.a',
        'gladLib': build / '_deps/glad-build/libglad.a',
        'sdlSourceInclude': build / '_deps/sdl2-src/include',
        'sdlBuildInclude': build / '_deps/sdl2-build/include/SDL2',
        'gladInclude': build / '_deps/glad-build/include',
        'tomlInclude': build / '_deps/tomlplusplus-src/include',
    }
    for name, path in artifacts.items():
        if not path.exists():
            raise RuntimeError(f'Expected toolchain artifact missing: {name}: {path}')
    if digest(source / 'CMakeLists.txt') != digest(public / 'stock-macos-toolchain.cmake.txt'):
        raise RuntimeError('Public toolchain recipe changed during the build')
    cocoa_gl = build / '_deps/sdl2-src/src/video/cocoa/SDL_cocoaopengl.m'
    cocoa_source = cocoa_gl.read_text()
    if '/* OpenSHSM: dual-GPU pixel format adapter */' not in cocoa_source or \
            'attr[i++] = NSOpenGLPFAAllowOfflineRenderers;' in cocoa_source:
        raise RuntimeError('SDL Cocoa OpenGL adapter was not applied')
    mfi = build / '_deps/sdl2-src/src/joystick/iphoneos/SDL_mfijoystick.m'
    from stock_sdl_mfi_hint_patch import adapt
    if adapt(mfi.read_text()) != mfi.read_text() or \
            digest(source / 'stock_sdl_mfi_hint_patch.py') != digest(public / 'stock_sdl_mfi_hint_patch.py'):
        raise RuntimeError('SDL MFI hint adapter differs')
    report = {'result': 'PINNED_MACOS_TOOLCHAIN_BUILT_NOT_GAME_VERIFIED',
        'nwiiRevision': upstream['revision'], 'nwiiSource': str(nwii),
        'runtimeSource': str(nwii / 'nWiiRuntime'),
        'nwiiSourceManifestSha256': digest(public_manifest),
        'sourceFileCount': len(upstream['files']), 'archiveHashes': ARCHIVES,
        'cmakeSourceSha256': digest(source / 'CMakeLists.txt'),
        'sdlCocoaAdapterSha256': digest(cocoa_gl),
        'sdlMfiHintAdapterSha256': digest(mfi),
        'sdlMfiHintPatchSha256': digest(source / 'stock_sdl_mfi_hint_patch.py'),
        'configureSeconds': configure_seconds, 'buildSeconds': build_seconds,
        'artifacts': {name: str(path) for name, path in artifacts.items()},
        'artifactHashes': {name: digest(path) for name, path in artifacts.items()
            if path.is_file()},
        'limits': ['Dependency source archives must be supplied separately and are not part of the public package.',
            'A successful toolchain build does not prove game compilation or playability.']}
    (destination / 'toolchain-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nwii-source', type=Path, required=True)
    parser.add_argument('--cmake', type=Path, required=True)
    parser.add_argument('--toml-archive', type=Path, required=True)
    parser.add_argument('--sdl-archive', type=Path, required=True)
    parser.add_argument('--glad-archive', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('--jobs must be between 1 and 16')
    print(prepare(args.nwii_source, args.cmake,
        {'tomlplusplus': args.toml_archive, 'sdl2': args.sdl_archive,
            'glad': args.glad_archive}, args.destination, args.jobs)['result'])


if __name__ == '__main__':
    main()
