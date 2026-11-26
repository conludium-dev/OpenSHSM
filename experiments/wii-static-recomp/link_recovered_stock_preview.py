"""Link the retained preview with recovered inputs and an optional verified depth delta."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from stock_gx_renderer_texgen_patch import depth
from stock_vertex_sources_patch import adapt_header
from stock_completed_xfb_patch import renderer as latch_renderer, main as latch_main
from stock_gx_efb_sampling_patch import renderer as efb_renderer, shader as efb_shader, main as efb_main
from stock_ios_negative_fd_patch import adapt as adapt_ios_negative_fd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path):
    build = json.loads(Path(path).read_text())
    assert build['result'] == 'RECOVERED_PREVIEW_LINKED_NOT_GAME_VERIFIED'
    for file, digest in {**build['dependencies'], **build['linkInputs']}.items():
        assert sha(file) == digest, file
    for field in ('executable', 'archive', 'rendererSource'):
        assert sha(build[field]) == build[field + 'Sha256']
    return Path(build['executable'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--depth-proof', type=Path)
    parser.add_argument('--renderer-source', type=Path,
        help='Private diagnostic renderer replacement; never implies game acceptance.')
    parser.add_argument('--shader-source', type=Path,
        help='Private TEV shader generator replacement; requires rebuilding renderer cache key.')
    parser.add_argument('--main-source', type=Path, help='Private host-framebuffer diagnostic replacement.')
    parser.add_argument('--gx-source', type=Path, help='Private GX queue diagnostic replacement.')
    parser.add_argument('--fifo-source', type=Path, help='Private FIFO parser diagnostic replacement.')
    parser.add_argument('--optimize-runtime', action='store_true',
        help='Compile supplied renderer, shader, GX and FIFO replacements with -O2, without fast-math.')
    parser.add_argument('--dc-zero', action='store_true',
        help='Restore the original DCZeroRange dcbz instruction, checked against the owned Wii DOL.')
    parser.add_argument('--lhaux', action='store_true',
        help='Restore Wii-observed indexed signed and unsigned halfword loads in the retained interpreter.')
    parser.add_argument('--negative-ios-fd', action='store_true',
        help='Skip unused vector materialization when the IOS kernel rejects a negative fd.')
    parser.add_argument('--completed-frame', action='store_true',
        help='Latch the existing640x480 host presentation at each XFB copy.')
    parser.add_argument('--efb-sampling', action='store_true',
        help='Apply coupled EFB528 top-origin and SU/image texture sampling correction.')
    parser.add_argument('--desktop-input-sources', type=Path,
        help='Two sources reproduced by the public Wii desktop input recipe.')
    args = parser.parse_args()
    if args.efb_sampling and (not args.renderer_source or not args.shader_source):
        parser.error('--efb-sampling requires --renderer-source and --shader-source.')
    if args.efb_sampling and args.completed_frame:
        parser.error('--efb-sampling is incompatible with the fixed480 completed-frame experiment.')
    if args.depth_proof and args.renderer_source:
        parser.error('Use either --depth-proof or --renderer-source.')
    if args.shader_source and not args.renderer_source:
        parser.error('--shader-source requires --renderer-source to rebuild the cache key.')
    if args.gx_source and not args.renderer_source:
        parser.error('--gx-source requires --renderer-source for the matching vertex source header.')
    if args.fifo_source and not args.renderer_source:
        parser.error('--fifo-source requires --renderer-source for the matching vertex source header.')
    if args.optimize_runtime and not args.renderer_source:
        parser.error('--optimize-runtime requires --renderer-source.')
    preview = args.preview.resolve()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    current = json.loads((preview / 'build.json').read_text())
    launch = json.loads((preview / 'launch.json').read_text())
    assert sha(launch['executable']) == launch['executableSha256']
    assert sha(preview / 'libnwiiruntime.a') == current['archiveSha256']
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    replacements = {}
    for name in ('recovered-inputs', 'recovered-aux'):
        report = json.loads((preview / name / 'recovery.json').read_text())
        for path, digest in report['dependencies'].items():
            assert sha(path) == digest, path
        for row in report['inputs']:
            assert sha(row['sourcePath']) == row['sourceSha256']
            assert sha(row['objectPath']) == row['objectSha256']
            replacements[row['replaces']] = row['objectPath']
    assert len(replacements) == 39
    archive = preview / 'libnwiiruntime.a'
    source_path = preview / 'renderer_gl.cpp'
    if args.depth_proof or args.renderer_source or args.completed_frame:
        source = output / 'renderer_gl.cpp'
        if args.depth_proof:
            proof = json.loads(args.depth_proof.read_text())
            assert proof['result'] == 'GX_DEPTH_ACTUAL_GL_38_PASS_BASELINE_FAIL'
            for path, digest in proof['dependencies'].items():
                assert sha(path) == digest, path
            source.write_text(depth(source_path.read_text()))
            assert sha(source) == proof['runs']['candidate']['sourceSha256']
        else:
            source.write_bytes((args.renderer_source or source_path).read_bytes())
        if args.completed_frame:
            source.write_text(latch_renderer(source.read_text()))
        if args.efb_sampling:
            source.write_text(efb_renderer(source.read_text()))
        header = output / 'runtime/gx/fifo_parser.h'
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text(adapt_header((root / 'export/nWiiRuntime/include/runtime/gx/fifo_parser.h').read_text()))
        recipe = json.loads((root / 'window-pe-execute/build.json').read_text())['changes']['renderer_gl.cpp']
        command = list(recipe['compileCommand'])
        command[1:1] = ['-I', str(output)]
        if args.optimize_runtime:
            command.append('-O2')
        command[command.index('-c') + 1] = str(source)
        obj = output / 'renderer_gl.cpp.o'
        command[command.index('-o') + 1] = str(obj)
        run = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (output / 'compile.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        archive = output / 'libnwiiruntime.a'
        shutil.copy2(preview / 'libnwiiruntime.a', archive)
        subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines():
            if member.startswith('__'):
                continue
            body = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
            expected = obj.read_bytes() if member == obj.name else subprocess.check_output(
                ['/usr/bin/ar', '-p', str(preview / 'libnwiiruntime.a'), member])
            assert body == expected, member
        source_path = source
    if args.shader_source:
        members = {member: subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
            for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()
            if not member.startswith('__')}
        recipe = next(row for row in json.loads((root / 'headless-tev-banks/build.json').read_text())['compiled']
            if row['member'] == 'tev_shader_gen.cpp.o')
        source = output / 'tev_shader_gen.cpp'
        source.write_bytes(args.shader_source.read_bytes())
        if args.efb_sampling:
            source.write_text(efb_shader(source.read_text()))
        obj = output / 'tev_shader_gen.cpp.o'
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *recipe['arguments'],
            '-c', str(source), '-o', str(obj)]
        if args.optimize_runtime:
            command.append('-O2')
        run = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (output / 'shader-compile.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        members[obj.name] = obj.read_bytes()
        for member, expected in members.items():
            assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member]) == expected, member
    for name, replacement, recipe_name in [('gx.cpp', args.gx_source, 'window-pe-cadence'),
            ('fifo_parser.cpp', args.fifo_source, 'window-bp-order')]:
        if not replacement:
            continue
        members = {member: subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
            for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()
            if not member.startswith('__')}
        recipe = json.loads((root / recipe_name / 'build.json').read_text())
        source = output / name
        source.write_bytes(replacement.read_bytes())
        obj = output / (name + '.o')
        command = list(recipe['compileCommand'])
        command[1:1] = ['-I', str(output)]
        if args.optimize_runtime:
            command.append('-O2')
        command[command.index('-c') + 1] = str(source)
        command[command.index('-o') + 1] = str(obj)
        run = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (output / (name + '-compile.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        members[obj.name] = obj.read_bytes()
        for member, expected in members.items():
            assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member]) == expected, member
    link = [replacements.get(value, value) for value in current['linkCommand']]
    if args.main_source or args.completed_frame or args.efb_sampling or args.desktop_input_sources:
        rows = json.loads((preview / 'recovered-aux/recovery.json').read_text())['inputs']
        recipe = next(row for row in rows if Path(row['sourcePath']).name == 'main.cpp')
        source = output / 'main.cpp'
        source.write_bytes((args.main_source or Path(recipe['sourcePath'])).read_bytes())
        if args.completed_frame:
            source.write_text(latch_main(source.read_text()))
        if args.efb_sampling:
            source.write_text(efb_main(source.read_text()))
        if args.desktop_input_sources:
            from stock_desktop_input_host_patch import adapt as desktop_host
            source.write_text(desktop_host(source.read_text()))
        obj = output / 'main.cpp.o'
        command = list(recipe['compileCommand'])
        command[1:1] = ['-I', str(output)]
        command[command.index('-c') + 1] = str(source)
        command[command.index('-o') + 1] = str(obj)
        run = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (output / 'main-compile.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        assert link.count(recipe['objectPath']) == 1
        link[link.index(recipe['objectPath'])] = str(obj)
    dc_zero_dependencies = []
    dc_zero_change = None
    if args.dc_zero:
        from stock_dcbz_lowering import lower_dcbz
        rows = json.loads((preview / 'recovered-aux/recovery.json').read_text())['inputs']
        recipe = next(row for row in rows if Path(row['sourcePath']).name == 'output_38.cpp')
        dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
        assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
        source = output / 'output_38.cpp'
        text, sites = lower_dcbz(Path(recipe['sourcePath']).read_text(), dol.read_bytes(), expected_sites=1)
        assert sites[0]['address'] == 0x8021307C
        source.write_text(text)
        obj = output / 'output_38.cpp.o'
        command = list(recipe['compileCommand'])
        command[command.index('-c') + 1] = str(source)
        command[command.index('-o') + 1] = str(obj)
        run = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (output / 'dc-zero-compile.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        assert link.count(recipe['objectPath']) == 1
        link[link.index(recipe['objectPath'])] = str(obj)
        dc_zero_dependencies = [source, dol, public / 'stock_dcbz_lowering.py']
        dc_zero_change = {'sites': sites, 'compileCommand': command,
            'originalSourceSha256': recipe['sourceSha256'], 'objectSha256': sha(obj)}
    lhaux_dependencies = []
    lhaux_change = None
    if args.lhaux:
        from stock_interpreter_reached_ops import adapt as reached_interpreter
        from stock_interpreter_lhaux import SITES, WORD, LHZUX_SITE, LHZUX_WORD, adapt as lower_lhaux, check_dol
        base = root / 'interpreter-addze-corrected/interpreter.cpp'
        dol = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
        assert sha(base) == '8efe126aed047c17cbd12accc8406576d7a7f7d0ce5da3679f214a63e985a26d'
        assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
        check_dol(dol.read_bytes())
        prior = reached_interpreter(base.read_text())
        assert hashlib.sha256(prior.encode()).hexdigest() == '7715ddc06412fd7f57413baa45f725d5d9e6bb90dbdb68ea88f589bbf5b2b5d7'
        member = subprocess.check_output(['/usr/bin/ar', '-p', str(preview / 'libnwiiruntime.a'),
            'interpreter.cpp.o'])
        assert hashlib.sha256(member).hexdigest() == '42c26b6e55c225202eb695cc5067e267c54795830799819b479fd4908f7dfa58'
        source = output / 'interpreter.cpp'
        source.write_text(lower_lhaux(prior))
        obj = output / 'interpreter.cpp.o'
        arguments = json.loads((root / 'window-fp-guard/build.json').read_text())['interpreterArguments']
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
            '-c', str(source), '-o', str(obj)]
        run = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
        (output / 'interpreter-compile.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr[-3000:]
        if archive == preview / 'libnwiiruntime.a':
            archive = output / 'libnwiiruntime.a'
            shutil.copy2(preview / 'libnwiiruntime.a', archive)
        retained_members = {name: subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
            for name in subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()
            if name != obj.name and not name.startswith('__')}
        subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive), obj.name]) == obj.read_bytes()
        for name, expected in retained_members.items():
            assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name]) == expected, name
        lhaux_dependencies = [base, dol, public / 'stock_interpreter_reached_ops.py',
            public / 'stock_interpreter_lhaux.py', root / 'window-fp-guard/build.json']
        lhaux_change = {'sites': [hex(address) for address in SITES], 'opcode': hex(WORD),
            'lhzuxSite': hex(LHZUX_SITE), 'lhzuxOpcode': hex(LHZUX_WORD),
            'sourceSha256': sha(source), 'objectSha256': sha(obj), 'compileCommand': command,
            'retainedRuntimeMembers': {name: hashlib.sha256(body).hexdigest()
                for name, body in retained_members.items()}}
    desktop_dependencies = []
    desktop_change = None
    if args.desktop_input_sources:
        source_dir = args.desktop_input_sources.resolve(strict=True)
        manifest_path = public / 'stock-desktop-input-runtime-wii-us-r5wea4-rev0.json'
        manifest = json.loads(manifest_path.read_text())
        if manifest['gameId'] != 'R5WEA4' or manifest['revision'] != 0:
            raise ValueError('Desktop input manifest is for another Wii copy')
        source_names = ('mouse_keyboard_source.cpp', 'gamepad_source.cpp')
        for name in source_names:
            fingerprint = manifest['files'][name]
            path = source_dir / name
            if path.stat().st_size != fingerprint['bytes'] or sha(path) != fingerprint['sha256']:
                raise ValueError(f'Desktop input source differs: {name}')
        if archive == preview / 'libnwiiruntime.a':
            archive = output / 'libnwiiruntime.a'
            shutil.copy2(preview / 'libnwiiruntime.a', archive)
        recipe = json.loads((root / 'window-quantization/build.json').read_text())
        objects = {}
        for name in source_names:
            row = next(item for item in recipe['compiled'] if item['source'] == name)
            obj = output / (name + '.o')
            command = ['/Library/Developer/CommandLineTools/usr/bin/c++',
                *row['arguments'], '-c', str(source_dir / name), '-o', str(obj)]
            run = subprocess.run(command, cwd=root / 'export/build',
                capture_output=True, text=True, timeout=120)
            (output / (name + '-compile.log')).write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(f'{name} compile failed: {run.stderr[-3000:]}')
            objects[name] = {'sourceSha256': sha(source_dir / name),
                'objectSha256': sha(obj), 'compileCommand': command}
            subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)],
                check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        for name in source_names:
            obj = output / (name + '.o')
            if subprocess.check_output(['/usr/bin/ar', '-p', str(archive), obj.name]) != obj.read_bytes():
                raise RuntimeError(f'Desktop input archive member differs: {name}')
        guest_source = root / 'window-input-sdk/output_44.cpp'
        guest_recipe_path = root / 'window-input-sdk/output_44.cpp.cache.json'
        guest_recipe = json.loads(guest_recipe_path.read_text())
        if sha(guest_source) != guest_recipe['key']['sourceSha256']:
            raise ValueError('Input guest source differs')
        guest_obj = output / 'output_44.cpp.o'
        guest_command = ['/Library/Developer/CommandLineTools/usr/bin/c++',
            *guest_recipe['key']['arguments'], '-c', str(guest_source),
            '-o', str(guest_obj)]
        run = subprocess.run(guest_command, cwd=root / 'export/build',
            capture_output=True, text=True, timeout=180)
        (output / 'desktop-output_44-compile.log').write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError(f'Input guest compile failed: {run.stderr[-3000:]}')
        old_guest = next(value for value in link if value.endswith('/output_44.cpp.o'))
        link[link.index(old_guest)] = str(guest_obj)
        desktop_change = {'runtimeObjects': objects, 'guestObjectSha256': sha(guest_obj),
            'guestCompileCommand': guest_command}
        desktop_dependencies = [manifest_path, public / 'stock_desktop_input_patch.py',
            public / 'stock_desktop_input_host_patch.py',
            public / 'stock_input_sample_bridge.h', public / 'stock_input_sdk_bridge.h',
            source_dir / source_names[0], source_dir / source_names[1],
            guest_source, guest_recipe_path, root / 'window-quantization/build.json']
    negative_ios_dependencies = []
    negative_ios_change = None
    if args.negative_ios_fd:
        stock_source = root / 'export/nWiiRuntime/src/platform/wii_platform.cpp'
        stock_manifest = public / 'stock-export-wii-us-r5wea4-rev0.json'
        expected = json.loads(stock_manifest.read_text())['runtime']['src/platform/wii_platform.cpp']
        if stock_source.stat().st_size != expected['bytes'] or sha(stock_source) != expected['sha256']:
            raise ValueError('Stock Wii platform source differs')
        recipe_path = root / 'window-quantization/build.json'
        recipe = next(row for row in json.loads(recipe_path.read_text())['compiled']
            if row['source'] == 'wii_platform.cpp')
        original = subprocess.check_output(['/usr/bin/ar', '-p', str(preview / 'libnwiiruntime.a'),
            'wii_platform.cpp.o'])
        if hashlib.sha256(original).hexdigest() != recipe['objectSha256']:
            raise ValueError('Retained Wii platform object differs')
        source = output / 'wii_platform.cpp'
        source.write_text(adapt_ios_negative_fd(stock_source.read_text()))
        core_manifest = public / 'stock-core-runtime-wii-us-r5wea4-rev0.json'
        core_expected = json.loads(core_manifest.read_text())['outputs']['src/platform/wii_platform.cpp']
        if source.stat().st_size != core_expected['bytes'] or sha(source) != core_expected['sha256']:
            raise ValueError('Adapted Wii platform source differs')
        obj = output / 'wii_platform.cpp.o'
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++',
            *recipe['arguments'], '-c', str(source), '-o', str(obj)]
        run = subprocess.run(command, cwd=root / 'export/build',
            capture_output=True, text=True, timeout=120)
        (output / 'wii-platform-compile.log').write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError(f'Wii platform compile failed: {run.stderr[-3000:]}')
        if archive == preview / 'libnwiiruntime.a':
            archive = output / 'libnwiiruntime.a'
            shutil.copy2(preview / 'libnwiiruntime.a', archive)
        retained_members = {name: subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
            for name in subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines()
            if name != obj.name and not name.startswith('__')}
        subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
        if subprocess.check_output(['/usr/bin/ar', '-p', str(archive), obj.name]) != obj.read_bytes():
            raise RuntimeError('Wii platform archive member differs')
        for name, body in retained_members.items():
            if subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name]) != body:
                raise RuntimeError(f'Unrelated runtime member changed: {name}')
        negative_ios_change = {'sourceSha256': sha(source), 'objectSha256': sha(obj),
            'compileCommand': command, 'retainedRuntimeMembers': len(retained_members)}
        negative_ios_dependencies = [stock_source, stock_manifest, core_manifest,
            public / 'stock_ios_negative_fd_patch.py', recipe_path]
    link[link.index(current['archive'])] = str(archive)
    exe = output / 'OpenSHSM-0.0.42'
    link[link.index('-o') + 1] = str(exe)
    retained = {}
    for value in link:
        if value.endswith(('.o', '.a')):
            path = Path(value) if Path(value).is_absolute() else root / 'export/build' / value
            assert path.is_file(), path
            retained[str(path.resolve())] = sha(path)
    run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    (output / 'link.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stderr[-4000:]
    report = {'result': 'RECOVERED_PREVIEW_LINKED_NOT_GAME_VERIFIED',
        'executable': str(exe), 'executableSha256': sha(exe), 'archive': str(archive),
        'archiveSha256': sha(archive), 'rendererSource': str(source_path),
        'rendererSourceSha256': sha(source_path), 'linkCommand': link, 'linkInputs': retained,
        'completedFrame': args.completed_frame, 'efbSampling': args.efb_sampling,
        'optimizedRuntime': args.optimize_runtime,
        'dcZero': dc_zero_change,
        'lhaux': lhaux_change,
        'negativeIosFd': negative_ios_change,
        'desktopInput': desktop_change,
        'depthFix': bool(args.depth_proof), 'recoveredInputs': replacements,
        'dependencies': {str(p.resolve()): sha(p) for p in [Path(__file__), *dc_zero_dependencies,
            *lhaux_dependencies, *desktop_dependencies, *negative_ios_dependencies,
            preview / 'build.json', preview / 'recovered-inputs/recovery.json',
            preview / 'recovered-aux/recovery.json', public / 'stock_gx_renderer_texgen_patch.py',
            public / 'stock_gx_shader_key.h',
            *([args.depth_proof] if args.depth_proof else []),
            *([args.main_source] if args.main_source else []),
            *([args.gx_source, public / 'stock_gx_completed_frame.h', public / 'stock_gx_completion.h',
                public / 'stock_pe_cadence_observation.h', root / 'window-pe-cadence/build.json']
                if args.gx_source else []),
            *([args.fifo_source, public / 'stock_gx_vertex_sources.h',
                root / 'window-bp-order/build.json'] if args.fifo_source else []),
            *([public / 'stock_gx_display_list_memory.h', public / 'stock_gx_display_list_memory_patch.py']
                if any(p and '"stock_gx_display_list_memory.h"' in p.read_text()
                    for p in (args.gx_source, args.fifo_source)) else []),
            *([public / 'stock_completed_xfb_patch.py'] if args.completed_frame else []),
            *([public / 'stock_gx_efb_sampling_patch.py', public / 'stock_gx_texture_sampling_patch.py',
                public / 'stock_gx_sampler_patch.py']
                if args.efb_sampling else []),
            *([args.renderer_source] if args.renderer_source else []),
            *([public / 'stock_gx_replay_capture.h'] if args.renderer_source and
                '"stock_gx_replay_capture.h"' in args.renderer_source.read_text() else []),
            *([args.shader_source, root / 'headless-tev-banks/build.json'] if args.shader_source else [])]},
        'limits': ['Uses the preserved full runtime archive with verified optional member changes.',
            'Recovered source recipes are verified; full runtime, cutscene and performance acceptance pending.']}
    (output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], exe, flush=True)


if __name__ == '__main__':
    main()
