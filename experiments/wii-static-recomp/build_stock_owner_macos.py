"""Compile an assembled owner-Wii source tree with explicit macOS or Linux dependencies."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time

from export_stock_wii_us_copy import digest
from recover_stock_late_adapter_guest import record
from verify_wii_us_copy import audit_copy
from stock_desktop_qte_payload import HEADER as QTE_PAYLOAD_HEADER, validate_descriptor


DOLPHIN_FLOATUTILS = {
    'Common/FloatUtils.cpp': 'e7bcd6a48701a361a84a9c0dfbf2ddb0c5c5219a1370838c05f99a5e8dff9dbb',
    'Common/FloatUtils.h': '8aad8c06eac7e14ac2876ddd56edc0562d28cd8c906ca6bfd9c72808810dbbe5',
}
RUNTIME_O2_MEMBERS = {'gx.cpp', 'fifo_parser.cpp', 'renderer_gl.cpp',
    'tev_shader_gen.cpp', 'texture_cache_gl.cpp', 'event_scheduler.cpp', 'ios.cpp',
    'di_device.cpp'}


def run(command, log, timeout=300):
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        log.write_text(f'Timed out after {timeout} seconds: {error}\n')
        raise RuntimeError(f'Timed out: {log.name}') from error
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{log.name}: exit {result.returncode}: {result.stderr[-800:]}')
    return round(time.monotonic() - started, 2)


def runtime_sources(source, target='macos'):
    cmake = (source / 'nWiiRuntime/CMakeLists.txt').read_text()
    listing = cmake.split('target_link_libraries(nwiiruntime', 1)[0]
    names = list(dict.fromkeys(re.findall(r'\s+(src/\S+\.cpp)', listing)))
    if target == 'macos':
        names += ['src/hle/gx/renderer_metal.mm']
    names += ['processor_adapter.cpp', 'stock_locked_cache_adapter.cpp']
    count = 45 if target == 'macos' else 44
    if len(names) != count or len({Path(name).name for name in names}) != count:
        raise ValueError('Runtime source list differs from the verified archive members')
    return names


def public_header_fingerprints(public):
    return {path.relative_to(public).as_posix(): digest(path)
        for path in sorted(public.rglob('*.h'))
        if path.is_file() and not any(part.startswith('.') for part in path.relative_to(public).parts)}


def build(game_data, source_tree, destination, sdl_includes, sdl_lib,
        glad_include, glad_lib, toml_include, dolphin_core, jobs,
        target='macos', compiler=None, public_source=None):
    if target not in ('macos', 'linux'):
        raise ValueError('Unsupported build target')
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    source = Path(source_tree).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    public = Path(public_source).resolve(strict=True) if public_source else Path(__file__).resolve().parent
    public_headers = public_header_fingerprints(public)
    if (public / QTE_PAYLOAD_HEADER).exists() or (public / QTE_PAYLOAD_HEADER).is_symlink():
        raise ValueError('Private QTE descriptor cannot be placed in public sources')
    if destination.exists() or destination.is_symlink() or \
            destination == public or public in destination.parents:
        raise ValueError('Destination must be a fresh private directory')
    if source == destination or source in destination.parents or \
            game == destination or game in destination.parents:
        raise ValueError('Build destination overlaps source or Wii DATA')
    if shutil.disk_usage(destination.parent).free < 3 * 1024 ** 3:
        raise ValueError('At least 3 GiB of free space is required')
    sdl_includes = [Path(path).expanduser().resolve(strict=True) for path in sdl_includes]
    sdl_lib = Path(sdl_lib).expanduser().resolve(strict=True)
    glad_include = Path(glad_include).expanduser().resolve(strict=True)
    glad_lib = Path(glad_lib).expanduser().resolve(strict=True)
    toml_include = Path(toml_include).expanduser().resolve(strict=True)
    dolphin_core = Path(dolphin_core).expanduser().resolve(strict=True)
    if not any((path / 'SDL.h').is_file() for path in sdl_includes) or \
            not (glad_include / 'glad/glad.h').is_file() or \
            not (toml_include / 'toml++/toml.h').is_file() or \
            not sdl_lib.is_file() or not glad_lib.is_file():
        raise ValueError('SDL2, GLAD or toml++ dependency paths are incomplete')
    if glad_lib.suffix != '.a' or (target == 'macos' and sdl_lib.suffix != '.a'):
        raise ValueError('GLAD must be static; macOS also requires static SDL2')
    for name, expected in DOLPHIN_FLOATUTILS.items():
        if digest(dolphin_core / name) != expected:
            raise ValueError(f'Pinned Dolphin FloatUtils differs: {name}')
    assembly = json.loads((source / 'owner-source-assembly-result.json').read_text())
    if assembly['dolSha256'] != digest(game / 'sys/main.dol') or \
            (assembly['guestSources'], assembly['runtimeSources'], assembly['hostSources']) != \
            (75, 45, 4):
        raise ValueError('Assembled sources do not match this Wii copy')
    for name, fingerprint in assembly['overlays'].items():
        path = source / name
        if not path.is_file() or path.is_symlink() or record(path.read_bytes()) != fingerprint:
            raise ValueError(f'Assembled source changed: {name}')
    validate_descriptor(source, assembly.get('desktopQtePayload'))
    sources = runtime_sources(source, target)
    version = re.search(r'^#define OPENSHSM_RECOMP_BUILD_VERSION "([0-9.]+)"$',
        (public / 'BuildVersion.h').read_text(), re.M)
    if not version:
        raise ValueError('BuildVersion.h differs')
    sdk = None
    if target == 'macos':
        compiler = subprocess.check_output(['xcrun', '--find', 'c++'], text=True).strip()
        sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
        if not Path(compiler).is_file() or not Path(sdk).is_dir():
            raise ValueError('macOS Command Line Tools are unavailable')
    else:
        compiler = shutil.which(compiler or 'clang++')
        if compiler is None:
            raise ValueError('Linux C++ compiler is unavailable')
    destination.mkdir(mode=0o700)
    for name in ('guest', 'runtime', 'host', 'logs'):
        (destination / name).mkdir()
    includes = [source, source / 'nWiiRuntime', source / 'nWiiRuntime/src',
        source / 'nWiiRuntime/include', public, public / 'dolphin-shim',
        dolphin_core, *sdl_includes, glad_include]
    common = [item for path in includes for item in ('-I', str(path))] + ['-isystem', str(toml_include)]
    common += ['-isysroot', sdk] if target == 'macos' else ['-pthread']
    optimized = ['-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off']
    paired = set(json.loads((public / 'stock-paired-guest-wii-us-r5wea4-rev0.json')
        .read_text())['changedUnits'])
    if len(paired) != 21:
        raise ValueError('Paired-estimate compilation set differs')

    tasks = []
    for index in range(75):
        name = f'output_{index}.cpp'
        flags = ['-g', '-std=gnu++20', *optimized,
            '-include', str(source / 'processor_adapter.h'),
            '-include', str(source / 'carry_adapter.h')]
        if name in paired:
            flags += ['-frounding-math', '-fno-fast-math']
        if name == 'output_37.cpp':
            flags[flags.index('-O2')] = '-O3'
        tasks.append(('guest', name, source / name, flags))
    for name in sources:
        tasks.append(('runtime', Path(name).name, source / 'nWiiRuntime' / name,
            ['-g', '-std=gnu++20', *(['-O2'] if Path(name).name in RUNTIME_O2_MEMBERS else [])]))
    host_flags = {
        'main.cpp': ['-g', '-std=gnu++20'],
        'fixed.cpp': ['-g', '-std=gnu++20', *optimized],
        'dispatch.cpp': ['-std=c++20', '-O2'],
        'bounds.cpp': ['-std=c++20', '-O2'],
        'FloatUtils.cpp': ['-std=c++20', '-O2', '-frounding-math', '-fno-fast-math'],
    }
    for name, flags in host_flags.items():
        path = dolphin_core / 'Common/FloatUtils.cpp' if name == 'FloatUtils.cpp' else source / name
        if target == 'linux' and name == 'main.cpp':
            from build_stock_owner_windows import windows_main_source
            linux_main = destination / 'host/main-linux.cpp'
            linux_main.write_text(windows_main_source(path.read_text()))
            path = linux_main
        tasks.append(('host', name, path, flags))

    def compile_one(task):
        group, name, path, flags = task
        obj = destination / group / (name + '.o')
        log = destination / 'logs' / (group + '-' + name + '.log')
        special = (['-I', str(public / 'active-movie-timing')]
            if group == 'guest' and name in ('output_11.cpp', 'output_37.cpp') else [])
        command = [compiler, *special, *common, *flags, '-c', str(path), '-o', str(obj)]
        seconds = run(command, log)
        return {'group': group, 'source': name, 'seconds': seconds,
            'objectSha256': digest(obj), 'sourceSha256': digest(path), 'command': command}

    compiled = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(compile_one, task) for task in tasks]
        for future in as_completed(futures):
            compiled.append(future.result())
            if len(compiled) % 10 == 0:
                print(f'Compiled {len(compiled)}/{len(tasks)} objects', flush=True)
    archive = destination / 'libnwiiruntime.a'
    run(['/usr/bin/ar', '-rcs', str(archive),
        *[str(destination / 'runtime' / (Path(name).name + '.o')) for name in sources]],
        destination / 'logs/archive.log')
    executable = destination / f'OpenSHSM-{version.group(1)}'
    objects = [destination / 'host/FloatUtils.cpp.o', destination / 'host/dispatch.cpp.o',
        destination / 'host/bounds.cpp.o', destination / 'host/main.cpp.o'] + \
        [destination / 'guest' / f'output_{index}.cpp.o' for index in range(75)] + \
        [destination / 'host/fixed.cpp.o']
    system_links = ['-lm', '-liconv',
        *[f'-Wl,-framework,{name}' for name in ('CoreVideo', 'Cocoa', 'IOKit',
            'ForceFeedback', 'Carbon', 'CoreAudio', 'AudioToolbox',
            'AVFoundation', 'Foundation')],
        *[f'-Wl,-weak_framework,{name}' for name in ('GameController', 'Metal',
            'QuartzCore', 'CoreHaptics')]]
    if target == 'macos':
        link = [compiler, '-g', '-isysroot', sdk, '-Wl,-search_paths_first',
            '-Wl,-headerpad_max_install_names', *map(str, objects), '-o', str(executable),
            str(archive), str(sdl_lib), *system_links, str(glad_lib),
            *[arg for name in ('Cocoa', 'Metal', 'QuartzCore', 'IOKit', 'CoreVideo')
                for arg in ('-framework', name)]]
    else:
        link = [compiler, '-g', *map(str, objects), '-o', str(executable),
            str(archive), str(sdl_lib), str(glad_lib), '-pthread', '-ldl', '-lGL', '-lm']
    run(link, destination / 'logs/link.log')
    if public_header_fingerprints(public) != public_headers:
        raise RuntimeError('Public headers changed during compilation; do not use this build')
    for name, fingerprint in assembly['overlays'].items():
        if record((source / name).read_bytes()) != fingerprint:
            raise RuntimeError(f'Assembled source changed during compilation: {name}')
    report = {'result': 'OWNER_WII_' + target.upper() + '_SOURCE_COMPILED_LINKED_NOT_GAME_VERIFIED',
        'targetPlatform': target, 'builderSha256': digest(Path(__file__)),
        'compilerIdentity': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
        'linkCommand': link,
        'dolSha256': assembly['dolSha256'], 'version': version.group(1),
        'guestObjects': 75, 'runtimeObjects': len(sources), 'hostObjects': 5,
        'executable': executable.name, 'executableSha256': digest(executable),
        'archiveSha256': digest(archive), 'assemblyResultSha256':
            digest(source / 'owner-source-assembly-result.json'),
        'dependencies': {'dolphinRevision': 'e2ad09306e6d371f7272205bdc363da9fe05fe08',
            'sdlLibrarySha256': digest(sdl_lib), 'gladLibrarySha256': digest(glad_lib),
            'sdlLinkage': 'static' if sdl_lib.suffix == '.a' else 'shared', 'gladLinkage': 'static',
            'runtimeO2Members': sorted(RUNTIME_O2_MEMBERS),
            'publicHeaders': public_headers},
        'desktopQtePayload': assembly.get('desktopQtePayload'),
        'compiled': sorted(compiled, key=lambda row: (row['group'], row['source'])),
        'limits': ['SDL2/GLAD/toml++ remain explicitly supplied dependencies.',
            'Linked derivative has not passed visual, audio, FPS, controller or full-game acceptance.',
            'Only Wii US R5WEA4 revision 0 has been verified.']}
    (destination / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--source-tree', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--sdl-include', type=Path, action='append', required=True)
    parser.add_argument('--sdl-lib', type=Path, required=True)
    parser.add_argument('--glad-include', type=Path, required=True)
    parser.add_argument('--glad-lib', type=Path, required=True)
    parser.add_argument('--toml-include', type=Path, required=True)
    parser.add_argument('--dolphin-core', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--target', choices=['macos', 'linux'], default='macos')
    parser.add_argument('--compiler')
    parser.add_argument('--public-source', type=Path)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('--jobs must be between 1 and 16')
    print(build(args.game_data, args.source_tree, args.destination,
        args.sdl_include, args.sdl_lib, args.glad_include, args.glad_lib,
        args.toml_include, args.dolphin_core, args.jobs, args.target,
        args.compiler, args.public_source)['result'])


if __name__ == '__main__':
    main()
