"""Compare polling-delivered compiled SI vector/OS context return with Dolphin."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_si_irq_native.py'
source = parent.read_text()
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
assert source.count(marker) == 1
namespace = {'__file__': __file__}
exec(compile(source.split(marker)[0], str(parent), 'exec'), namespace)
body = namespace['body'].replace('si-irq-native', 'si-vector-native').replace('verify_si_irq_dolphin.py', 'verify_si_vector_dolphin.py')
body = body.replace('build_si_irq_native.py', 'build_si_vector_native.py').replace('dolphin-si-irq/comparison.json', 'dolphin-si-vector/comparison.json')
marker = "        assert Path(record['source']).read_text() == source_text"
assert body.count(marker) == 1
body = body.replace(marker, '''        if record['file'] == 'output_63.cpp':
            for before, after in build['vectorChanges']:
                count = 38 if before.startswith('nwii::runtime::experiment_template_execution_guard') else 1
                assert source_text.count(before) == count
                source_text = source_text.replace(before, after)
''' + marker)
marker = 'assert positive.stdout + positive.stderr == (output / \'native.log\').read_text()'
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
contexts = [[int(value) for value in line.split()[1:]] for line in positive.stdout.splitlines() if line.startswith('SI_VECTOR_CONTEXT ')]
assert len(contexts) == 16
for index, actual_context in enumerate(contexts):
    reference = list(oracle['vectorValues'][index]['observations'])
    assert reference[1] == reference[10]
    reference[1] = reference[10] = 0x807f0000
    assert actual_context == [index, *reference], (index, actual_context, reference)
assert build['externalDeliverySha256'] == sha(experiment / 'si_external_delivery.h')
assert build['pollSha256'] == sha(experiment / 'boot_poll.h')
assert build['batMemorySha256'] == sha(experiment / 'bat_memory_frontend.h')
assert 'context.pc = 0x8020f850;' not in build['hostBody']
assert 'SI_EXTERNAL_GUARDS 8 GATES 3' in run('guards')[0].stdout
''')
validated = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), validated)
private = Path('work/private-game/static-recomp')
output = private / 'si-vector-native'
path = output / 'comparison.json'
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report['result'] = 'COMPILED_SI_CPU_POLL_VECTOR16_CONTEXT_RETURN_MATCHES_ORIGINAL'
report['baseVerifierSha256'] = sha(parent)
assert validated['build']['irqBuilderSha256'] == sha(experiment / 'build_si_irq_native.py')
report['contextValues'] = validated['contexts']
report['externalGuards'] = 8
report['nonDeliveryGates'] = 3
report['limits'] = ['Prepared original vector/OS context/tables/masks/None-port profile; native synchronous completion and scripted clock remain PC adaptations.',
    'Native sentinel807F0000 replaces the Dolphin post-mtmsr continuation in both SRR0 observations; other12context/return fields compare unchanged.',
    'Existing CPU polling/run_game delivers the cause; original handler/dispatcher/callback/LoadContext execute. Physical500 maps to compiled template80211BA0 after full copied-byte validation.',
    'Scoped vector DR-off MEM1 accesses share existing D-cache; other bypass profiles remain unverified. No retail boot integration/first image/timing/full-register/attached-controller/Wiimote/physicalWii acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 polling-delivered SI vector/OS-handler/return:22packet+12context fields, IRQ guards8/gates3')
