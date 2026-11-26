"""Exercise the current private guest KPAD entry with the pause-input archive, headless."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile

from stock_debug_font_build import sha
from stock_pause_input_validation import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pause-input-build', type=Path, required=True)
    args = parser.parse_args()
    build_path = args.pause_input_build.resolve()
    build = json.loads(build_path.read_text())
    validate(build_path, Path(build['rendererBuildPath']), Path(build['rendererGlProofPath']))
    project = Path(__file__).resolve().parents[2]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    sdk_build = json.loads((root / 'window-input-sdk/build.json').read_text())
    guest = next(Path(item) for item in build['linkCommand'] if item.endswith('output_44.cpp.o'))
    expected = next(item['objectSha256'] for item in sdk_build['compiled'] if item['source'] == 'output_44.cpp')
    assert sha(guest) == expected
    original_main = next(item for item in build['linkCommand'] if item.endswith('main.cpp.o'))
    contract = root / 'window-quantization/contract-entry.cpp.o'
    assert contract.is_file()
    source = Path(__file__).with_name('stock_pause_kpad_probe.cpp')
    manager = build['replacements']['input_manager.cpp.o']
    compile_command = manager['compileCommand']
    assert compile_command[-4:] == ['-c', manager['sourcePath'], '-o', manager['objectPath']]
    output = Path(tempfile.mkdtemp(prefix='openshsm-pause-kpad-', dir='/private/tmp'))
    obj = output / 'probe.cpp.o'
    command = [*compile_command[:-4], '-c', str(source), '-o', str(obj)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-4000:]
    link = list(build['linkCommand'])
    link[link.index(original_main)] = str(contract)
    link.insert(1, str(obj))
    exe = output / 'probe'
    link[link.index('-o') + 1] = str(exe)
    linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    (output / 'link.log').write_text(linked.stdout + linked.stderr)
    assert linked.returncode == 0, linked.stderr[-4000:]
    tested = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (output / 'run.log').write_text(tested.stdout + tested.stderr)
    assert tested.returncode == 0 and 'PAUSE_KPAD_GUEST_HEADLESS_PASS' in tested.stdout, (
        tested.returncode, tested.stdout, tested.stderr)
    report = {'result': 'PAUSE_KPAD_GUEST_HEADLESS_PASS_NOT_GAME_VERIFIED',
        'pauseInputBuildPath': str(build_path), 'pauseInputBuildSha256': sha(build_path),
        'guestObjectPath': str(guest), 'guestObjectSha256': sha(guest),
        'probeSourcePath': str(source), 'probeSourceSha256': sha(source),
        'probeObjectSha256': sha(obj), 'executableSha256': sha(exe),
        'runLogSha256': sha(output / 'run.log'), 'compileCommand': command, 'linkCommand': link,
        'limits': ['Actual compiled guest KPADReadEx entry, original button helper and current private pause-input archive.',
            'Constructed CPU context and input source only; no game scene, pause menu, audio, window or controller hardware tested.']}
    path = output / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
