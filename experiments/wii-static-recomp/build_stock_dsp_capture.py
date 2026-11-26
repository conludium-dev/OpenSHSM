"""Instrument only the current DSP member; keep all existing audio/CPU/display policies."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from stock_dsp_capture_patch import adapt
from build_stock_sysconf import execute


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--component', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).resolve().parent
    root = public.parents[1] / 'work/private-game/static-recomp/stock-baseline'
    parent = json.loads(args.parent.read_text())
    assert sha(parent['executablePath']) == parent['executableSha256']
    component = json.loads(args.component.read_text())
    assert component['result'] == 'BOUNDED_DSP_CAPTURE_COMPONENT_PASS'
    for path, digest in component['dependencies'].items():
        assert sha(path) == digest
    original = root / 'window-adma-deadline/hw_dsp.cpp'
    record = json.loads((original.parent / 'build.json').read_text())
    assert sha(original) == record['sourceSha256']
    previous = Path(parent['archivePath'])
    assert sha(previous) == parent['archiveSha256']
    original_object = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), 'hw_dsp.cpp.o'])
    assert hashlib.sha256(original_object).hexdigest() == record['objectSha256']
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-capture-build-', dir='/private/tmp'))
    source = cache / 'hw_dsp.cpp'
    source.write_text(adapt(original.read_text()))
    shutil.copy2(public / 'stock_dsp_capture.h', cache / 'stock_dsp_capture.h')
    for name in ('stock_axwii_commands.h', 'stock_axwii_pb.h'):
        shutil.copy2(public / name, cache / name)
    shutil.copy2(original.parent / 'stock_adma_output.h', cache / 'stock_adma_output.h')
    full = json.loads((root / 'window-quantization/build.json').read_text())
    args_dsp = next(row['arguments'] for row in full['compiled'] if row['source'] == 'hw_dsp.cpp')
    arguments = ['-I', str(original.parent / 'include'), *args_dsp]
    compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
    obj = cache / 'hw_dsp.cpp.o'
    compile_command = [compiler, '-H', *arguments, '-c', str(source), '-o', str(obj)]
    execute(compile_command, root / 'export/build', cache / 'compile.log')
    assert str(cache / 'stock_dsp_capture.h') in (cache / 'compile.log').read_text()
    for name in ('stock_axwii_commands.h', 'stock_axwii_pb.h'):
        assert str(cache / name) in (cache / 'compile.log').read_text()
    assert str(cache / 'stock_adma_output.h') in (cache / 'compile.log').read_text()
    archive = cache / previous.name
    shutil.copy2(previous, archive)
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
    subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
    retained = {}
    for member in subprocess.check_output(['/usr/bin/ar', 't', str(previous)], text=True).splitlines():
        if member.startswith('__.SYMDEF') or member == obj.name:
            continue
        before = subprocess.check_output(['/usr/bin/ar', '-p', str(previous), member])
        assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        retained[member] = hashlib.sha256(before).hexdigest()
    command = list(parent['linkCommand'])
    command[command.index(str(previous))] = str(archive)
    exe = cache / 'OpenSHSM-0.0.42'
    command[command.index('-o') + 1] = str(exe)
    execute(command, root / 'export/build', cache / 'link.log')
    probe = public / 'stock_dsp_mail_probe.cpp'
    probe_obj = cache / 'probe.cpp.o'
    probe_args = json.loads((root / 'input-snapshot-research/build.json').read_text())['arguments']
    execute([compiler, *probe_args, '-c', str(probe), '-o', str(probe_obj)],
        root / 'export/build', cache / 'probe-compile.log')
    probe_command = list(command)
    main_obj = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    probe_command[probe_command.index(main_obj)] = str(root / 'window-quantization/contract-entry.cpp.o')
    probe_command.insert(1, str(probe_obj))
    runs = {}
    env = {key: value for key, value in os.environ.items() if key != 'OPENSHSM_DSP_CAPTURE_DIR'}
    for name, runtime, enabled in [('baseline', previous, False), ('disabled', archive, False), ('enabled', archive, True)]:
        cmd = list(probe_command)
        cmd[cmd.index(str(archive))] = str(runtime)
        probe_exe = cache / (name + '-probe')
        cmd[cmd.index('-o') + 1] = str(probe_exe)
        execute(cmd, root / 'export/build', cache / (name + '-link.log'))
        current_env = dict(env)
        if enabled:
            sink = cache / 'probe-capture'
            sink.mkdir()
            current_env['OPENSHSM_DSP_CAPTURE_DIR'] = str(sink)
        run = subprocess.run([str(probe_exe)], env=current_env, capture_output=True, text=True, timeout=20)
        (cache / (name + '-run.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and 'CURRENT_DSP_MAIL_ACK_WITHOUT_LIST_EXECUTION_REPRODUCED' in run.stdout
        runs[name] = {'output': run.stdout.strip(), 'executableSha256': sha(probe_exe), 'linkCommand': cmd}
    assert runs['baseline']['output'] == runs['disabled']['output'] == runs['enabled']['output']
    captured = [json.loads(line) for line in (cache / 'probe-capture/dsp-events.jsonl').read_text().splitlines()]
    lists = [row for row in captured if row['kind'] == 'list']
    assert len(lists) == 3 and [row['saved'] for row in lists] == [True, True, False]
    report = {'result': 'BOUNDED_DSP_CAPTURE_CURRENT_RUNTIME_COMPONENT_PASS_NOT_LIVE_VERIFIED',
        'parentBuildPath': str(args.parent.resolve()), 'parentBuildSha256': sha(args.parent),
        'componentPath': str(args.component.resolve()), 'componentSha256': sha(args.component),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'originalSourcePath': str(original), 'originalSourceSha256': sha(original),
        'originalObjectSha256': record['objectSha256'], 'archivePath': str(archive), 'archiveSha256': sha(archive),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'compileCommand': compile_command,
        'linkCommand': command, 'retainedRuntimeMembers': retained, 'runs': runs,
        'retainedLinkInputs': {arg: sha(arg) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
        'dependencies': {str(path): sha(path) for path in [Path(__file__), public / 'stock_dsp_capture.h',
            public / 'stock_axwii_commands.h', public / 'stock_axwii_pb.h',
            public / 'stock_dsp_capture_patch.py', probe, original.parent / 'build.json',
            original.parent / 'stock_adma_output.h', original.parent / 'include/runtime/event_scheduler.h']},
        'limits': ['Diagnostic only; existing ACK-only adapter remains unchanged/not accepted as original mixer.',
            'Defaultdisabled; boundedcapture enabled only in explicit private directory; no performance acceptance.',
            'All other runtime/guest/main/currentSYSCONF/CPU corrections retained; no currentprocess mutation.',
            'No liveoriginalcommandlist/ucode/PB identity or voice/audio improvement proof yet.']}
    path = cache / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
