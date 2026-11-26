"""Independently inspect recovered scalar-PPC roots in private dtk objects."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('.').resolve()
tools = root / '_scratch/tmp/wii-static-recomp-tools'
sdk = tools / 'ghidra-sdk/ghidra_12.1.4_PUBLIC'
jdk = tools / 'jdk-sdk/jdk-21.0.12.1+1/Contents/Home'
private = root / 'work/private-game/static-recomp'
output = private / 'frsp-roots/ghidra'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
records = []
for name, filename, count, size in [('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),
                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]:
    project = 'shsm-frsp-roots-' + name
    obj = private / 'dtk-output/obj' / filename
    command = [str(jdk / 'bin/java'), '-Xmx2G', '-Djava.awt.headless=true',
               '-Djava.system.class.loader=ghidra.GhidraClassLoader',
               '-Dapplication.settingsdir=' + str(tools / 'ghidra-settings'),
               '-Dapplication.cachedir=' + str(tools / 'ghidra-cache'),
               '-cp', str(sdk / 'Ghidra/Framework/Utility/lib/Utility.jar'),
               'ghidra.Ghidra', 'ghidra.app.util.headless.AnalyzeHeadless', str(output), project,
               *(['-process', filename] if (output / (project + '.gpr')).exists() else
                 ['-import', str(obj), '-processor', 'PowerPC:BE:32:default', '-cspec', 'default']),
               '-scriptPath', str(root / 'experiments/wii-static-recomp'),
               '-postScript', 'ExportRootCheck.java', str(output), name, str(count), str(size),
               '-analysisTimeoutPerFile', '180']
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    log = result.stdout + result.stderr
    (output / (name + '.log')).write_text(log)
    assert result.returncode == 0 and f'SHSM_ROOT_GHIDRA_PASS:{name}:{count}:{size}' in log, log[-3000:]
    records.append({'name': name, 'instructions': count, 'bytes': size, 'objectSha256': sha(obj),
                    'assemblySha256': sha(output / (name + '.asm')), 'decompiledSha256': sha(output / (name + '.c'))})
report = {'result': 'TWO_SCALAR_PPC_ROOTS_GHIDRA_BOUNDARIES_AND_DECOMPILER_PASS', 'records': records,
          'scriptSha256': sha(root / 'experiments/wii-static-recomp/ExportRootCheck.java'),
          'runnerSha256': sha(Path(__file__)),
          'limits': ['Relocatable dtk object boundaries/decompilation, not native/original behavior equivalence.',
                     'Third root includes Wii paired singles; default Ghidra PPC language verification not claimed.',
                     'Headless local verifier; Ghidra MCP remains unavailable.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending', flush=True)
