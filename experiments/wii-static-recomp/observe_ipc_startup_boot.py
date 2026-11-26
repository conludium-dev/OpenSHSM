"""Observe the exact original IPC indexed store, delegating the unchanged guard."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_si_queue_boot.py')
source = parent.read_text().replace('mass-si-queue-boot', 'mass-ipc-startup-observer')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
old = '''for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']'''
new = '''records = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'output_67.cpp':
        original_source = Path(row['source']).read_text()
        before = '    // 0x80241C38: 7C83012E\\n    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + ctx.gpr[0], ctx.gpr[4]); // stwx'
        after = before.replace('bat_memory_write32', 'experiment_ipc_startup_observe_store')
        assert original_source.count(before) == 1
        target = output / row['file']
        target.write_text(original_source.replace(before, after))
        obj = output / (row['file'] + '.o')
        compile_result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0',
            '-include', str(output / 'finite_mem2_clear.h'), '-include', str(experiment / 'ipc_startup_observer.h'),
            '-DSHSM_SI_EXTERNAL_DELIVERY', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
            '-I', str(runtime / 'include'), '-c', str(target), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'observer-compile.log').write_text(compile_result.stdout + compile_result.stderr)
        assert compile_result.returncode == 0, compile_result.stderr[-3000:]
        record.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
    records.append(record)
build['records'] = records'''
source = source.replace(marker, "body = body.replace(\"base = private / 'mass-finite-mem2-boot'\", \"base = private / 'mass-si-resume-boot'\")\nbody = body.replace(\"base / 'boot.json'\", \"base / 'build.json'\")\nbody = body.replace(" + repr(old) + ", " + repr(new) + ")\n" + marker)
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ipc-startup-observer')
path = output / 'build.json'
report = json.loads(path.read_text())
report['sourceHashes']['experiments/wii-static-recomp/ipc_startup_observer.h'] = hashlib.sha256(Path('experiments/wii-static-recomp/ipc_startup_observer.h').read_bytes()).hexdigest()
report['limits'].append('One original store seam observed then delegated unchanged BAT guard; no IPC permission or registers altered.')
path.write_text(json.dumps(report, indent=2) + '\n')
print('\n'.join(line for line in (output / 'observed-boot.log').read_text().splitlines() if line.startswith('IPC_STARTUP_')))
