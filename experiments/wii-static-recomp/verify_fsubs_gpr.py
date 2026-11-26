"""Check the new original register routing using the unchanged numeric helper."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fsubs_variant.py')
body = parent.read_text().replace('dolphin-fsubs-variant', 'dolphin-fsubs-gpr').replace(
    'build_fsubs_variant_dolphin.py', 'build_fsubs_gpr_dolphin.py').replace(
    'run_fsubs_variant_dolphin.ps1', 'run_fsubs_gpr_dolphin.ps1').replace('ec401828', 'ec201028').replace(
    '(208,464,704,192,216,448,472)', '(200,456,704,192,208,448,464)').replace(
    '(208,464,708,192,216,448,472,36)', '(200,456,708,192,208,448,464,36)').replace(
    'PREFIX16', 'PREFIX19').replace('prefix16', 'prefix19').replace('first16', 'first19').replace(
    'F2-F0-F3', 'F1-F0-F2').replace('destinationF2/leftF0/rightF3', 'destinationF1/leftF0/rightF2')
marker = "runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')"
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
probe = output / 'gpr-probe.cpp'
source = (experiment / 'fsubs_variant_probe.cpp').read_text().replace('0xec401828','0xec201028').replace(
    'context.fpr[3]', 'context.fpr[2]').replace('context.ps1[3]', 'context.ps1[2]')
source = source.replace('std::bit_cast<uint64_t>(context.fpr[2])', 'std::bit_cast<uint64_t>(context.fpr[1])',1).replace(
    'std::bit_cast<uint64_t>(context.ps1[2])', 'std::bit_cast<uint64_t>(context.ps1[1])',1)
probe.write_text(source)
''')
body = body.replace("str(experiment / 'fsubs_variant_probe.cpp')", 'str(probe)').replace(
    "sha(experiment / 'fsubs_variant_probe.cpp')", 'sha(probe)')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
