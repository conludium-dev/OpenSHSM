"""Build only AX DSP; retain current main/font/guest/CPU/SYSCONF/ADMA unchanged."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from build_stock_sysconf import execute
from stock_axwii_device_patch import adapt
from stock_axwii_device_build import validate
from stock_debug_font_build import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--dsp-build', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    args = parser.parse_args()
    parent_path, dsp_path = args.parent.resolve(), args.dsp_build.resolve()
    parent, dsp = json.loads(parent_path.read_text()), json.loads(dsp_path.read_text())
    assert parent['result'] == 'DEBUG_FONT_CURRENT_MAIN_COMPILED_NOT_LIVE_VERIFIED'
    assert parent['archivePath'] == dsp['archivePath']
    for file, digest in {**parent['dependencies'], **parent['retainedLinkInputs'], **dsp['dependencies']}.items():
        assert sha(file) == digest, file
    assert sha(parent['executablePath']) == parent['executableSha256']
    proof = json.loads(args.component.read_text())
    assert proof['result'] == 'CURRENT_AXWII_DEVICE_MMIO_PCM_PASS_NOT_GAME_AUDIO'
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest, file
    assert sha(dsp['sourcePath']) == dsp['sourceSha256']
    previous = Path(parent['archivePath'])
    assert sha(previous) == parent['archiveSha256'] == dsp['archiveSha256']
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-device-build-', dir='/private/tmp'))
    source, obj = cache / 'hw_dsp.cpp', cache / 'hw_dsp.cpp.o'
    source.write_text(adapt(Path(dsp['sourcePath']).read_text()))
    assert sha(source) == proof['sourceSha256']
    headers = ['stock_dsp_capture.h', 'stock_adma_output.h', 'stock_dsp_replies.h']
    headers += sorted(path.name for path in public.glob('stock_axwii_*.h'))
    for name in headers:
        original = dsp_path.parent / name if name in ('stock_dsp_capture.h', 'stock_adma_output.h') else public / name
        shutil.copy2(original, cache / name)
    command = list(dsp['compileCommand'])
    command[command.index(dsp['sourcePath'])] = str(source)
    command[command.index('-o') + 1] = str(obj)
    execute(command, root / 'export/build', cache / 'compile.log')
    archive = cache / previous.name
    shutil.copy2(previous, archive)
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
    subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
    retained = {}
    for member in subprocess.check_output(['/usr/bin/ar', 't', str(previous)], text=True).splitlines():
        if member.startswith('__.SYMDEF') or member == obj.name:
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), member])
        assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        retained[member] = hashlib.sha256(before).hexdigest()
    link = list(parent['linkCommand'])
    link[link.index(str(previous))] = str(archive)
    exe = cache / 'OpenSHSM-0.0.42'
    link[link.index('-o') + 1] = str(exe)
    execute(link, root / 'export/build', cache / 'link.log')
    report = {'result': 'AXWII_DEVICE_CURRENT_DSP_COMPILED_NOT_LIVE_VERIFIED',
        'parentBuildPath': str(parent_path), 'parentBuildSha256': sha(parent_path),
        'dspBuildPath': str(dsp_path), 'dspBuildSha256': sha(dsp_path),
        'componentPath': str(args.component.resolve()), 'componentSha256': sha(args.component),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
        'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'copiedHeaders': headers,
        'compileCommand': command, 'linkCommand': link, 'retainedRuntimeMembers': retained,
        'retainedLinkInputs': {file: sha(file) for file in parent['linkCommand']
            if Path(file).is_file() and Path(file).suffix in ('.o', '.a') and file != str(previous)},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), public / 'stock_axwii_device_build.py',
            public / 'stock_axwii_device_patch.py', public / 'stock_dsp_replies_patch.py',
            *[public / name for name in headers if (public / name).is_file()]]},
        'limits': ['SoleDSPmember derivative; current font/main/75guest objects/44other runtime members retained.',
            'Opt-in recognized4CC mixer; missing DROM/polyphase/remote voices refuse, not full game audio acceptance.',
            'No timer/input/config reset or game asset changes; actual game launch/listening still pending.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    validate(path, parent_path, parent, dsp_path)
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
