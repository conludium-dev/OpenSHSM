"""Compile an assembled owner-Wii source tree for Windows x86-64 with Zig."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
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


def runtime_compile_flags(name, dsp_o2_experiment=False):
    flags = ['-g', '-std=gnu++20']
    if name in RUNTIME_O2_MEMBERS or (dsp_o2_experiment and name == 'hw_dsp.cpp'):
        flags.append('-O2')
    if dsp_o2_experiment and name == 'hw_dsp.cpp':
        flags.extend(['-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off'])
    return flags


def validate_dsp_resume(destination, resume, dsp_o2_experiment):
    if resume and dsp_o2_experiment:
        raise ValueError('DSP O2 experiment requires a fresh build; --resume is not allowed')
    report = destination / 'build-result.json'
    if resume and report.is_file():
        previous = json.loads(report.read_text())
        members = previous.get('dependencies', {}).get('runtimeO2Members', [])
        if 'hw_dsp.cpp' in members:
            raise ValueError('Do not resume an optimized DSP candidate as a baseline; use a fresh build')


def windows_main_source(text):
    version = 'SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);'
    loaded = '      std::cout << "[GL] " << (const char *)glGetString(GL_RENDERER)'
    if text.count(version) != 1 or text.count(loaded) != 1:
        raise ValueError('Windows OpenGL startup markers differ from the verified source')
    text = text.replace(version,
        'SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);')
    check = '''      if (!GLAD_GL_VERSION_3_3 || !glGenSamplers || !glBindSampler ||
          !glSamplerParameteri) {
          std::cerr << "OpenSHSM requires OpenGL 3.3 with sampler objects\\n";
          return 1;
      }
'''
    return text.replace(loaded, check + loaded)


def run(command, log, timeout=300):
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        log.write_text(f'Timed out after {timeout} seconds: {error}\n')
        raise RuntimeError(f'Timed out: {log.name}') from error
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{log.name}: exit {result.returncode}: {result.stderr[-1200:]}')
    return round(time.monotonic() - started, 2)


def runtime_sources(source):
    cmake = (source / 'nWiiRuntime/CMakeLists.txt').read_text()
    listing = cmake.split('target_link_libraries(nwiiruntime', 1)[0]
    names = list(dict.fromkeys(re.findall(r'\s+(src/\S+\.cpp)', listing)))
    names += ['processor_adapter.cpp', 'stock_locked_cache_adapter.cpp']
    if len(names) != 44 or len({Path(name).name for name in names}) != 44:
        raise ValueError('Windows runtime source list differs from the verified 44-member set')
    return names


def build(game_data, source_tree, destination, zig, sdl_includes, sdl_lib,
        sdl_dll, glad_include, glad_lib, toml_include, dolphin_core, jobs,
        resume=False, dsp_o2_experiment=False):
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    source = Path(source_tree).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    public = Path(__file__).resolve().parent
    if (public / QTE_PAYLOAD_HEADER).exists() or (public / QTE_PAYLOAD_HEADER).is_symlink():
        raise ValueError('Private QTE descriptor cannot be placed in public sources')
    validate_dsp_resume(destination, resume, dsp_o2_experiment)
    if destination.is_symlink() or \
            destination == public or public in destination.parents:
        raise ValueError('Destination must be a fresh private directory')
    if destination.exists() and not resume:
        raise ValueError('Destination exists; use --resume only for this interrupted build')
    if source == destination or source in destination.parents or \
            game == destination or game in destination.parents:
        raise ValueError('Build destination overlaps source or Wii DATA')
    if shutil.disk_usage(destination.parent).free < 3 * 1024 ** 3:
        raise ValueError('At least 3 GiB of free space is required')
    zig = Path(zig).expanduser().resolve(strict=True)
    sdl_includes = [Path(path).expanduser().resolve(strict=True) for path in sdl_includes]
    sdl_lib = Path(sdl_lib).expanduser().resolve(strict=True)
    sdl_dll = Path(sdl_dll).expanduser().resolve(strict=True)
    glad_include = Path(glad_include).expanduser().resolve(strict=True)
    glad_lib = Path(glad_lib).expanduser().resolve(strict=True)
    toml_include = Path(toml_include).expanduser().resolve(strict=True)
    dolphin_core = Path(dolphin_core).expanduser().resolve(strict=True)
    if not any((path / 'SDL.h').is_file() for path in sdl_includes) or \
            not (glad_include / 'glad/glad.h').is_file() or \
            not (toml_include / 'toml++/toml.h').is_file() or \
            not sdl_lib.is_file() or not sdl_dll.is_file() or not glad_lib.is_file():
        raise ValueError('SDL2, GLAD or toml++ dependency paths are incomplete')
    if sdl_dll.name.casefold() != 'sdl2.dll':
        raise ValueError('SDL runtime must be named SDL2.dll')
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
    if resume:
        previous_path = destination / 'build-result.json'
        previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
        if assembly.get('desktopQtePayload') is not None or previous.get('desktopQtePayload') is not None:
            raise ValueError('Prepared QTE payload requires a fresh Windows build; --resume is not allowed')
    sources = runtime_sources(source)
    version = re.search(r'^#define OPENSHSM_RECOMP_BUILD_VERSION "([0-9.]+)"$',
        (public / 'BuildVersion.h').read_text(), re.M)
    if not version:
        raise ValueError('BuildVersion.h differs')
    if destination.exists():
        for name in ('guest', 'runtime', 'host', 'logs'):
            path = destination / name
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f'Incomplete resume directory: {path}')
    else:
        destination.mkdir(mode=0o700)
        for name in ('guest', 'runtime', 'host', 'logs'):
            (destination / name).mkdir()
    includes = [source, source / 'nWiiRuntime', source / 'nWiiRuntime/src',
        source / 'nWiiRuntime/include', public, public / 'dolphin-shim',
        dolphin_core, *sdl_includes, glad_include]
    common = [item for path in includes for item in ('-I', str(path))] + \
        ['-isystem', str(toml_include), '-target', 'x86_64-windows-gnu',
            '-DWIN32_LEAN_AND_MEAN', '-DNOMINMAX', '-DSDL_MAIN_HANDLED', '-fno-char8_t']
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
            runtime_compile_flags(Path(name).name, dsp_o2_experiment)))
    host_flags = {
        'main.cpp': ['-g', '-std=gnu++20'],
        'fixed.cpp': ['-g', '-std=gnu++20', *optimized],
        'dispatch.cpp': ['-std=c++20', '-O2'],
        'bounds.cpp': ['-std=c++20', '-O2'],
        'FloatUtils.cpp': ['-std=c++20', '-O2', '-frounding-math', '-fno-fast-math'],
    }
    fixed_source = (source / 'fixed.cpp').read_text()
    setjmp_source = 'if (_setjmp(ctx.exception_jmp_buf) == 0) {'
    setjmp_windows = 'if (setjmp(ctx.exception_jmp_buf) == 0) {'
    if fixed_source.count(setjmp_source) != 1 or setjmp_windows in fixed_source:
        raise ValueError('Fixed dispatcher setjmp call differs from the verified source')
    fixed_windows = destination / 'host/fixed.windows.cpp'
    fixed_windows.write_text(fixed_source.replace(setjmp_source, setjmp_windows))
    main_windows = destination / 'host/main.windows.cpp'
    main_windows.write_text(windows_main_source((source / 'main.cpp').read_text()))
    for name, flags in host_flags.items():
        if name == 'FloatUtils.cpp':
            path = dolphin_core / 'Common/FloatUtils.cpp'
        elif name == 'fixed.cpp':
            path = fixed_windows
        elif name == 'main.cpp':
            path = main_windows
        else:
            path = source / name
        tasks.append(('host', name, path, flags))

    def compile_one(task):
        group, name, path, flags = task
        obj = destination / group / (name + '.o')
        log = destination / 'logs' / (group + '-' + name + '.log')
        if resume and not (group == 'host' and name == 'main.cpp') and \
                obj.is_file() and not obj.is_symlink() and obj.stat().st_size > 0:
            return {'group': group, 'source': name, 'seconds': 0,
                'objectSha256': digest(obj), 'reused': True}
        special = (['-I', str(public / 'active-movie-timing')]
            if group == 'guest' and name in ('output_11.cpp', 'output_37.cpp') else [])
        seconds = run([str(zig), 'c++', *special, *common, *flags,
            '-c', str(path), '-o', str(obj)], log)
        return {'group': group, 'source': name, 'seconds': seconds,
            'objectSha256': digest(obj), 'reused': False}

    compiled = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(compile_one, task) for task in tasks]
        for future in as_completed(futures):
            compiled.append(future.result())
            if len(compiled) % 10 == 0:
                print(f'Compiled {len(compiled)}/{len(tasks)} objects', flush=True)
    archive = destination / 'libnwiiruntime.a'
    run([str(zig), 'ar', 'rcs', str(archive),
        *[str(destination / 'runtime' / (Path(name).name + '.o')) for name in sources]],
        destination / 'logs/archive.log')
    executable = destination / f'OpenSHSM-{version.group(1)}.exe'
    objects = [destination / 'host/FloatUtils.cpp.o', destination / 'host/dispatch.cpp.o',
        destination / 'host/bounds.cpp.o', destination / 'host/main.cpp.o'] + \
        [destination / 'guest' / f'output_{index}.cpp.o' for index in range(75)] + \
        [destination / 'host/fixed.cpp.o']
    link = [str(zig), 'c++', '-target', 'x86_64-windows-gnu', *map(str, objects),
        '-o', str(executable), str(archive), str(sdl_lib), str(glad_lib),
        '-lopengl32', '-lws2_32', '-luser32', '-lgdi32', '-lshell32', '-lole32',
        '-luuid', '-lwinmm', '-limm32', '-lversion', '-lsetupapi']
    run(link, destination / 'logs/link.log', timeout=900)
    copied_sdl = destination / 'SDL2.dll'
    shutil.copyfile(sdl_dll, copied_sdl)
    report = {'result': 'OWNER_WII_WINDOWS_SOURCE_COMPILED_LINKED_NOT_GAME_VERIFIED',
        'dolSha256': assembly['dolSha256'], 'version': version.group(1),
        'target': 'x86_64-windows-gnu', 'guestObjects': 75,
        'runtimeObjects': 44, 'hostObjects': 5, 'executable': executable.name,
        'executableSha256': digest(executable), 'sdlRuntime': copied_sdl.name,
        'sdlRuntimeSha256': digest(copied_sdl), 'archiveSha256': digest(archive),
        'assemblyResultSha256': digest(source / 'owner-source-assembly-result.json'),
        'windowsAdapters': {'fixedSetjmpSourceSha256': digest(source / 'fixed.cpp'),
            'fixedSetjmpWindowsSha256': digest(fixed_windows),
            'mainSourceSha256': digest(source / 'main.cpp'),
            'mainWindowsSha256': digest(main_windows),
            'minimumOpenGLVersion': '3.3', 'samplerEntryPointsChecked': True},
        'dependencies': {'dolphinRevision': 'e2ad09306e6d371f7272205bdc363da9fe05fe08',
            'zigSha256': digest(zig), 'sdlLibrarySha256': digest(sdl_lib),
            'gladLibrarySha256': digest(glad_lib),
            'runtimeO2Members': sorted(RUNTIME_O2_MEMBERS | ({'hw_dsp.cpp'} if dsp_o2_experiment else set())),
            'dspO2Experiment': dsp_o2_experiment,
            'dspCompileFlags': runtime_compile_flags('hw_dsp.cpp', dsp_o2_experiment)},
        'reusedObjects': sum(bool(row['reused']) for row in compiled),
        'desktopQtePayload': assembly.get('desktopQtePayload'),
        'compiled': sorted(compiled, key=lambda row: (row['group'], row['source'])),
        'limits': ['Windows source compilation and linking are not gameplay acceptance.',
            'Visual, audio, FPS and physical controllers require a native Windows test.',
            'Only Wii US R5WEA4 revision 0 is accepted as an input copy.']}
    (destination / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--source-tree', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--zig', type=Path, required=True)
    parser.add_argument('--sdl-include', type=Path, action='append', required=True)
    parser.add_argument('--sdl-lib', type=Path, required=True)
    parser.add_argument('--sdl-dll', type=Path, required=True)
    parser.add_argument('--glad-include', type=Path, required=True)
    parser.add_argument('--glad-lib', type=Path, required=True)
    parser.add_argument('--toml-include', type=Path, required=True)
    parser.add_argument('--dolphin-core', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--dsp-o2-experiment', action='store_true',
        help='Private strict-O2 DSP candidate; requires a fresh build and Windows performance acceptance')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('--jobs must be between 1 and 16')
    print(build(args.game_data, args.source_tree, args.destination, args.zig,
        args.sdl_include, args.sdl_lib, args.sdl_dll, args.glad_include,
        args.glad_lib, args.toml_include, args.dolphin_core, args.jobs,
        args.resume, args.dsp_o2_experiment)['result'])


if __name__ == '__main__':
    main()
