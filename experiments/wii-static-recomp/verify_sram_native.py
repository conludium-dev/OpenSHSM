"""Verify compiled original SRAM initialization and DMA against original captures."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_si_query_native.py'
body = parent.read_text().replace('si-query-native', 'sram-native').replace('si-query-probe', 'sram-probe').replace('si-query-host', 'sram-host')
body = body.replace('verify_si_query_dolphin.py', 'verify_sram_dolphin.py').replace('dolphin-si-query-callback/comparison.json', 'dolphin-sram/comparison.json')
body = body.replace('build_si_query_native.py', 'build_sram_native.py').replace('si_idle_backend.h', 'exi_getid_backend.h').replace('si_query_backend.h', 'exi_getid_backend.h')
body = body.replace('si_query_frontend.h', 'sram_frontend.h').replace('si_query_host.cpp', 'sram_host.cpp')
before = "expected = [[row['index'], *row['observations'], row['typeAfterCallback']] for row in oracle['reports'][1]['values']]"
after = '''expected = []
for row in oracle['reports'][0]['values']:
    phase = row['phase']
    scb = bytes.fromhex(row['scbHex'])
    observations = [phase[1], phase[2], phase[3], phase[0], phase[8], phase[9], phase[10], phase[0]]
    expected.append([row['index'], *row['scalar'], *scb, *row['ecb'], *row['abi'], *observations,
        phase[4], phase[6], row['index'] + 1, *scb[:64]])
assert build['settingsSha256'] == sha(output / 'settings.bin') == oracle['settingsSha256']
assert build['hostInputSha256'] == sha(experiment / 'sram_host.cpp')
assert build['getidFrontendSha256'] == sha(experiment / 'exi_getid_frontend.h')
assert build['baseBuilderSha256'] == sha(experiment / 'build_si_query_native.py')'''
assert body.count(before) == 1
body = body.replace(before, after)
body = body.replace("[str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode]", "[str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'settings.bin'), mode]")
body = body.replace("line.startswith('SI_QUERY_CASE ')", "line.startswith('SRAM_CASE ')")
body = body.replace("assert lost.returncode == 20 and not lost_values and 'SI_QUERY_LOST_COMPLETION polls=100001' in lost.stdout", '''assert lost.returncode == 20 and not lost_values and 'GetID instruction budget exceeded phase=0 control=53 dma=0' in lost.stdout
lost_dma, lost_dma_values = run('lost-dma')
assert lost_dma.returncode == 20 and not lost_dma_values and 'GetID instruction budget exceeded phase=1 control=3 dma=0' in lost_dma.stdout''')
body = body.replace('    row[4] = 0x01020300\n    row[9] = 0x010203a5', '    row[11] ^= 1\n    row[-64] ^= 1')
body = body.replace('SI_QUERY_GUARDS 8', 'SRAM_GUARDS 10')
body = body.replace("private / 'dolphin-si-query-callback/ghidra/verification.json'", "private / 'dolphin-sram/ghidra/verification.json'")
body = body.replace('verify_si_query_ghidra.py', 'verify_sram_ghidra.py')
body = body.replace("'guards': 8", "'guards': 10, 'lostDmaReturnCode': lost_dma.returncode")
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
output = Path('work/private-game/static-recomp/sram-native')
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'COMPILED_SRAM16_COMMAND_DMA_CACHE_ABI_MATCHES_ORIGINAL_AND_UNPATCHED'
report['baseVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Whole compiled original __OSInitSram/EXIImm/EXIDma/EXISync/UnlockSram; synchronous completion is a PC adaptation.',
    '64response bytes originate in the isolated Dolphin laboratory profile; private reference settings, not original game assets/personal Wii settings.',
    'DMA writes raw existing RAM backing; original cache invalidation and subsequent reads remain executed. No forced cache clearing or second EXI registry.',
    'Not timing/all-register/physical Wii/retail boot advance/first image or complete SRAM write-device support. Observed r3 is not a documented void return value.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 original compiled SRAM/DMA/cache/ABI; lost immediate+DMA completion/wrong response16/refusals10')
