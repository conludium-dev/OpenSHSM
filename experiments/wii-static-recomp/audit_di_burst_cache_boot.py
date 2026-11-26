"""Audit original DI86 callback/lifetime and native ES return with LAB cache rule."""
from pathlib import Path
import base64
import json

parent = Path('experiments/wii-static-recomp/audit_di_burst_sender_boot.py')
body = parent.read_text().split("assert [line for line in live.splitlines()", 1)[0]
body = body.replace('mass-di-burst-sender-boot', 'mass-di-burst-cache-boot').replace(
    'build_di_burst_sender_boot.py', 'build_di_burst_cache_boot.py').replace(
    'verify_di_burst_events_dolphin.py', 'verify_di_cache_events_dolphin.py').replace(
    'verify_di_burst_sender_guard.py', 'verify_di_burst_cache_guard.py')
body = body.replace("assert row['file'] == old['file'] and row['sourceSha256'] == old['sourceSha256']",
    "assert row['file'] == old['file']\n    if row['file'] not in ('output_63.cpp', 'output_68.cpp'):\n        assert row['sourceSha256'] == old['sourceSha256']")
body = body.replace("('output_62.cpp', 'output_65.cpp', 'output_67.cpp')", "('output_62.cpp', 'output_63.cpp', 'output_65.cpp', 'output_67.cpp', 'output_68.cpp')")
exec(compile(body, str(parent), 'exec'), globals())
subprocess.run(['python3', str(experiment / 'verify_ipc_control_dolphin.py')], check=True)
assert (output / 'di_burst_cache_adapter.h').read_bytes() == (experiment / 'di_burst_cache_adapter.h').read_bytes()
for name, old_text, new_text in [
    ('output_63.cpp', 'nwii::runtime::bat_memory_cache_operation(ctx, ctx.gpr[3], 470);',
        'nwii::runtime::experiment_di_burst_cache_operation(ctx, ctx.gpr[3], 470);'),
    ('output_68.cpp', 'loc_802497D4: ;',
        'loc_802497D4: ;\n    nwii::runtime::experiment_di_burst_es_return_observe(ctx);')]:
    old_row = next(row for row in previous['records'] if row['file'] == name)
    old_source = Path(old_row['source']).read_text()
    new_source = (output / name).read_text()
    if name == 'output_63.cpp':
        start = old_source.index('void func_80212FA0(')
        end = old_source.index('\nvoid func_', start + 1)
        expected = old_source[:start] + old_source[start:end].replace(old_text, new_text) + old_source[end:]
    else:
        expected = old_source.replace(old_text, new_text)
    assert new_source == expected
assert live.count('DI86_INPUT_DCBI_LAB_OBSERVED_UNCHANGED\n') == 1
assert 'DI86_SOURCE 2 1 804983a0 32 1 1 935e0180' in live
assert 'DI86_SOURCE 3 1 804983a0 32 0 0 935e0180' in live
assert live.index('DI86_SOURCE 3') < live.index('DI_BURST_ES_REPLY 4') < live.index('DI_BURST_ES_SOURCE 0 a032 4')
assert 'BOOT_BOUNDARY pc=80212ff4 lr=80242fc8 msr=a032' in live
assert 'reason=EE flush caller/pending-state unverified' in live
assert 'BOOT_STM submitted=36 produced=16' in live
assert 'BOOT_SI_DELIVERY entries=38 callbacks=4' in live
assert 'BOOT_STM submitted=30 produced=14' in disabled
assert 'DI86_INPUT_DCBI' not in disabled and 'DI_BURST_ES_SOURCE' not in disabled
oracle_path = root / 'dolphin-di-burst-events-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
for kind, event in [(2, 106), (3, 107)]:
    row = raw[64 + event * 1280:64 + (event + 1) * 1280]
    for tag, offset in [('DI86_REPLY_CACHED', 64), ('DI86_REPLY_PHYSICAL', 128)]:
        prefix = tag + ' ' + str(kind) + ' '
        line = next(line for line in live.splitlines() if line.startswith(prefix))
        assert bytes(map(int, line[len(prefix):].split())) == row[offset:offset + 64]
(output / 'cache-audit.json').write_text(json.dumps({'result': 'DI86_ORIGINAL_CALLBACK32_CLEAR_FREE_ES_FD4_RETURN0_LAB_CACHE_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'originalCaptureSha256': sha(oracle_path), 'limits': [
        'Both native callback packet views equal original106/107, args1/804983A0/MSR32 and source clears busy/pending.',
        'ES scheduling gate checks original heap free0060/final write; no forced source callback/free.',
        'ES API0/FD4 matches original, but native MSR A032 differs from synthetic original caller2032; not normalized.',
        'Single scoped input-dcbi unchanged behavior is Dolphin LAB adaptation; physical Wii cache behavior unverified.',
        'CSR3C is composition of measured X2=8 and pending reply=4, not directly captured whole-burst control read.',
        'Inquiry output/callback and next ES ioctlv flush still unverified; no first screen.']}, indent=2) + '\n')
print('PASS fresh native DI86 original callback32/clear/both64/free gate→ES API0-FD4-A032; five rebuilt/120 retained; NEXT ioctlv flush')
