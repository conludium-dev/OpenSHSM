"""Add one owned-DOL-verified IRQ continuation to the existing generated dispatcher."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_si_queue_boot.py')
source = parent.read_text().replace('mass-si-queue-boot', 'mass-si-resume-boot')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
old = '''for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']'''
new = '''records = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'main_output.cpp':
        dispatcher = Path(row['source']).read_text()
        marker = '            case 0x80217500: func_80217500(ctx); break;'
        added = '            case 0x8021750C: func_80217500(ctx); break;'
        assert dispatcher.count(marker) == 1 and added not in dispatcher
        target = output / 'main_output.cpp'
        target.write_text(dispatcher.replace(marker, marker + '\\n' + added))
        obj = output / 'main_output.cpp.o'
        compile_result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0',
            '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment),
            '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
            '-c', str(target), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'dispatch-compile.log').write_text(compile_result.stdout + compile_result.stderr)
        assert compile_result.returncode == 0, compile_result.stderr[-3000:]
        record.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
    records.append(record)
build['records'] = records'''
source = source.replace(marker, "body = body.replace(" + repr(old) + ", " + repr(new) + ")\n" + marker)
exec(compile(source, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-si-resume-boot/build.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Only8021750CIRQ continuation added to existing dispatcher; oversized other bounds remain unresolved.')
path.write_text(json.dumps(report, indent=2) + '\n')
