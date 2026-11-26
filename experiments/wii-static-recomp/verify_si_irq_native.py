"""Verify the compiled SI handler and dispatcher callback against original IRQ captures."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'verify_si_query_native.py'
body = builder.read_text().replace('si-query-native', 'si-irq-native').replace('verify_si_query_dolphin.py', 'verify_si_irq_dolphin.py')
body = body.replace("sha(experiment / 'build_si_query_native.py')", "sha(experiment / 'build_si_irq_native.py')")
body = body.replace('dolphin-si-query-callback/comparison.json', 'dolphin-si-irq/comparison.json')
before = "expected = [[row['index'], *row['observations'], row['typeAfterCallback']] for row in oracle['reports'][1]['values']]"
assert body.count(before) == 1
body = body.replace(before, "expected = [[row['index'], *row['observations']] for row in oracle['values']]")
body = body.replace("line.startswith('SI_QUERY_CASE ')", "line.startswith('SI_IRQ_CASE ')")
before = "        assert Path(record['source']).read_text() == ''.join(lines)"
assert body.count(before) == 1
body = body.replace(before, '''        source_text = ''.join(lines)
        if record['file'] == 'output_63.cpp':
            observer = build['callbackObserver']
            assert source_text.count(observer['before']) == 1
            source_text = source_text.replace(observer['before'], observer['after'])
        assert Path(record['source']).read_text() == source_text''')
before = "assert (output / 'si-query-host.cpp').read_text() == '#include \"si_query_frontend.h\"\\n' + body + '\\n' + (experiment / 'si_query_host.cpp').read_text()"
assert body.count(before) == 1
body = body.replace(before, '''sentinel = build['hostSentinel']
assert body.count(sentinel['before']) == 1
body = body.replace(sentinel['before'], sentinel['after'])
assert (output / 'si-query-host.cpp').read_text() == '#include "si_query_frontend.h"\\n' + body + '\\n' + build['hostBody']
assert 'func_8020F550(' not in build['hostBody'] and 'func_80210110(' not in build['hostBody']
assert build['hostBody'].count('run_game(context);') == 1
assert build['hostInputSha256'] == sha(experiment / 'si_query_host.cpp')
assert build['baseBuilderSha256'] == sha(experiment / 'build_si_query_native.py')
assert build['dispatcherSha256'] == sha(private / 'mass-current/main_output.cpp')''')
body = body.replace('PASS16 whole compiled SI setup/completion/callback;18observed fields/final type8;lost completion/wrong response16/refusals8',
    'PASS16 whole compiled SI handler/run_game callback:22fields/PI/status/type8;lost completion/wrong response16/refusals8')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = Path('work/private-game/static-recomp/si-irq-native')
path = output / 'comparison.json'
report = json.loads(path.read_text())
ghidra_path = Path('work/private-game/static-recomp/dolphin-si-irq/ghidra/verification.json')
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['runnerSha256'] == sha(experiment / 'verify_si_irq_ghidra.py')
assert ghidra['scriptSha256'] == sha(experiment / 'ExportFormatSpan.java')
assert ghidra['records'][0]['discoveredBodyBytes'] == 1004
for row in ghidra['records']:
    assert row['objectSha256'] == sha(Path('work/private-game/static-recomp/dtk-output/obj/auto_03_802045CC_text.o'))
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
report['result'] = 'COMPILED_SI_IRQ_HANDLER16_DISPATCHER_CALLBACK_MATCHES_ORIGINAL'
report['baseVerifierSha256'] = sha(builder)
report['handlerGhidraSha256'] = sha(ghidra_path)
report['limits'] = ['Disconnected SI ports/empty queue/prepared SDK state; synchronous completion and scripted clock are PC fixtures.',
    'Original handler performs completion and callback through unchanged run_game; host supplies handler entry, not CPU external-exception delivery.',
    'No queued packets/alarms/attached input/physical Wii/all-register/full SI or game-image/boot-integration proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
