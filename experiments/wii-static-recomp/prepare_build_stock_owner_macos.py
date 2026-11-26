"""Run the verified Wii US rev0 source recovery and macOS build in a fresh directory."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

from export_stock_wii_us_copy import digest, require_corrected_signatures
from prepare_stock_macos_toolchain import ARCHIVES
from verify_wii_us_copy import audit_copy


RUNTIME_STAGES = ('unchanged', 'interpreter', 'os_hle', 'ipc', 'input',
    'core', 'cpu_cp', 'dsp', 'graphics', 'ios', 'nand', 'scheduler')


def load_toolchain(path):
    try:
        toolchain_path = Path(path).expanduser().resolve(strict=True)
        toolchain = json.loads(toolchain_path.read_text())
        if toolchain['result'] != 'PINNED_MACOS_TOOLCHAIN_BUILT_NOT_GAME_VERIFIED' or \
                toolchain['archiveHashes'] != ARCHIVES or \
                toolchain['nwiiSourceManifestSha256'] != digest(
                    Path(__file__).with_name('stock-nwii-source-revision-595f176f.json')):
            raise ValueError('Pinned toolchain report differs')
        artifacts = {name: Path(path).resolve(strict=True)
            for name, path in toolchain['artifacts'].items()}
        if any(digest(artifacts[name]) != expected
                for name, expected in toolchain['artifactHashes'].items()):
            raise ValueError('Toolchain artifact differs from its report')
        cocoa_gl = artifacts['sdlSourceInclude'].parent / \
            'src/video/cocoa/SDL_cocoaopengl.m'
        if digest(cocoa_gl) != toolchain['sdlCocoaAdapterSha256']:
            raise ValueError('SDL Cocoa OpenGL adapter differs from toolchain report')
        return toolchain, artifacts
    except (OSError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f'Invalid pinned toolchain report: {error}') from error


def prepare_build(args):
    if args.toolchain_result:
        toolchain, artifacts = load_toolchain(args.toolchain_result)
        args.recompiler = artifacts['recompiler']
        args.nwii_source = Path(toolchain['nwiiSource'])
        args.runtime_source = Path(toolchain['runtimeSource'])
        args.sdl_include = [artifacts['sdlSourceInclude'], artifacts['sdlBuildInclude']]
        args.sdl_lib = artifacts['sdlLib']
        args.glad_include = artifacts['gladInclude']
        args.glad_lib = artifacts['gladLib']
        args.toml_include = artifacts['tomlInclude']
    game = Path(audit_copy(args.game_data)['source']).resolve(strict=True)
    if args.sdl_lib.suffix != '.a' or args.glad_lib.suffix != '.a' or \
            not args.sdl_lib.is_file() or not args.glad_lib.is_file():
        raise ValueError('SDL2 and GLAD static .a libraries are required')
    destination = args.destination.expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError('Destination parent does not exist')
    destination = destination.parent.resolve(strict=True) / destination.name
    public = Path(__file__).resolve().parent
    inputs = [game, Path(args.recompiler).resolve(strict=True),
        Path(args.runtime_source).resolve(strict=True),
        Path(args.nwii_source).resolve(strict=True)]
    if destination.exists() or destination.is_symlink() or \
            destination == public or public in destination.parents or \
            any(destination == path or path in destination.parents for path in inputs):
        raise ValueError('Destination must be fresh and outside Wii DATA, source and tools')
    if shutil.disk_usage(destination.parent).free < 6 * 1024 ** 3:
        raise ValueError('At least 6 GiB of free space is required')
    destination.mkdir(mode=0o700)
    logs = destination / 'logs'
    logs.mkdir()

    def step(name, script, options, timeout=900):
        command = [sys.executable, str(public / script),
            '--game-data', str(game), *map(str, options),
            '--destination', str(destination / name)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        (logs / f'{name}.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'{name} failed; inspect {logs / (name + ".log")}')
        print(f'{name}: complete', flush=True)

    stock = destination / 'stock'
    step('stock', 'export_stock_wii_us_copy.py',
        ['--recompiler', args.recompiler, '--runtime-source', args.runtime_source])
    export = stock / 'export'
    require_corrected_signatures(export.parent / 'export-result.json')
    step('optimized', 'recover_stock_optimized_guest.py',
        ['--stock-export', export])
    step('hid2', 'recover_stock_hid2_carry_guest.py',
        ['--optimized-guest', destination / 'optimized'])
    step('dma', 'recover_stock_dma_quantization_sources.py',
        ['--stock-export', export, '--hid2-carry-guest', destination / 'hid2'])
    step('fp', 'recover_stock_fp_guard_guest.py',
        ['--dma-quantization', destination / 'dma'])
    step('late', 'recover_stock_late_adapter_guest.py',
        ['--fp-guest', destination / 'fp'])
    step('guest38', 'recover_stock_guest38_transition.py',
        ['--late-guest', destination / 'late'])
    step('paired', 'recover_stock_paired_guest.py',
        ['--guest38', destination / 'guest38'])
    step('scan-input', 'generate_stock_scan_input.py',
        ['--nwii-source', args.nwii_source], timeout=300)
    step('scan', 'recover_stock_scan_guest.py',
        ['--paired-guest', destination / 'paired',
            '--mass-guest', destination / 'scan-input/scan.cpp'])
    step('final-guest', 'recover_stock_final_guest.py',
        ['--scan-guest', destination / 'scan'])
    step('host', 'recover_stock_host_inputs.py',
        ['--stock-export', export])
    step('desktop-host', 'recover_stock_desktop_host_inputs.py',
        ['--host-inputs', destination / 'host'])
    step('base-interpreter', 'recover_stock_interpreter_runtime.py',
        ['--stock-export', export])
    for name, script, extra in (
        ('snapshot-input', 'recover_stock_input_snapshot_runtime.py', []),
        ('unchanged', 'recover_stock_unchanged_runtime.py', []),
        ('interpreter', 'recover_stock_stwux_interpreter_runtime.py',
            ['--interpreter-runtime', destination / 'base-interpreter']),
        ('os_hle', 'recover_stock_os_hle_runtime.py', []),
        ('ipc', 'recover_stock_ipc_runtime.py', []),
        ('pause-input', 'recover_stock_pause_input_runtime.py',
            ['--snapshot-runtime', destination / 'snapshot-input']),
        ('input', 'recover_stock_desktop_input_runtime.py',
            ['--pause-runtime', destination / 'pause-input']),
        ('core', 'recover_stock_core_runtime.py', []),
        ('cpu_cp', 'recover_stock_cpu_cp_runtime.py', []),
        ('dsp', 'recover_stock_dsp_runtime.py', []),
        ('graphics', 'recover_stock_graphics_runtime.py', []),
        ('ios', 'recover_stock_ios_runtime.py', []),
        ('nand', 'recover_stock_nand_runtime.py', []),
        ('scheduler', 'recover_stock_scheduler_runtime.py', []),
    ):
        options = extra if name == 'interpreter' else ['--stock-export', export, *extra]
        step(name, script, options)
    stage_options = [item for name in RUNTIME_STAGES
        for item in ('--runtime-stage', f'{name}={destination / name}')]
    if getattr(args, 'prepare_desktop_qte', False):
        stage_options.append('--prepare-desktop-qte')
    step('assembled', 'assemble_stock_owner_sources.py',
        ['--stock-export', export, '--dma-quantization', destination / 'dma',
            '--final-guest', destination / 'final-guest',
            '--host-inputs', destination / 'desktop-host', *stage_options])
    step('fixed-assembled', 'recover_stock_fixed_ios_assembly.py',
        ['--assembly', destination / 'assembled', '--stock-export', export])
    build_options = ['--source-tree', destination / 'fixed-assembled',
        *[item for path in args.sdl_include for item in ('--sdl-include', path)],
        '--sdl-lib', args.sdl_lib, '--glad-include', args.glad_include,
        '--glad-lib', args.glad_lib, '--toml-include', args.toml_include,
        '--dolphin-core', args.dolphin_core, '--jobs', args.jobs]
    step('build', 'build_stock_owner_macos.py', build_options, timeout=3600)
    built = json.loads((destination / 'build/build-result.json').read_text())
    report = {'result': 'OWNER_WII_RECOVERED_AND_COMPILED_NOT_GAME_VERIFIED',
        'dolSha256': digest(game / 'sys/main.dol'),
        'toolchainResultSha256': digest(args.toolchain_result) if args.toolchain_result else None,
        'fixedIosResultSha256': digest(destination / 'fixed-assembled/fixed-ios-result.json'),
        'executable': str(destination / 'build' / built['executable']),
        'buildResultSha256': digest(destination / 'build/build-result.json'),
        'desktopQtePayload': built.get('desktopQtePayload'),
        'limits': ['Generated Wii code and build outputs are private.',
            'This requires a previously extracted Wii DATA directory and external toolchains/libraries.',
            'Visual, audio, FPS, controller and full-game acceptance remain.']}
    (destination / 'prepare-build-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--toolchain-result', type=Path)
    parser.add_argument('--recompiler', type=Path)
    parser.add_argument('--runtime-source', type=Path)
    parser.add_argument('--nwii-source', type=Path)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--sdl-include', type=Path, action='append')
    parser.add_argument('--sdl-lib', type=Path)
    parser.add_argument('--glad-include', type=Path)
    parser.add_argument('--glad-lib', type=Path)
    parser.add_argument('--toml-include', type=Path)
    parser.add_argument('--dolphin-core', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--prepare-desktop-qte', action='store_true',
        help='Prepare the experimental desktop QTE glyph bank from your own Wii data')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('--jobs must be between 1 and 16')
    explicit = (args.recompiler, args.runtime_source, args.nwii_source,
        args.sdl_include, args.sdl_lib, args.glad_include, args.glad_lib,
        args.toml_include)
    if args.toolchain_result:
        if any(value is not None for value in explicit):
            parser.error('--toolchain-result cannot be combined with explicit toolchain paths')
    elif not all(value is not None for value in explicit):
        parser.error('Supply --toolchain-result or all explicit toolchain paths')
    print(prepare_build(args)['result'])


if __name__ == '__main__':
    main()
