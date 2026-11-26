"""Compare the whole recompiled function, output store and native-return contract."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/verify_fp_initializer_native.py')
body = parent.read_text().replace('mass-fp-initializer-boot', 'mass-divide-initializer-boot').replace(
    'dolphin-fp-initializer', 'dolphin-divide-initializer').replace('verify_fp_initializer_dolphin.py', 'verify_divide_initializer_capture.py').replace(
    'build_fp_initializer_boot.py', 'build_divide_initializer_boot.py').replace('--fp-initializer-probe', '--divide-initializer-probe').replace(
    'FP_INITIALIZER_PROBE', 'DIVIDE_INITIALIZER_PROBE')
start, end = body.index("assert (output / 'fsubs_integer_bias.h')"), body.index('for path,digest')
body = body[:start] + '''component = root / 'divide-initializer-component'
for name in ('divide_initializer_adapter.h','divide_initializer_probe.h'):
    assert (output / name).read_bytes() == (component / name).read_bytes()
''' + body[end:]
start, end = body.index('runtime = '), body.index("print('PASS SAME125")
body = body[:start] + '''(output / 'initializer-native-comparison.json').write_text(json.dumps({
    'result':'SAME125_WHOLE_DIVIDE5_128_NATIVE_MATCH_AND_RETURN',
    'verifierSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'captureSha256':sha(capture_path),'probeLogSha256':sha(output / 'initializer-probe.log'),
    'cases':128,'limits':['Whole original five-instruction generated function using actual125 objects, no synthetic function result.',
        'Output store/neighbor/both F0-F1 lanes/FPSCR and SP-LR-MSR return-to-native contract compared; not physical Wii or full runtime.']},indent=2) + '\\n')
''' + "print('PASS SAME125 whole original divide5/native128/global-neighbor/paired lanes/FPSCR/stack-return')\n"
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
