"""Bind ordered replies to the actual retained DSP MMIO implementation, without a game launch."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from build_stock_sysconf import execute
from stock_dsp_replies_patch import adapt
from stock_debug_font_build import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dsp-build', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    parser.add_argument('--mixer-evidence', type=Path)
    args = parser.parse_args()
    build = json.loads(args.dsp_build.read_text())
    assert build['result'] == 'BOUNDED_DSP_CAPTURE_CURRENT_RUNTIME_COMPONENT_PASS_NOT_LIVE_VERIFIED'
    for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(path) == digest, path
    assert sha(build['sourcePath']) == build['sourceSha256']
    assert sha(build['archivePath']) == build['archiveSha256']
    proof = json.loads(args.component.read_text())
    assert proof['result'] == 'DSP_REPLIES_PINNED_REFERENCE_PASS'
    for path, digest in proof['dependencies'].items():
        assert sha(path) == digest, path
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-replies-runtime-', dir='/private/tmp'))
    source = cache / 'hw_dsp.cpp'
    patch = adapt
    firmware_path = None
    if args.mixer_evidence:
        from stock_axwii_device_patch import adapt as adapt_device
        patch = adapt_device
        evidence = json.loads(args.mixer_evidence.read_text())
        for path, digest in evidence['dependencies'].items():
            assert sha(path) == digest, path
        firmware = evidence['liveRAMFirmwareCandidate']
        assert firmware['exactOwnedDOLCandidateMatch'] and firmware['ectorHash'] == '4CC52064'
        firmware_path = Path(firmware['path'])
        assert sha(firmware_path) == firmware['sha256']
    source.write_text(patch(Path(build['sourcePath']).read_text()))
    for name in ('stock_dsp_capture.h', 'stock_axwii_commands.h', 'stock_axwii_pb.h', 'stock_adma_output.h'):
        shutil.copy2(args.dsp_build.parent / name, cache / name)
    shutil.copy2(public / 'stock_dsp_replies.h', cache / 'stock_dsp_replies.h')
    if args.mixer_evidence:
        for header in public.glob('stock_axwii_*.h'):
            shutil.copy2(header, cache / header.name)
    recipe = json.loads((root / 'input-snapshot-research/build.json').read_text())
    probe = public / ('stock_axwii_device_probe.cpp' if args.mixer_evidence else 'stock_dsp_replies_runtime_probe.cpp')
    obj = cache / 'probe.cpp.o'
    compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
    command = [compiler, '-H', '-I', str(cache), '-I', str(public),
        '-I', str(Path(build['originalSourcePath']).parent / 'include'), *recipe['arguments'],
        '-c', str(probe), '-o', str(obj)]
    execute(command, root / 'export/build', cache / 'compile.log')
    log = (cache / 'compile.log').read_text()
    assert str(source) in log and str(cache / 'stock_dsp_replies.h') in log
    link = list(build['linkCommand'])
    main = next(path for path in link if Path(path).name == 'main.cpp.o')
    link[link.index(main)] = str(root / 'window-quantization/contract-entry.cpp.o')
    link.insert(1, str(obj))
    exe = cache / 'probe'
    link[link.index('-o') + 1] = str(exe)
    execute(link, root / 'export/build', cache / 'link.log')
    env = {key: value for key, value in os.environ.items() if key != 'OPENSHSM_DSP_CAPTURE_DIR'}
    argv = [str(exe), str(firmware_path)] if firmware_path else [str(exe)]
    run = subprocess.run(argv, cwd=root / 'export/build', env=env,
        capture_output=True, text=True, timeout=20)
    (cache / 'run.log').write_text(run.stdout + run.stderr)
    expected = 'CURRENT_AXWII_DEVICE_MMIO_PCM_PASS' if args.mixer_evidence else 'CURRENT_DSP_ORDERED_REPLY_MMIO_PASS'
    assert run.returncode == 0 and expected in run.stdout, (run.returncode, run.stdout, run.stderr)
    guards = {}
    if args.mixer_evidence:
        for mode in ('disabled', 'firmware', 'coefficients', 'address'):
            guard = subprocess.run([str(exe), str(firmware_path), mode], cwd=root / 'export/build',
                env=env, capture_output=True, text=True, timeout=20)
            (cache / (mode + '-run.log')).write_text(guard.stdout + guard.stderr)
            assert guard.returncode == 0 and 'CURRENT_AXWII_DEVICE_GUARD_PASS ' + mode in guard.stdout, (mode, guard.returncode, guard.stdout, guard.stderr)
            guards[mode] = {'output': guard.stdout.strip(), 'diagnostic': guard.stderr.strip()}
    report = {'result': expected + '_NOT_GAME_AUDIO',
        'dspBuildPath': str(args.dsp_build), 'dspBuildSha256': sha(args.dsp_build),
        'componentPath': str(args.component), 'componentSha256': sha(args.component),
        'output': run.stdout.strip(), 'guards': guards, 'compileCommand': command, 'linkCommand': link,
        'sourcePath': str(source), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
        'dependencies': {str(path): sha(path) for path in [Path(__file__), probe,
            public / 'stock_dsp_replies.h', public / 'stock_dsp_replies_patch.py',
            Path(build['sourcePath']), *[path for path in cache.iterdir() if path.suffix == '.h']]},
        'limits': ['Actual retained DSP producer/consumer compiled in probe translation unit with retained runtime archive.',
            'Direct internal two-reply injection; no actual AX command mixer/firmware/game execution.',
            'SYNC4 thenYIELD2 preserved; low-read clears old DSP IRQ before raising deferred next IRQ.',
            'Existing1ms scheduled reply policy retained, not physicalWii or pinned2500cycle timing acceptance.',
            'No game/window/asset/config/release or existing executable changed.']}
    path = cache / 'verification.json'
    if args.mixer_evidence:
        report['mixerEvidencePath'] = str(args.mixer_evidence)
        report['mixerEvidenceSha256'] = sha(args.mixer_evidence)
        for dependency in [firmware_path, public / 'stock_axwii_device_patch.py',
                *public.glob('stock_axwii_*.h')]:
            report['dependencies'][str(dependency)] = sha(dependency)
        report['limits'] = ['Actual retained DSP MMIO mailbox/scheduler/RAM with opt-in mixer, same ADMA path unchanged.',
            'Owned live firmware snapshot exact DOL match; synthetic PB/sample data using captured format/addresses/nearest0 configuration.',
            'Two sequential setup/LR/process/compressor(no-trigger)/WM/output jobs verify nonzero stereo PCM/PB writeback and SYNC4-before-YIELD2.',
            'Expected synthetic PCM/ramp manually calculated; pinned algorithm equivalence remains prior component evidence, not original Wii full-job acceptance.',
            'Fixed standard32/64MB sample masks with backed24/64MB bounds are adapter assumptions; actual captured MEM2 addresses are in range.',
            'Polyphase/remote processing uses the generated free Dolphin coefficient replacement; not original DROM accuracy.',
            'Separate-process disabled/unknownfirmware/invalid-coefficient-bank/invalidRAM checks preserve PCM/PB and emit no false SYNC; refusal stops context explicitly.',
            'No game build/window/live dialogue/render acceptance; exact IRQ timing and physical hardware unverified.']
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
